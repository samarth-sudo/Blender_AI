"""
Refinement Agent - Optional agent for quality improvement.

Responsibility: Improve simulation quality based on quality metrics feedback.

This agent analyzes quality issues and suggests improvements to the plan,
then regenerates the simulation with refined parameters.
"""

from typing import Optional, List, Tuple
from copy import deepcopy

from src.agents.base_agent import BaseAgent
from src.llm import ClaudeClient, Tool
from src.models.schemas import (
    SimulationPlan,
    QualityMetrics,
    SimulationType,
)
from src.utils.errors import ValidationError


class RefinementAgent(BaseAgent):
    """
    Refinement Agent: Improve simulation quality iteratively.

    This agent:
    1. Analyzes quality metrics and issues
    2. Identifies specific problems
    3. Suggests targeted improvements
    4. Modifies the simulation plan
    5. Can be called multiple times for iterative improvement

    Example:
        refiner = RefinementAgent()
        improved_plan = refiner.run(
            original_plan=plan,
            quality_metrics=metrics,
            iteration=1
        )
    """

    def __init__(self, claude_client: Optional[ClaudeClient] = None):
        """
        Initialize Refinement Agent.

        Args:
            claude_client: Optional Claude client
        """
        super().__init__("RefinementAgent")
        self.claude = claude_client or ClaudeClient()

        # Define refinement tool for structured suggestions
        self.refinement_tool = self._create_refinement_tool()

    def _create_refinement_tool(self) -> Tool:
        """
        Create tool definition for refinement suggestions.

        Returns:
            Tool object with schema
        """
        return Tool(
            name="suggest_refinements",
            description="Analyze quality issues and suggest specific improvements to simulation plan",
            input_schema={
                "type": "object",
                "properties": {
                    "identified_issues": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of specific issues found"
                    },
                    "suggested_changes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "parameter": {
                                    "type": "string",
                                    "description": "Which parameter to change (e.g., 'gravity', 'duration_frames', 'object_scale')"
                                },
                                "current_value": {
                                    "type": "string",
                                    "description": "Current value of the parameter"
                                },
                                "new_value": {
                                    "type": "string",
                                    "description": "Suggested new value"
                                },
                                "reasoning": {
                                    "type": "string",
                                    "description": "Why this change would improve quality"
                                }
                            },
                            "required": ["parameter", "new_value", "reasoning"]
                        }
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["critical", "high", "medium", "low"],
                        "description": "Priority of these refinements"
                    }
                },
                "required": ["identified_issues", "suggested_changes"]
            }
        )

    def execute(
        self,
        original_plan: SimulationPlan,
        quality_metrics: QualityMetrics,
        iteration: int = 1
    ) -> SimulationPlan:
        """
        Refine simulation plan based on quality issues.

        Args:
            original_plan: The original simulation plan
            quality_metrics: Quality metrics from validation
            iteration: Which refinement iteration this is

        Returns:
            Refined SimulationPlan

        Raises:
            ValidationError: If refinement fails
        """
        self.logger.info(
            f"Refining simulation (iteration {iteration})",
            current_quality=quality_metrics.quality_score,
            issues=len(quality_metrics.issues)
        )

        # Build refinement prompt
        prompt = self._build_refinement_prompt(original_plan, quality_metrics)

        try:
            # Get refinement suggestions from Claude
            result = self.claude.call_tool(
                prompt=prompt,
                tool=self.refinement_tool,
                system=self._get_system_prompt(),
                require_tool_use=True
            )

            suggestions = result.tool_input

            # Apply suggestions to plan
            refined_plan = self._apply_suggestions(original_plan, suggestions, quality_metrics)

            self.logger.success(
                "execute",
                changes_applied=len(suggestions.get("suggested_changes", [])),
                iteration=iteration
            )

            return refined_plan

        except Exception as e:
            raise ValidationError(
                f"Refinement failed: {str(e)}",
                validation_type="refinement"
            )

    def _build_refinement_prompt(
        self,
        plan: SimulationPlan,
        metrics: QualityMetrics
    ) -> str:
        """
        Build prompt for refinement analysis.

        Args:
            plan: Current simulation plan
            metrics: Quality metrics

        Returns:
            Prompt string
        """
        issues_text = "\n".join(f"- {issue}" for issue in metrics.issues) if metrics.issues else "None"

        prompt = f"""Analyze this simulation and suggest improvements:

**Current Simulation Plan:**
- Type: {plan.simulation_type.value}
- Objects: {len(plan.objects)} types
- Duration: {plan.duration_frames} frames
- Physics: gravity={plan.physics_settings.gravity}, substeps={plan.physics_settings.substeps_per_frame}

**Quality Issues Found:**
{issues_text}

**Quality Metrics:**
- Overall Score: {metrics.quality_score:.2f}/1.0
- Object Count Correct: {'✓' if metrics.object_count_correct else '✗'}
- Physics Setup: {'✓' if metrics.has_physics_setup else '✗'}
- Camera: {'✓' if metrics.has_camera else '✗'}
- Lighting: {'✓' if metrics.has_lighting else '✗'}

**Your Task:**
1. Identify the root causes of the quality issues
2. Suggest specific, actionable changes to improve the simulation
3. Focus on the most impactful improvements first

Consider:
- Are physics parameters realistic?
- Is the duration long enough for the action?
- Do object scales make sense?
- Are there missing elements (camera, lighting, ground plane)?
- Could simulation settings be more accurate (more substeps, higher resolution)?
"""

        return prompt

    def _get_system_prompt(self) -> str:
        """Get system prompt for refinement."""
        return """You are an expert in physics simulation and 3D animation.

Your goal is to analyze quality issues in Blender simulations and suggest precise improvements.

Guidelines:
- Be specific: "Increase duration from 100 to 250 frames" not "make it longer"
- Explain reasoning: Why will this change improve quality?
- Prioritize: Fix critical issues first (missing physics, camera, lighting)
- Be realistic: Don't suggest impossible values
- Consider simulation type: Rigid body needs different settings than fluids

Common issues and fixes:
- "No physics setup" → Ensure rigid_body_world or fluid domain is configured
- "Object count mismatch" → Check if ground plane is missing
- "No camera" → Add camera with appropriate framing
- "No lighting" → Add sun or point light with sufficient energy
- "Frame range too short" → Increase duration for action to complete
- "Physics unstable" → Increase substeps, reduce time scale, or adjust masses
"""

    def _apply_suggestions(
        self,
        original_plan: SimulationPlan,
        suggestions: dict,
        metrics: QualityMetrics
    ) -> SimulationPlan:
        """
        Apply refinement suggestions to plan.

        Args:
            original_plan: Original plan
            suggestions: Suggestions from Claude
            metrics: Quality metrics

        Returns:
            Refined plan
        """
        # Deep copy to avoid modifying original
        refined_plan = deepcopy(original_plan)

        suggested_changes = suggestions.get("suggested_changes", [])

        for change in suggested_changes:
            parameter = change.get("parameter", "")
            new_value = change.get("new_value", "")
            reasoning = change.get("reasoning", "")

            self.logger.info(
                f"Applying change: {parameter} = {new_value}",
                reasoning=reasoning
            )

            try:
                self._apply_single_change(refined_plan, parameter, new_value)
            except Exception as e:
                self.logger.warning(f"Failed to apply change to {parameter}: {str(e)}")

        # Handle common missing elements
        if not metrics.has_camera:
            self.logger.info("Adding default camera (was missing)")
            # Camera settings are already in plan, just ensure they're set
            # The plan already has CameraSettings with defaults

        if not metrics.has_lighting:
            self.logger.info("Adding default lighting (was missing)")
            # Lighting settings are already in plan with defaults

        return refined_plan

    def _apply_single_change(
        self,
        plan: SimulationPlan,
        parameter: str,
        new_value: str
    ) -> None:
        """
        Apply a single parameter change to plan.

        Args:
            plan: Plan to modify (in place)
            parameter: Parameter name
            new_value: New value (as string, will be converted)
        """
        param_lower = parameter.lower().replace(" ", "_")

        # Physics settings
        if "gravity" in param_lower:
            plan.physics_settings.gravity = float(new_value)

        elif "substep" in param_lower:
            plan.physics_settings.substeps_per_frame = int(new_value)

        elif "solver" in param_lower or "iteration" in param_lower:
            plan.physics_settings.solver_iterations = int(new_value)

        elif "resolution" in param_lower:
            plan.physics_settings.resolution_max = int(new_value)

        # Duration
        elif "duration" in param_lower or "frame" in param_lower:
            plan.duration_frames = int(new_value)

        # Time scale
        elif "time" in param_lower and "scale" in param_lower:
            plan.physics_settings.time_scale = float(new_value)

        # Object changes (more complex)
        elif "scale" in param_lower:
            # Scale all objects
            for obj in plan.objects:
                obj.scale = float(new_value)

        else:
            self.logger.warning(f"Unknown parameter: {parameter}")

    def should_refine(self, quality_metrics: QualityMetrics, threshold: float = 0.8) -> Tuple[bool, str]:
        """
        Determine if refinement is needed.

        Args:
            quality_metrics: Quality metrics
            threshold: Minimum acceptable quality (default 0.8)

        Returns:
            Tuple of (should_refine, reason)
        """
        if quality_metrics.quality_score >= threshold:
            return False, "Quality already meets threshold"

        if not quality_metrics.has_physics_setup:
            return True, "Critical: Missing physics setup"

        if not quality_metrics.has_camera:
            return True, "Critical: Missing camera"

        if not quality_metrics.has_lighting:
            return True, "Important: Missing lighting"

        if not quality_metrics.object_count_correct:
            return True, "Important: Object count mismatch"

        if quality_metrics.issues:
            return True, f"{len(quality_metrics.issues)} issues found"

        return True, "Quality below threshold"

    def get_refinement_stats(self, original_quality: float, refined_quality: float) -> dict:
        """
        Calculate refinement statistics.

        Args:
            original_quality: Quality before refinement
            refined_quality: Quality after refinement

        Returns:
            Dictionary with statistics
        """
        improvement = refined_quality - original_quality
        improvement_pct = (improvement / original_quality * 100) if original_quality > 0 else 0

        return {
            "original_quality": round(original_quality, 3),
            "refined_quality": round(refined_quality, 3),
            "improvement": round(improvement, 3),
            "improvement_percent": round(improvement_pct, 1),
            "was_successful": refined_quality > original_quality
        }
