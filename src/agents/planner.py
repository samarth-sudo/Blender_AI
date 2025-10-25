"""
Planner Agent - First agent in the pipeline.

Responsibility: Parse natural language user input into a structured SimulationPlan.

This agent uses Claude's tool calling to ensure reliable JSON parsing with
validation. The structured output achieves 95%+ reliability compared to
60-70% for freeform JSON parsing.
"""

from typing import Optional
from datetime import datetime

from src.agents.base_agent import BaseAgent
from src.llm import ClaudeClient, Tool
from src.models.schemas import (
    SimulationPlan,
    SimulationType,
    SimulationObject,
    ObjectType,
    PhysicsSettings,
    CameraSettings,
    LightingSettings,
)
from src.utils.errors import PlanningError


class PlannerAgent(BaseAgent):
    """
    Planner Agent: Parse natural language → structured simulation plan.

    This agent is critical because it converts ambiguous user input into
    precise parameters that downstream agents can use.

    Example:
        planner = PlannerAgent()
        plan = planner.run("Create 20 wooden blocks falling on a table")
        # Returns SimulationPlan with all parameters filled
    """

    def __init__(self, claude_client: Optional[ClaudeClient] = None):
        """
        Initialize Planner Agent.

        Args:
            claude_client: Optional Claude client (creates new one if not provided)
        """
        super().__init__("PlannerAgent")
        self.claude = claude_client or ClaudeClient()

        # Define tool schema for structured output
        self.planning_tool = self._create_planning_tool()

    def _create_planning_tool(self) -> Tool:
        """
        Create the tool definition for simulation planning.

        This JSON schema ensures Claude returns properly structured data.

        Returns:
            Tool object with complete schema
        """
        return Tool(
            name="create_simulation_plan",
            description="Parse user's simulation request into a structured plan with all necessary parameters",
            input_schema={
                "type": "object",
                "properties": {
                    "simulation_type": {
                        "type": "string",
                        "enum": ["rigid_body", "fluid_smoke", "fluid_fire", "fluid_liquid", "cloth", "soft_body"],
                        "description": "Type of physics simulation"
                    },
                    "objects": {
                        "type": "array",
                        "description": "List of objects in the simulation",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": "Object name (e.g., 'wooden_block', 'ground')"
                                },
                                "object_type": {
                                    "type": "string",
                                    "enum": ["cube", "sphere", "cylinder", "cone", "plane", "torus", "monkey"],
                                    "description": "Basic shape type"
                                },
                                "count": {
                                    "type": "integer",
                                    "minimum": 1,
                                    "maximum": 1000,
                                    "description": "Number of instances"
                                },
                                "material": {
                                    "type": "string",
                                    "description": "Material name (wood, metal, glass, etc.)"
                                },
                                "scale": {
                                    "type": "number",
                                    "minimum": 0.1,
                                    "maximum": 100,
                                    "description": "Object scale multiplier"
                                },
                                "is_static": {
                                    "type": "boolean",
                                    "description": "Is this a static/passive object (like ground)?"
                                }
                            },
                            "required": ["name", "object_type", "count", "material"]
                        }
                    },
                    "duration_frames": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 1000,
                        "description": "Animation length in frames (24 frames = 1 second at 24fps)"
                    },
                    "physics_settings": {
                        "type": "object",
                        "description": "Global physics parameters",
                        "properties": {
                            "gravity": {
                                "type": "number",
                                "description": "Gravity in m/s² (negative pulls down)"
                            },
                            "substeps_per_frame": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 20
                            },
                            "resolution_max": {
                                "type": "integer",
                                "minimum": 32,
                                "maximum": 512,
                                "description": "For fluid simulations only"
                            }
                        }
                    }
                },
                "required": ["simulation_type", "objects", "duration_frames"]
            }
        )

    def execute(self, user_prompt: str) -> SimulationPlan:
        """
        Parse user input into a structured simulation plan.

        Args:
            user_prompt: Natural language description (e.g., "20 cubes falling")

        Returns:
            SimulationPlan object with all parameters

        Raises:
            PlanningError: If parsing fails or input is invalid
        """
        self.logger.info(f"Parsing user prompt: '{user_prompt}'")

        # Build system prompt with context
        system_prompt = self._build_system_prompt()

        # Build user prompt with examples
        full_prompt = self._build_user_prompt(user_prompt)

        try:
            # Use Claude with tool calling for structured output
            result = self.claude.call_tool(
                prompt=full_prompt,
                tool=self.planning_tool,
                system=system_prompt,
                max_tokens=self.config.agents.get("planner", {}).get("max_tokens", 2000),
                require_tool_use=True
            )

            # Parse the tool output into our Pydantic model
            plan_data = result.tool_input

            # Convert to SimulationPlan
            plan = self._parse_tool_output(plan_data, user_prompt)

            self.logger.info(
                f"Plan created: {plan.simulation_type.value}, "
                f"{len(plan.objects)} object types, "
                f"{plan.duration_frames} frames"
            )

            return plan

        except Exception as e:
            raise PlanningError(
                f"Failed to parse simulation request: {str(e)}",
                user_input=user_prompt
            )

    def _build_system_prompt(self) -> str:
        """Build system prompt for the planner."""
        return """You are an expert in physics simulations and Blender 3D animation.

Your task is to parse user requests for simulations into structured plans.

Guidelines:
1. Identify the simulation type (rigid body, fluid smoke/fire/liquid, cloth)
2. Extract all objects mentioned (active objects and static ground/obstacles)
3. Infer reasonable defaults for unspecified parameters
4. For rigid body: default to 250 frames (10 seconds at 24fps)
5. For fluid: default to 150 frames (fluids need less time)
6. For cloth: default to 200 frames
7. Always include a ground plane for falling objects
8. Material names: use simple terms (wood, metal, stone, rubber, glass, plastic)

Common patterns:
- "X blocks falling" → rigid_body simulation with X cubes + ground plane
- "smoke rising" → fluid_smoke simulation with emitter sphere
- "flag waving" → cloth simulation with plane
- "water pouring" → fluid_liquid simulation with source

Be specific and precise in your output."""

    def _build_user_prompt(self, user_prompt: str) -> str:
        """Build user prompt with examples."""
        return f"""Parse this simulation request:

"{user_prompt}"

Examples of good plans:

Request: "20 wooden blocks falling on concrete floor"
→ rigid_body, 20 cubes (wood), 1 plane (concrete, static), 250 frames

Request: "Smoke rising from a sphere"
→ fluid_smoke, 1 sphere (emitter), domain, 150 frames

Request: "Red cloth draped over a sphere"
→ cloth, 1 plane (fabric), 1 sphere (static collision), 200 frames

Now parse the user's request above."""

    def _parse_tool_output(self, tool_data: dict, user_prompt: str) -> SimulationPlan:
        """
        Convert tool output dictionary to SimulationPlan object.

        Args:
            tool_data: Raw dictionary from Claude
            user_prompt: Original user prompt

        Returns:
            Validated SimulationPlan

        Raises:
            PlanningError: If data is invalid
        """
        try:
            # Parse simulation type
            sim_type = SimulationType(tool_data["simulation_type"])

            # Parse objects
            objects = []
            for obj_data in tool_data["objects"]:
                obj = SimulationObject(
                    name=obj_data["name"],
                    object_type=ObjectType(obj_data["object_type"]),
                    count=obj_data["count"],
                    material=obj_data.get("material", "default"),
                    scale=obj_data.get("scale", 1.0),
                    is_static=obj_data.get("is_static", False)
                )
                objects.append(obj)

            # Parse physics settings
            physics_data = tool_data.get("physics_settings", {})
            physics = PhysicsSettings(
                gravity=physics_data.get("gravity", -9.81),
                substeps_per_frame=physics_data.get("substeps_per_frame", 10),
                solver_iterations=physics_data.get("solver_iterations", 10),
                time_scale=physics_data.get("time_scale", 1.0),
                resolution_max=physics_data.get("resolution_max", 128) if sim_type in [
                    SimulationType.FLUID_SMOKE,
                    SimulationType.FLUID_FIRE,
                    SimulationType.FLUID_LIQUID
                ] else None
            )

            # Create plan
            plan = SimulationPlan(
                simulation_type=sim_type,
                objects=objects,
                physics_settings=physics,
                camera_settings=CameraSettings(),  # Use defaults
                lighting_settings=LightingSettings(),  # Use defaults
                duration_frames=tool_data["duration_frames"],
                frame_rate=24,  # Default
                user_prompt=user_prompt,
                created_at=datetime.now()
            )

            return plan

        except Exception as e:
            raise PlanningError(f"Invalid plan structure: {str(e)}")

    def validate_plan(self, plan: SimulationPlan) -> tuple[bool, list[str]]:
        """
        Validate a simulation plan for common issues.

        Args:
            plan: The plan to validate

        Returns:
            Tuple of (is_valid, list_of_warnings)
        """
        warnings = []

        # Check for at least one object
        if len(plan.objects) == 0:
            warnings.append("Plan has no objects")

        # Check for ground plane in falling simulations
        if plan.simulation_type == SimulationType.RIGID_BODY:
            has_ground = any(obj.is_static for obj in plan.objects)
            if not has_ground:
                warnings.append("Rigid body simulation should have a static ground plane")

        # Check frame count is reasonable
        if plan.duration_frames > 500:
            warnings.append(f"Long animation ({plan.duration_frames} frames) may take time to bake")

        # Check object counts
        total_objects = sum(obj.count for obj in plan.objects)
        if total_objects > 500:
            warnings.append(f"High object count ({total_objects}) may cause performance issues")

        # Check fluid resolution
        if plan.simulation_type in [SimulationType.FLUID_SMOKE, SimulationType.FLUID_FIRE, SimulationType.FLUID_LIQUID]:
            if plan.physics_settings.resolution_max and plan.physics_settings.resolution_max > 256:
                warnings.append(f"High fluid resolution ({plan.physics_settings.resolution_max}) will be slow to bake")

        is_valid = len(warnings) == 0

        return is_valid, warnings
