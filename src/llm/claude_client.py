"""
Claude API client with tool calling support for structured outputs.

This module provides a production-ready wrapper around the Anthropic API
with built-in retry logic, error handling, and tool calling for structured JSON.
"""

import json
import time
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
import anthropic
from anthropic.types import Message, ToolUseBlock

from src.utils.config import get_claude_config
from src.utils.logger import get_logger
from src.utils.errors import ClaudeAPIError


@dataclass
class Tool:
    """
    Definition of a tool that Claude can use for structured output.

    Example:
        tool = Tool(
            name="create_simulation_plan",
            description="Parse user input into structured simulation plan",
            input_schema={
                "type": "object",
                "properties": {
                    "simulation_type": {"type": "string", "enum": ["rigid_body", "fluid"]},
                    "objects": {"type": "array", "items": {"type": "object"}}
                },
                "required": ["simulation_type", "objects"]
            }
        )
    """
    name: str
    description: str
    input_schema: Dict[str, Any]


@dataclass
class ToolCall:
    """Result from a tool call."""
    tool_name: str
    tool_input: Dict[str, Any]
    raw_response: Message


class ClaudeClient:
    """
    Production-ready Claude API client with tool calling support.

    Features:
    - Automatic retry with exponential backoff
    - Token usage tracking
    - Error handling and recovery
    - Tool calling for structured outputs
    - Request/response logging

    Usage:
        client = ClaudeClient()

        # Simple completion
        response = client.complete("Explain rigid body physics")

        # Structured output with tool calling
        tool = Tool(name="parse_input", description="...", input_schema={...})
        result = client.call_tool(
            prompt="Create 10 cubes falling",
            tool=tool
        )
        print(result.tool_input)  # Parsed JSON
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        timeout_seconds: Optional[int] = None,
    ):
        """
        Initialize Claude client.

        Args:
            api_key: Anthropic API key (defaults to config)
            model: Model name (defaults to config)
            max_tokens: Maximum tokens to generate (defaults to config)
            temperature: Sampling temperature 0-1 (defaults to config)
            timeout_seconds: Request timeout (defaults to config)
        """
        config = get_claude_config()

        self.api_key = api_key or config.api_key
        self.model = model or config.model
        self.max_tokens = max_tokens or config.max_tokens
        self.temperature = temperature or config.temperature
        self.timeout = timeout_seconds or config.timeout_seconds

        if not self.api_key:
            raise ClaudeAPIError(
                "Claude API key not configured. Set CLAUDE_API_KEY environment variable.",
                status_code=None
            )

        self.client = anthropic.Client(api_key=self.api_key, timeout=self.timeout)
        self.logger = get_logger("ClaudeClient")

        # Track usage
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.request_count = 0

    def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stop_sequences: Optional[List[str]] = None,
    ) -> str:
        """
        Generate a text completion (no tool calling).

        Args:
            prompt: User prompt
            system: Optional system prompt
            max_tokens: Override default max_tokens
            temperature: Override default temperature
            stop_sequences: Sequences where the model should stop

        Returns:
            Generated text

        Raises:
            ClaudeAPIError: If API call fails after retries
        """
        self.logger.start("complete", prompt_length=len(prompt))

        messages = [{"role": "user", "content": prompt}]

        try:
            response = self._make_request(
                messages=messages,
                system=system,
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature or self.temperature,
                stop_sequences=stop_sequences,
            )

            # Extract text from response
            text = self._extract_text(response)

            self.logger.success(
                "complete",
                response_length=len(text),
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens
            )

            return text

        except Exception as e:
            self.logger.error("complete", e)
            raise ClaudeAPIError(
                f"Failed to generate completion: {str(e)}",
                status_code=getattr(e, 'status_code', None)
            )

    def call_tool(
        self,
        prompt: str,
        tool: Tool,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        require_tool_use: bool = True,
    ) -> ToolCall:
        """
        Use tool calling to get structured JSON output.

        This is the recommended way to get reliable structured data from Claude.

        Args:
            prompt: User prompt describing what to generate
            tool: Tool definition with JSON schema
            system: Optional system prompt
            max_tokens: Override default max_tokens
            require_tool_use: Raise error if Claude doesn't use the tool

        Returns:
            ToolCall object with parsed JSON

        Raises:
            ClaudeAPIError: If API call fails
            ValueError: If tool not used and require_tool_use=True

        Example:
            tool = Tool(
                name="create_plan",
                description="Generate simulation plan",
                input_schema={
                    "type": "object",
                    "properties": {
                        "sim_type": {"type": "string"},
                        "objects": {"type": "array"}
                    }
                }
            )

            result = client.call_tool(
                prompt="Create 10 falling cubes",
                tool=tool
            )
            plan = result.tool_input  # Validated JSON
        """
        self.logger.start("call_tool", tool_name=tool.name, prompt_length=len(prompt))

        messages = [{"role": "user", "content": prompt}]

        # Format tool for Claude API
        tools = [self._format_tool(tool)]

        try:
            response = self._make_request(
                messages=messages,
                system=system,
                max_tokens=max_tokens or self.max_tokens,
                temperature=self.temperature,
                tools=tools,
                tool_choice={"type": "tool", "name": tool.name} if require_tool_use else {"type": "auto"},
            )

            # Extract tool use from response
            tool_call = self._extract_tool_call(response, tool.name, require_tool_use)

            self.logger.success(
                "call_tool",
                tool_name=tool.name,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens
            )

            return tool_call

        except Exception as e:
            self.logger.error("call_tool", e, tool_name=tool.name)
            raise ClaudeAPIError(
                f"Failed to call tool '{tool.name}': {str(e)}",
                status_code=getattr(e, 'status_code', None)
            )

    def call_with_retry(
        self,
        prompt: str,
        tool: Optional[Tool] = None,
        max_retries: int = 3,
        **kwargs
    ) -> Union[str, ToolCall]:
        """
        Make API call with automatic retry on failure.

        Args:
            prompt: User prompt
            tool: Optional tool for structured output
            max_retries: Maximum retry attempts
            **kwargs: Additional arguments for complete() or call_tool()

        Returns:
            Text response or ToolCall

        Raises:
            ClaudeAPIError: If all retries fail
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                if tool:
                    return self.call_tool(prompt, tool, **kwargs)
                else:
                    return self.complete(prompt, **kwargs)

            except ClaudeAPIError as e:
                last_error = e
                self.logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed",
                    error=str(e)
                )

                # Exponential backoff
                if attempt < max_retries - 1:
                    sleep_time = 2 ** attempt
                    time.sleep(sleep_time)

        # All retries failed
        raise last_error

    def _make_request(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.2,
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[Dict] = None,
        stop_sequences: Optional[List[str]] = None,
    ) -> Message:
        """
        Make a request to Claude API with error handling.

        Args:
            messages: List of message dicts
            system: System prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            tools: List of tool definitions
            tool_choice: Tool selection strategy
            stop_sequences: Stop sequences

        Returns:
            Anthropic Message object

        Raises:
            ClaudeAPIError: If request fails
        """
        try:
            request_params = {
                "model": self.model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages,
            }

            if system:
                request_params["system"] = system

            if tools:
                request_params["tools"] = tools

            if tool_choice:
                request_params["tool_choice"] = tool_choice

            if stop_sequences:
                request_params["stop_sequences"] = stop_sequences

            response = self.client.messages.create(**request_params)

            # Track usage
            self.total_input_tokens += response.usage.input_tokens
            self.total_output_tokens += response.usage.output_tokens
            self.request_count += 1

            return response

        except anthropic.APIError as e:
            raise ClaudeAPIError(
                f"Claude API error: {str(e)}",
                status_code=getattr(e, 'status_code', None),
                response=getattr(e, 'body', None)
            )
        except Exception as e:
            raise ClaudeAPIError(f"Unexpected error: {str(e)}")

    def _format_tool(self, tool: Tool) -> Dict[str, Any]:
        """Format Tool object for Claude API."""
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema
        }

    def _extract_text(self, response: Message) -> str:
        """Extract text content from Claude response."""
        for block in response.content:
            if block.type == "text":
                return block.text
        return ""

    def _extract_tool_call(
        self,
        response: Message,
        expected_tool_name: str,
        require_tool_use: bool
    ) -> ToolCall:
        """Extract tool use from Claude response."""
        for block in response.content:
            if isinstance(block, ToolUseBlock):
                if block.name == expected_tool_name:
                    return ToolCall(
                        tool_name=block.name,
                        tool_input=block.input,
                        raw_response=response
                    )

        # Tool not used
        if require_tool_use:
            raise ValueError(
                f"Claude did not use the required tool '{expected_tool_name}'. "
                f"Response: {self._extract_text(response)[:200]}"
            )

        # Return empty tool call
        return ToolCall(
            tool_name=expected_tool_name,
            tool_input={},
            raw_response=response
        )

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get token usage statistics."""
        return {
            "total_requests": self.request_count,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "estimated_cost_usd": self._estimate_cost(),
        }

    def _estimate_cost(self) -> float:
        """Estimate API cost based on token usage."""
        # Pricing for Claude Sonnet 4.5 (as of Jan 2025)
        # Input: $3 per million tokens
        # Output: $15 per million tokens
        input_cost = (self.total_input_tokens / 1_000_000) * 3.0
        output_cost = (self.total_output_tokens / 1_000_000) * 15.0
        return round(input_cost + output_cost, 4)

    def reset_stats(self) -> None:
        """Reset usage statistics."""
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.request_count = 0
