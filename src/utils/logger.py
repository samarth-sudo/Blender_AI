"""
Structured logging for Blender AI Simulation Generator.

Provides consistent, production-ready logging across all agents.
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime
import structlog
from colorama import Fore, Style, init as colorama_init

from src.utils.config import get_config


# Initialize colorama for Windows support
colorama_init(autoreset=True)


def setup_logging(
    log_level: Optional[str] = None,
    log_file: Optional[Path] = None,
    enable_console: bool = True
) -> None:
    """
    Configure structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file
        enable_console: Whether to log to console
    """
    config = get_config()

    # Use config values if not provided
    log_level = log_level or config.logging.get("level", "INFO")
    log_file = log_file or config.paths.log_file

    # Create log directory
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Configure structlog processors
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Add console renderer if enabled
    if enable_console:
        processors.append(
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback,
            )
        )
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout) if enable_console else logging.NullHandler(),
        ],
    )


class AgentLogger:
    """
    Structured logger for agent operations.

    Automatically adds agent context and timing information.
    """

    def __init__(self, agent_name: str):
        """
        Initialize agent logger.

        Args:
            agent_name: Name of the agent (e.g., "PlannerAgent")
        """
        self.agent_name = agent_name
        self.logger = structlog.get_logger(agent_name)
        self.start_time = None

    def start(self, operation: str, **kwargs) -> None:
        """Log the start of an operation."""
        self.start_time = datetime.now()
        self.logger.info(
            f"Starting {operation}",
            agent=self.agent_name,
            operation=operation,
            **kwargs
        )

    def success(self, operation: str, **kwargs) -> None:
        """Log successful completion."""
        elapsed = self._get_elapsed()
        self.logger.info(
            f"Completed {operation}",
            agent=self.agent_name,
            operation=operation,
            elapsed_seconds=elapsed,
            status="success",
            **kwargs
        )

    def error(self, operation: str, error: Exception, **kwargs) -> None:
        """Log an error."""
        elapsed = self._get_elapsed()
        self.logger.error(
            f"Failed {operation}",
            agent=self.agent_name,
            operation=operation,
            elapsed_seconds=elapsed,
            error_type=type(error).__name__,
            error_message=str(error),
            status="error",
            **kwargs
        )

    def warning(self, message: str, **kwargs) -> None:
        """Log a warning."""
        self.logger.warning(
            message,
            agent=self.agent_name,
            **kwargs
        )

    def info(self, message: str, **kwargs) -> None:
        """Log informational message."""
        self.logger.info(
            message,
            agent=self.agent_name,
            **kwargs
        )

    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        self.logger.debug(
            message,
            agent=self.agent_name,
            **kwargs
        )

    def _get_elapsed(self) -> Optional[float]:
        """Calculate elapsed time since operation start."""
        if self.start_time:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            return round(elapsed, 3)
        return None


class PipelineLogger:
    """
    Logger for tracking the entire simulation pipeline.

    Tracks timing for each agent and overall pipeline performance.
    """

    def __init__(self, session_id: str):
        """
        Initialize pipeline logger.

        Args:
            session_id: Unique identifier for this pipeline run
        """
        self.session_id = session_id
        self.logger = structlog.get_logger("Pipeline")
        self.start_time = datetime.now()
        self.agent_times = {}

    def log_agent_start(self, agent_name: str) -> None:
        """Log when an agent starts."""
        self.agent_times[agent_name] = {"start": datetime.now()}
        self.logger.info(
            f"Agent starting: {agent_name}",
            session_id=self.session_id,
            agent=agent_name,
            pipeline_elapsed=self._get_pipeline_elapsed()
        )

    def log_agent_complete(self, agent_name: str, success: bool, **kwargs) -> None:
        """Log when an agent completes."""
        if agent_name in self.agent_times:
            end_time = datetime.now()
            elapsed = (end_time - self.agent_times[agent_name]["start"]).total_seconds()
            self.agent_times[agent_name]["end"] = end_time
            self.agent_times[agent_name]["elapsed"] = elapsed

            self.logger.info(
                f"Agent completed: {agent_name}",
                session_id=self.session_id,
                agent=agent_name,
                agent_elapsed=elapsed,
                pipeline_elapsed=self._get_pipeline_elapsed(),
                success=success,
                **kwargs
            )

    def log_pipeline_complete(self, success: bool, **kwargs) -> None:
        """Log when the entire pipeline completes."""
        total_elapsed = self._get_pipeline_elapsed()

        self.logger.info(
            "Pipeline completed",
            session_id=self.session_id,
            total_elapsed=total_elapsed,
            success=success,
            agent_times={
                name: times.get("elapsed", 0)
                for name, times in self.agent_times.items()
            },
            **kwargs
        )

    def _get_pipeline_elapsed(self) -> float:
        """Get elapsed time since pipeline start."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return round(elapsed, 3)


def get_logger(name: str) -> AgentLogger:
    """
    Get a logger instance for an agent.

    Args:
        name: Name of the agent or module

    Returns:
        AgentLogger instance
    """
    return AgentLogger(name)


# Console formatting utilities
def format_success(message: str) -> str:
    """Format a success message with color."""
    return f"{Fore.GREEN}✓{Style.RESET_ALL} {message}"


def format_error(message: str) -> str:
    """Format an error message with color."""
    return f"{Fore.RED}✗{Style.RESET_ALL} {message}"


def format_warning(message: str) -> str:
    """Format a warning message with color."""
    return f"{Fore.YELLOW}⚠{Style.RESET_ALL} {message}"


def format_info(message: str) -> str:
    """Format an info message with color."""
    return f"{Fore.CYAN}ℹ{Style.RESET_ALL} {message}"


# Initialize logging when module is imported
setup_logging()
