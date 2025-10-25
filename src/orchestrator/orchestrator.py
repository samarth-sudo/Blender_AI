"""
Simulation Orchestrator - The central coordinator for the multi-agent pipeline.

This is the main entry point for generating simulations. It coordinates all 6 agents:
1. PlannerAgent
2. PhysicsValidatorAgent
3. CodeGeneratorAgent
4. SyntaxValidatorAgent
5. ExecutorAgent
6. QualityValidatorAgent

The orchestrator handles:
- Agent sequencing
- Error recovery
- Progress tracking
- Result aggregation
"""

import uuid
from pathlib import Path
from typing import Optional, Callable
from datetime import datetime

from src.agents import (
    PlannerAgent,
    PhysicsValidatorAgent,
    CodeGeneratorAgent,
    SyntaxValidatorAgent,
    ExecutorAgent,
    QualityValidatorAgent,
    RefinementAgent,
)
from src.models.schemas import (
    SimulationPlan,
    BlenderCode,
    ValidationResult,
    ExecutionResult,
    QualityMetrics,
    SimulationResult,
)
from src.llm import ClaudeClient
from src.utils.config import get_config
from src.utils.logger import PipelineLogger, get_logger
from src.utils.errors import (
    BlenderAIError,
    PlanningError,
    ValidationError,
    ExecutionError,
    QualityError,
)


class SimulationOrchestrator:
    """
    Central orchestrator for the Blender AI simulation pipeline.

    This class coordinates all agents to generate simulations from natural language.

    Example usage:
        ```python
        orchestrator = SimulationOrchestrator()

        # Simple generation
        result = orchestrator.generate_simulation(
            "Create 20 wooden blocks falling on a table"
        )

        if result.success:
            print(f"Simulation saved to: {result.blend_file}")
            print(f"Quality score: {result.quality_metrics.quality_score}")

        # With custom output path
        result = orchestrator.generate_simulation(
            "Smoke rising from a sphere",
            output_path="/tmp/my_smoke_sim.blend"
        )
        ```

    Advanced usage with progress callback:
        ```python
        def progress_callback(step: str, progress: float):
            print(f"[{progress:.0%}] {step}")

        result = orchestrator.generate_simulation(
            "Red cloth draped over a sphere",
            progress_callback=progress_callback,
            enable_refinement=True
        )
        ```
    """

    def __init__(
        self,
        claude_client: Optional[ClaudeClient] = None,
        output_dir: Optional[Path] = None,
        enable_auto_retry: bool = True
    ):
        """
        Initialize the orchestrator.

        Args:
            claude_client: Optional Claude client (creates new one if not provided)
            output_dir: Directory for output files (defaults to config)
            enable_auto_retry: Enable automatic retry on recoverable errors
        """
        self.config = get_config()
        self.logger = get_logger("Orchestrator")

        # Initialize Claude client
        self.claude = claude_client or ClaudeClient()

        # Output directory
        self.output_dir = output_dir or self.config.paths.output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Auto-retry configuration
        self.enable_auto_retry = enable_auto_retry
        self.max_retries = self.config.errors.get("max_retry_attempts", 2)

        # Initialize agents
        self._initialize_agents()

        self.logger.info("Orchestrator initialized", output_dir=str(self.output_dir))

    def _initialize_agents(self) -> None:
        """Initialize all agents in the pipeline."""
        self.planner = PlannerAgent(self.claude)
        self.physics_validator = PhysicsValidatorAgent()
        self.code_generator = CodeGeneratorAgent(self.claude)
        self.syntax_validator = SyntaxValidatorAgent()
        self.executor = ExecutorAgent()
        self.quality_validator = QualityValidatorAgent()
        self.refinement = RefinementAgent(self.claude)

        self.logger.info("All agents initialized")

    def generate_simulation(
        self,
        user_prompt: str,
        output_path: Optional[str] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        enable_refinement: bool = False,
        max_refinement_iterations: int = 2
    ) -> SimulationResult:
        """
        Generate a complete Blender simulation from natural language.

        This is the main method that runs the entire pipeline.

        Args:
            user_prompt: Natural language description (e.g., "20 cubes falling")
            output_path: Where to save .blend file (auto-generated if not provided)
            progress_callback: Optional callback(step_name, progress_0_to_1)
            enable_refinement: Enable quality-based refinement loop
            max_refinement_iterations: Maximum refinement attempts

        Returns:
            SimulationResult with all pipeline information

        Raises:
            BlenderAIError: If generation fails after all retries
        """
        # Create session ID for tracking
        session_id = str(uuid.uuid4())[:8]
        pipeline_logger = PipelineLogger(session_id)

        self.logger.info(
            f"Starting simulation generation",
            session_id=session_id,
            prompt=user_prompt
        )

        # Generate output path if not provided
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(self.output_dir / f"simulation_{timestamp}.blend")

        # Initialize result object
        result = SimulationResult(
            success=False,
            plan=None,
            total_time_seconds=0.0,
            agent_times={},
            created_at=datetime.now()
        )

        try:
            # ===== STEP 1: Planning =====
            self._report_progress(progress_callback, "Planning simulation...", 0.10)
            pipeline_logger.log_agent_start("PlannerAgent")

            plan = self.planner.run(user_prompt)
            result.plan = plan

            pipeline_logger.log_agent_complete("PlannerAgent", True)
            result.agent_times["planner"] = self.planner.get_stats()["average_time"]

            # ===== STEP 2: Physics Validation =====
            self._report_progress(progress_callback, "Validating physics...", 0.25)
            pipeline_logger.log_agent_start("PhysicsValidatorAgent")

            enriched_plan = self.physics_validator.run(plan)
            result.plan = enriched_plan

            pipeline_logger.log_agent_complete("PhysicsValidatorAgent", True)
            result.agent_times["physics_validator"] = self.physics_validator.get_stats()["average_time"]

            # ===== STEP 3: Code Generation =====
            self._report_progress(progress_callback, "Generating code...", 0.40)
            pipeline_logger.log_agent_start("CodeGeneratorAgent")

            code = self.code_generator.run(enriched_plan, output_path)

            pipeline_logger.log_agent_complete("CodeGeneratorAgent", True)
            result.agent_times["code_generator"] = self.code_generator.get_stats()["average_time"]

            # ===== STEP 4: Syntax Validation =====
            self._report_progress(progress_callback, "Validating syntax...", 0.55)
            pipeline_logger.log_agent_start("SyntaxValidatorAgent")

            validation = self.syntax_validator.run(code)

            if not validation.is_valid:
                # Try to auto-fix
                self.logger.warning("Syntax validation failed, attempting auto-fix...")
                code, validation = self.syntax_validator.validate_and_fix(code)

                if not validation.is_valid:
                    raise ValidationError(
                        f"Code validation failed: {', '.join(validation.errors)}",
                        validation_type="syntax",
                        details={"errors": validation.errors}
                    )

            pipeline_logger.log_agent_complete("SyntaxValidatorAgent", True)
            result.agent_times["syntax_validator"] = self.syntax_validator.get_stats()["average_time"]

            # ===== STEP 5: Execution =====
            self._report_progress(progress_callback, "Executing in Blender...", 0.70)
            pipeline_logger.log_agent_start("ExecutorAgent")

            execution_result = self.executor.run(code, output_path)

            if not execution_result.success:
                raise ExecutionError(
                    "Blender execution failed",
                    blender_output=execution_result.stderr
                )

            result.blend_file = execution_result.blend_file_path

            pipeline_logger.log_agent_complete("ExecutorAgent", True)
            result.agent_times["executor"] = self.executor.get_stats()["average_time"]

            # ===== STEP 6: Quality Validation =====
            self._report_progress(progress_callback, "Validating quality...", 0.90)
            pipeline_logger.log_agent_start("QualityValidatorAgent")

            quality_metrics = self.quality_validator.run(execution_result, enriched_plan)
            result.quality_metrics = quality_metrics

            pipeline_logger.log_agent_complete("QualityValidatorAgent", True)
            result.agent_times["quality_validator"] = self.quality_validator.get_stats()["average_time"]

            # ===== OPTIONAL: Refinement Loop =====
            if enable_refinement and quality_metrics.quality_score < 0.9:
                self.logger.info(f"Quality score {quality_metrics.quality_score:.2f}, attempting refinement...")

                should_refine, reason = self.refinement.should_refine(quality_metrics, threshold=0.8)

                if should_refine:
                    self.logger.info(f"Refinement needed: {reason}")

                    for iteration in range(1, max_refinement_iterations + 1):
                        self._report_progress(
                            progress_callback,
                            f"Refining simulation (attempt {iteration})...",
                            0.95
                        )

                        try:
                            # Get refined plan
                            refined_plan = self.refinement.run(
                                original_plan=enriched_plan,
                                quality_metrics=quality_metrics,
                                iteration=iteration
                            )

                            # Regenerate with refined plan
                            self.logger.info(f"Regenerating with refined plan (iteration {iteration})")

                            # Re-run code generation through quality validation
                            refined_code = self.code_generator.run(refined_plan, output_path)
                            refined_validation = self.syntax_validator.run(refined_code)

                            if not refined_validation.is_valid:
                                self.logger.warning("Refined code validation failed, using original")
                                break

                            refined_execution = self.executor.run(refined_code, output_path)

                            if not refined_execution.success:
                                self.logger.warning("Refined execution failed, using original")
                                break

                            refined_quality = self.quality_validator.run(refined_execution, refined_plan)

                            # Check if quality improved
                            if refined_quality.quality_score > quality_metrics.quality_score:
                                self.logger.info(
                                    f"Refinement successful! Quality improved: "
                                    f"{quality_metrics.quality_score:.2f} → {refined_quality.quality_score:.2f}"
                                )

                                # Update result with refined version
                                result.blend_file = refined_execution.blend_file_path
                                result.quality_metrics = refined_quality
                                result.refinement_count = iteration

                                enriched_plan = refined_plan
                                quality_metrics = refined_quality

                                # Stop if quality is now good enough
                                if refined_quality.quality_score >= 0.9:
                                    break
                            else:
                                self.logger.info(
                                    f"Refinement didn't improve quality: "
                                    f"{quality_metrics.quality_score:.2f} vs {refined_quality.quality_score:.2f}"
                                )
                                break

                        except Exception as e:
                            self.logger.warning(f"Refinement iteration {iteration} failed: {str(e)}")
                            result.warnings.append(f"Refinement attempt {iteration} failed")
                            break

                    # Log refinement stats
                    if result.refinement_count > 0:
                        original_quality = execution_result.blend_file_path  # This was the first attempt
                        final_quality = result.quality_metrics.quality_score if result.quality_metrics else 0
                        # Note: We don't have original quality stored, skip detailed stats for now
                        self.logger.info(
                            f"Refinement completed after {result.refinement_count} iterations",
                            final_quality=final_quality
                        )
                else:
                    self.logger.info(f"Refinement not needed: {reason}")

            # ===== SUCCESS =====
            result.success = True
            self._report_progress(progress_callback, "Complete!", 1.0)

            # Calculate total time
            result.total_time_seconds = sum(result.agent_times.values())

            pipeline_logger.log_pipeline_complete(
                True,
                quality_score=quality_metrics.quality_score
            )

            self.logger.info(
                "Simulation generation successful",
                session_id=session_id,
                output=output_path,
                quality=quality_metrics.quality_score,
                total_time=result.total_time_seconds
            )

            return result

        except BlenderAIError as e:
            # Handle known errors
            self.logger.error("pipeline_execution", e)

            result.errors.append(str(e))

            # Attempt retry if enabled
            if self.enable_auto_retry and e.recoverable:
                self.logger.info("Attempting retry...")
                result.warnings.append(f"Retried due to: {str(e)}")
                # TODO: Implement retry logic in Phase 3

            pipeline_logger.log_pipeline_complete(
                False,
                error=str(e)
            )

            return result

        except Exception as e:
            # Unexpected error
            self.logger.error("unexpected_error", e)
            result.errors.append(f"Unexpected error: {str(e)}")

            pipeline_logger.log_pipeline_complete(False, error=str(e))

            return result

    def _report_progress(
        self,
        callback: Optional[Callable[[str, float], None]],
        message: str,
        progress: float
    ) -> None:
        """Report progress to callback if provided."""
        if callback:
            try:
                callback(message, progress)
            except Exception as e:
                self.logger.warning(f"Progress callback failed: {str(e)}")

    def get_pipeline_stats(self) -> dict:
        """
        Get statistics for all agents.

        Returns:
            Dictionary with stats for each agent
        """
        return {
            "planner": self.planner.get_stats(),
            "physics_validator": self.physics_validator.get_stats(),
            "code_generator": self.code_generator.get_stats(),
            "syntax_validator": self.syntax_validator.get_stats(),
            "executor": self.executor.get_stats(),
            "quality_validator": self.quality_validator.get_stats(),
        }

    def check_system_ready(self) -> tuple[bool, list[str]]:
        """
        Check if the system is ready to generate simulations.

        Returns:
            Tuple of (is_ready, list_of_issues)
        """
        issues = []

        # Check Claude API
        if not self.claude.api_key:
            issues.append("Claude API key not configured")

        # Check Blender
        blender_available, blender_msg = self.executor.check_blender_available()
        if not blender_available:
            issues.append(f"Blender not available: {blender_msg}")

        # Check output directory
        if not self.output_dir.exists():
            try:
                self.output_dir.mkdir(parents=True)
            except Exception as e:
                issues.append(f"Cannot create output directory: {str(e)}")

        # Check materials database
        if not self.config.materials:
            issues.append("Materials database not loaded")

        is_ready = len(issues) == 0

        return is_ready, issues

    def list_available_materials(self) -> dict:
        """
        Get list of available materials.

        Returns:
            Dictionary with material categories
        """
        return self.physics_validator.list_available_materials()

    def estimate_generation_time(self, user_prompt: str) -> int:
        """
        Estimate how long generation will take.

        Args:
            user_prompt: User's simulation request

        Returns:
            Estimated seconds

        Note:
            This is a rough estimate. Actual time can vary significantly.
        """
        try:
            # Quick plan to estimate
            plan = self.planner.run(user_prompt)
            enriched_plan = self.physics_validator.run(plan)
            code = self.code_generator.run(enriched_plan, "/tmp/test.blend")

            # Estimate execution time
            exec_time = self.executor.estimate_execution_time(code)

            # Add overhead for other agents (planning, validation, etc.)
            total_time = exec_time + 30

            return total_time

        except Exception:
            # Fallback estimate
            return 60  # 1 minute default
