"""
Custom exception classes for Blender AI Simulation Generator.

Provides structured error handling with recovery strategies.
"""

from typing import Optional
from src.models.schemas import ErrorType


class BlenderAIError(Exception):
    """Base exception for all Blender AI errors."""

    def __init__(
        self,
        message: str,
        error_type: Optional[ErrorType] = None,
        recoverable: bool = True,
        suggested_action: Optional[str] = None
    ):
        """
        Initialize Blender AI error.

        Args:
            message: Human-readable error message
            error_type: Category of error (for recovery strategies)
            recoverable: Whether this error can be recovered from
            suggested_action: Suggested action to resolve the error
        """
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.recoverable = recoverable
        self.suggested_action = suggested_action

    def to_dict(self) -> dict:
        """Convert error to dictionary format."""
        return {
            "error_class": self.__class__.__name__,
            "message": self.message,
            "error_type": self.error_type.value if self.error_type else None,
            "recoverable": self.recoverable,
            "suggested_action": self.suggested_action,
        }


class PlanningError(BlenderAIError):
    """Raised when the Planner Agent fails to parse user input."""

    def __init__(self, message: str, user_input: Optional[str] = None):
        """
        Initialize planning error.

        Args:
            message: Error description
            user_input: The input that failed to parse
        """
        super().__init__(
            message=message,
            error_type=ErrorType.REQUIREMENTS_ERROR,
            recoverable=True,
            suggested_action="Rephrase the simulation request with more specific details"
        )
        self.user_input = user_input


class ValidationError(BlenderAIError):
    """Raised when validation fails (physics, syntax, quality)."""

    def __init__(
        self,
        message: str,
        validation_type: str,
        details: Optional[dict] = None
    ):
        """
        Initialize validation error.

        Args:
            message: Error description
            validation_type: Type of validation that failed (physics, syntax, quality)
            details: Additional details about the failure
        """
        error_types = {
            "syntax": ErrorType.SYNTAX_ERROR,
            "physics": ErrorType.PHYSICS_ERROR,
            "quality": ErrorType.LOGIC_ERROR,
        }

        super().__init__(
            message=message,
            error_type=error_types.get(validation_type, ErrorType.LOGIC_ERROR),
            recoverable=True,
            suggested_action=f"Review {validation_type} validation errors and regenerate"
        )
        self.validation_type = validation_type
        self.details = details or {}


class SyntaxError(ValidationError):
    """Raised when generated Blender code has syntax errors."""

    def __init__(self, message: str, code_snippet: Optional[str] = None):
        """
        Initialize syntax error.

        Args:
            message: Error description
            code_snippet: The problematic code
        """
        super().__init__(
            message=message,
            validation_type="syntax",
            details={"code_snippet": code_snippet}
        )
        self.suggested_action = "Regenerate code with stricter syntax validation"


class PhysicsError(ValidationError):
    """Raised when physics parameters are invalid."""

    def __init__(self, message: str, invalid_params: Optional[dict] = None):
        """
        Initialize physics error.

        Args:
            message: Error description
            invalid_params: Dictionary of invalid parameters
        """
        super().__init__(
            message=message,
            validation_type="physics",
            details={"invalid_params": invalid_params}
        )
        self.suggested_action = "Use realistic physics parameters from materials database"


class ExecutionError(BlenderAIError):
    """Raised when Blender execution fails."""

    def __init__(
        self,
        message: str,
        blender_output: Optional[str] = None,
        exit_code: Optional[int] = None
    ):
        """
        Initialize execution error.

        Args:
            message: Error description
            blender_output: Blender's stderr output
            exit_code: Blender process exit code
        """
        super().__init__(
            message=message,
            error_type=ErrorType.API_ERROR,
            recoverable=True,
            suggested_action="Check Blender installation and script compatibility"
        )
        self.blender_output = blender_output
        self.exit_code = exit_code


class QualityError(BlenderAIError):
    """Raised when quality validation fails."""

    def __init__(
        self,
        message: str,
        quality_score: float,
        threshold: float,
        issues: Optional[list] = None
    ):
        """
        Initialize quality error.

        Args:
            message: Error description
            quality_score: Calculated quality score (0-1)
            threshold: Minimum required score
            issues: List of quality issues found
        """
        super().__init__(
            message=message,
            error_type=ErrorType.LOGIC_ERROR,
            recoverable=True,
            suggested_action="Run refinement agent to improve quality"
        )
        self.quality_score = quality_score
        self.threshold = threshold
        self.issues = issues or []


class ClaudeAPIError(BlenderAIError):
    """Raised when Claude API calls fail."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response: Optional[str] = None
    ):
        """
        Initialize Claude API error.

        Args:
            message: Error description
            status_code: HTTP status code
            response: API response body
        """
        super().__init__(
            message=message,
            error_type=ErrorType.API_ERROR,
            recoverable=True,
            suggested_action="Check API key and rate limits, retry after delay"
        )
        self.status_code = status_code
        self.response = response


class ResourceError(BlenderAIError):
    """Raised when system resources are insufficient."""

    def __init__(self, message: str, resource_type: str):
        """
        Initialize resource error.

        Args:
            message: Error description
            resource_type: Type of resource (memory, disk, cpu)
        """
        super().__init__(
            message=message,
            error_type=ErrorType.MEMORY_ERROR,
            recoverable=False,
            suggested_action=f"Free up {resource_type} or reduce simulation complexity"
        )
        self.resource_type = resource_type


class ConfigurationError(BlenderAIError):
    """Raised when configuration is invalid."""

    def __init__(self, message: str, config_key: Optional[str] = None):
        """
        Initialize configuration error.

        Args:
            message: Error description
            config_key: The problematic configuration key
        """
        super().__init__(
            message=message,
            error_type=ErrorType.REQUIREMENTS_ERROR,
            recoverable=False,
            suggested_action="Check config.yaml and environment variables"
        )
        self.config_key = config_key


class TimeoutError(BlenderAIError):
    """Raised when an operation times out."""

    def __init__(self, message: str, timeout_seconds: int, operation: str):
        """
        Initialize timeout error.

        Args:
            message: Error description
            timeout_seconds: The timeout limit
            operation: The operation that timed out
        """
        super().__init__(
            message=message,
            error_type=ErrorType.API_ERROR,
            recoverable=True,
            suggested_action=f"Increase timeout or simplify {operation}"
        )
        self.timeout_seconds = timeout_seconds
        self.operation = operation


# Recovery strategy mapping
ERROR_RECOVERY_STRATEGIES = {
    ErrorType.SYNTAX_ERROR: "regenerate_with_feedback",
    ErrorType.API_ERROR: "retry_with_backoff",
    ErrorType.PHYSICS_ERROR: "use_fallback_params",
    ErrorType.MEMORY_ERROR: "reduce_complexity",
    ErrorType.LOGIC_ERROR: "run_refinement",
    ErrorType.REQUIREMENTS_ERROR: "request_clarification",
}


def get_recovery_strategy(error_type: ErrorType) -> str:
    """
    Get the recommended recovery strategy for an error type.

    Args:
        error_type: The type of error

    Returns:
        Recovery strategy name
    """
    return ERROR_RECOVERY_STRATEGIES.get(
        error_type,
        "manual_intervention"
    )


def format_error_for_refinement(error: BlenderAIError) -> str:
    """
    Format error message for the Refinement Agent.

    Args:
        error: The error to format

    Returns:
        Human-readable error description for Claude
    """
    parts = [
        f"Error Type: {error.error_type.value if error.error_type else 'Unknown'}",
        f"Message: {error.message}",
    ]

    if error.suggested_action:
        parts.append(f"Suggested Action: {error.suggested_action}")

    if isinstance(error, ValidationError):
        parts.append(f"Validation Type: {error.validation_type}")
        if error.details:
            parts.append(f"Details: {error.details}")

    elif isinstance(error, QualityError):
        parts.append(f"Quality Score: {error.quality_score:.2f} (threshold: {error.threshold:.2f})")
        if error.issues:
            parts.append(f"Issues: {', '.join(error.issues)}")

    return "\n".join(parts)
