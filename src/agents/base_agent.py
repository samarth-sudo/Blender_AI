"""
Base agent class with common functionality.

All agents inherit from BaseAgent to get:
- Structured logging
- Timing measurements
- Error handling
- Configuration access
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
from datetime import datetime

from src.utils.logger import AgentLogger
from src.utils.config import get_config
from src.utils.errors import BlenderAIError


class BaseAgent(ABC):
    """
    Base class for all agents in the pipeline.

    Each agent performs a specific task in the simulation generation pipeline.
    Agents are designed to be:
    - Stateless (no side effects)
    - Testable (clear inputs/outputs)
    - Observable (comprehensive logging)
    """

    def __init__(self, name: Optional[str] = None):
        """
        Initialize base agent.

        Args:
            name: Agent name (defaults to class name)
        """
        self.name = name or self.__class__.__name__
        self.logger = AgentLogger(self.name)
        self.config = get_config()

        # Statistics
        self.execution_count = 0
        self.total_time = 0.0
        self.error_count = 0

    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        """
        Execute the agent's primary function.

        This method must be implemented by all subclasses.

        Returns:
            Agent-specific output
        """
        pass

    def run(self, *args, **kwargs) -> Any:
        """
        Wrapper around execute() that adds logging and error handling.

        Use this method instead of calling execute() directly.

        Returns:
            Result from execute()

        Raises:
            BlenderAIError: If execution fails
        """
        self.logger.start("execute")
        start_time = datetime.now()

        try:
            result = self.execute(*args, **kwargs)

            elapsed = (datetime.now() - start_time).total_seconds()
            self.total_time += elapsed
            self.execution_count += 1

            self.logger.success(
                "execute",
                execution_time=elapsed
            )

            return result

        except BlenderAIError as e:
            self.error_count += 1
            self.logger.error("execute", e)
            raise

        except Exception as e:
            self.error_count += 1
            self.logger.error("execute", e)
            raise BlenderAIError(
                f"{self.name} execution failed: {str(e)}",
                recoverable=False
            )

    def get_stats(self) -> dict:
        """Get execution statistics for this agent."""
        avg_time = self.total_time / self.execution_count if self.execution_count > 0 else 0

        return {
            "agent": self.name,
            "executions": self.execution_count,
            "total_time": round(self.total_time, 3),
            "average_time": round(avg_time, 3),
            "errors": self.error_count,
        }

    def reset_stats(self) -> None:
        """Reset execution statistics."""
        self.execution_count = 0
        self.total_time = 0.0
        self.error_count = 0
