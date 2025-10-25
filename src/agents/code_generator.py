"""
Code Generator Agent - Third agent in the pipeline.

Responsibility: Generate production-ready Blender Python code from SimulationPlan.

This agent combines:
1. Pre-built templates (for reliability)
2. Claude AI (for flexibility and adaptation)
3. Parameter injection (for customization)

The hybrid approach achieves higher success rates than pure code generation.
"""

import json
from typing import Optional

from src.agents.base_agent import BaseAgent
from src.llm import ClaudeClient
from src.models.schemas import SimulationPlan, SimulationType, BlenderCode
from src.templates import (
    get_rigid_body_template,
    get_fluid_smoke_template,
    get_fluid_liquid_template,
    get_cloth_template,
)
from src.utils.errors import ValidationError


class CodeGeneratorAgent(BaseAgent):
    """
    Code Generator Agent: Generate Blender Python code from plan.

    Strategy:
    1. Select appropriate template based on simulation type
    2. Convert plan to parameters dictionary
    3. Use Claude to customize code if needed
    4. Inject parameters into template

    This hybrid approach (templates + AI) is more reliable than pure generation.

    Example:
        generator = CodeGeneratorAgent()
        code = generator.run(plan, output_path="/tmp/sim.blend")
        # Returns BlenderCode with executable Python
    """

    def __init__(self, claude_client: Optional[ClaudeClient] = None, use_templates: bool = True):
        """
        Initialize Code Generator Agent.

        Args:
            claude_client: Optional Claude client
            use_templates: If True, use templates (recommended). If False, generate from scratch.
        """
        super().__init__("CodeGeneratorAgent")
        self.claude = claude_client or ClaudeClient()
        self.use_templates = use_templates

        # Template mapping
        self.templates = {
            SimulationType.RIGID_BODY: get_rigid_body_template,
            SimulationType.FLUID_SMOKE: get_fluid_smoke_template,
            SimulationType.FLUID_FIRE: get_fluid_smoke_template,  # Same as smoke
            SimulationType.FLUID_LIQUID: get_fluid_liquid_template,
            SimulationType.CLOTH: get_cloth_template,
        }

    def execute(self, plan: SimulationPlan, output_path: str = "/tmp/simulation.blend") -> BlenderCode:
        """
        Generate Blender Python code from simulation plan.

        Args:
            plan: Enriched plan from PhysicsValidatorAgent
            output_path: Where to save the .blend file

        Returns:
            BlenderCode object with executable code

        Raises:
            ValidationError: If code generation fails
        """
        self.logger.info(
            f"Generating code for {plan.simulation_type.value} simulation",
            objects=len(plan.objects),
            frames=plan.duration_frames
        )

        try:
            if self.use_templates:
                code = self._generate_from_template(plan, output_path)
            else:
                code = self._generate_from_scratch(plan, output_path)

            # Calculate complexity score
            complexity = self._calculate_complexity(plan)

            blender_code = BlenderCode(
                code=code,
                template_used=plan.simulation_type.value if self.use_templates else None,
                complexity_score=complexity,
                estimated_execution_time=self._estimate_execution_time(plan)
            )

            self.logger.success(
                "execute",
                code_length=len(code),
                complexity=complexity
            )

            return blender_code

        except Exception as e:
            raise ValidationError(
                f"Code generation failed: {str(e)}",
                validation_type="code_generation"
            )

    def _generate_from_template(self, plan: SimulationPlan, output_path: str) -> str:
        """
        Generate code using pre-built templates.

        This is the recommended approach for reliability.

        Args:
            plan: Simulation plan
            output_path: Output file path

        Returns:
            Python code string
        """
        # Get template for simulation type
        template_func = self.templates.get(plan.simulation_type)
        if not template_func:
            raise ValidationError(
                f"No template for simulation type: {plan.simulation_type.value}",
                validation_type="template_selection"
            )

        # Get base template code
        template_code = template_func()

        # Convert plan to parameters
        params = self._plan_to_parameters(plan, output_path)

        # Create main execution block
        main_code = self._create_main_execution(plan, params)

        # Combine template + main execution
        full_code = f"{template_code}\n\n{main_code}"

        return full_code

    def _generate_from_scratch(self, plan: SimulationPlan, output_path: str) -> str:
        """
        Generate code from scratch using Claude (less reliable but more flexible).

        Args:
            plan: Simulation plan
            output_path: Output file path

        Returns:
            Python code string
        """
        system_prompt = """You are an expert Blender Python developer.
Generate complete, production-ready Blender Python scripts.

Requirements:
1. Import bpy and necessary modules
2. Clear the default scene
3. Create all objects with exact specifications
4. Apply physics with all parameters
5. Set up camera and lighting
6. Bake the simulation
7. Save the .blend file

Code must be:
- Error-free and executable
- Well-commented
- Following Blender API best practices
- Complete (no placeholders or TODOs)"""

        user_prompt = f"""Generate a complete Blender Python script for this simulation:

Simulation Type: {plan.simulation_type.value}
Objects: {json.dumps([obj.dict() for obj in plan.objects], indent=2)}
Physics: {plan.physics_settings.dict()}
Duration: {plan.duration_frames} frames
Output: {output_path}

Generate ONLY the Python code, no explanations."""

        code = self.claude.complete(
            prompt=user_prompt,
            system=system_prompt,
            max_tokens=self.config.agents.get("code_generator", {}).get("max_tokens", 4000),
            temperature=0.2
        )

        # Extract code if wrapped in markdown
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0].strip()
        elif "```" in code:
            code = code.split("```")[1].split("```")[0].strip()

        return code

    def _plan_to_parameters(self, plan: SimulationPlan, output_path: str) -> dict:
        """
        Convert SimulationPlan to parameters dictionary for template.

        Args:
            plan: Simulation plan
            output_path: Output file path

        Returns:
            Dictionary of parameters
        """
        # Convert objects to dict format
        objects_data = []
        for obj in plan.objects:
            obj_dict = {
                "name": obj.name,
                "object_type": obj.object_type.value,
                "count": obj.count,
                "scale": obj.scale,
                "material": obj.material,
                "is_static": obj.is_static,
                "is_emitter": not obj.is_static,  # For fluid/smoke
            }

            # Add physics properties if present
            if obj.physics_properties:
                obj_dict["physics_properties"] = {
                    "density": obj.physics_properties.density,
                    "friction": obj.physics_properties.friction,
                    "restitution": obj.physics_properties.restitution,
                    "linear_damping": obj.physics_properties.linear_damping,
                    "angular_damping": obj.physics_properties.angular_damping,
                    "collision_shape": obj.physics_properties.collision_shape,
                    "collision_margin": obj.physics_properties.collision_margin,
                }

                # For cloth simulations
                if plan.simulation_type == SimulationType.CLOTH:
                    obj_dict["physics_properties"]["mass_per_m2"] = 0.3
                    obj_dict["is_cloth"] = not obj.is_static

                # For fluid simulations
                if plan.simulation_type in [SimulationType.FLUID_SMOKE, SimulationType.FLUID_FIRE]:
                    obj_dict["flow_type"] = "FIRE" if plan.simulation_type == SimulationType.FLUID_FIRE else "SMOKE"
                    obj_dict["density"] = 1.5
                    obj_dict["temperature"] = 2.0
                    obj_dict["velocity"] = 0.5

            # Set position if specified
            if obj.position:
                obj_dict["position"] = obj.position

            # Assign color based on material (simple mapping)
            obj_dict["color"] = self._material_to_color(obj.material)

            objects_data.append(obj_dict)

        # Build parameters dictionary
        params = {
            "duration_frames": plan.duration_frames,
            "frame_rate": plan.frame_rate,
            "physics_settings": {
                "gravity": plan.physics_settings.gravity,
                "substeps_per_frame": plan.physics_settings.substeps_per_frame,
                "solver_iterations": plan.physics_settings.solver_iterations,
                "time_scale": plan.physics_settings.time_scale,
            },
            "camera_settings": {
                "location": plan.camera_settings.location,
                "rotation": plan.camera_settings.rotation,
                "focal_length": plan.camera_settings.focal_length,
            },
            "lighting_settings": {
                "type": plan.lighting_settings.type,
                "energy": plan.lighting_settings.energy,
                "location": plan.lighting_settings.location,
                "rotation": plan.lighting_settings.rotation,
            },
            "objects": objects_data,
            "output_path": output_path,
        }

        # Add simulation-specific settings
        if plan.physics_settings.resolution_max:
            params["physics_settings"]["resolution_max"] = plan.physics_settings.resolution_max

        if plan.physics_settings.quality_steps:
            params["physics_settings"]["quality_steps"] = plan.physics_settings.quality_steps

        return params

    def _create_main_execution(self, plan: SimulationPlan, params: dict) -> str:
        """
        Create the main execution code that calls the template functions.

        Args:
            plan: Simulation plan
            params: Parameters dictionary

        Returns:
            Python code string
        """
        # Determine main function name based on simulation type
        func_name_map = {
            SimulationType.RIGID_BODY: "create_rigid_body_simulation",
            SimulationType.FLUID_SMOKE: "create_fluid_smoke_simulation",
            SimulationType.FLUID_FIRE: "create_fluid_smoke_simulation",
            SimulationType.FLUID_LIQUID: "create_fluid_liquid_simulation",
            SimulationType.CLOTH: "create_cloth_simulation",
        }

        func_name = func_name_map.get(plan.simulation_type, "create_simulation")

        # Format parameters as Python dict (use pprint for proper Python syntax, not JSON)
        import pprint
        params_str = pprint.pformat(params, indent=4, width=80)

        main_code = f'''
# Main execution
if __name__ == "__main__":
    # Simulation parameters
    params = {params_str}

    # Run simulation
    {func_name}(params)

    print("\\n" + "="*50)
    print("SIMULATION COMPLETE!")
    print("="*50)
    print(f"Output: {{params['output_path']}}")
    print(f"Frames: {{params['duration_frames']}}")
    print(f"Objects: {{len(params['objects'])}}")
'''

        return main_code

    def _material_to_color(self, material: str) -> tuple:
        """Map material name to approximate RGB color."""
        material = material.lower()

        color_map = {
            "wood": (0.6, 0.4, 0.2, 1.0),
            "metal": (0.7, 0.7, 0.7, 1.0),
            "steel": (0.5, 0.5, 0.6, 1.0),
            "aluminum": (0.8, 0.8, 0.8, 1.0),
            "copper": (0.9, 0.5, 0.3, 1.0),
            "gold": (1.0, 0.8, 0.2, 1.0),
            "glass": (0.9, 0.9, 1.0, 1.0),
            "rubber": (0.2, 0.2, 0.2, 1.0),
            "plastic": (0.7, 0.3, 0.3, 1.0),
            "stone": (0.5, 0.5, 0.5, 1.0),
            "concrete": (0.6, 0.6, 0.6, 1.0),
            "fabric": (0.8, 0.2, 0.2, 1.0),
            "cloth": (0.7, 0.3, 0.5, 1.0),
        }

        # Find best match
        for key, color in color_map.items():
            if key in material:
                return color

        # Default gray
        return (0.7, 0.7, 0.7, 1.0)

    def _calculate_complexity(self, plan: SimulationPlan) -> float:
        """
        Calculate complexity score (0-1) based on plan.

        Higher complexity = longer execution time and more chance of failure.

        Args:
            plan: Simulation plan

        Returns:
            Complexity score 0-1
        """
        score = 0.0

        # Base complexity by simulation type
        type_complexity = {
            SimulationType.RIGID_BODY: 0.2,
            SimulationType.CLOTH: 0.4,
            SimulationType.FLUID_SMOKE: 0.5,
            SimulationType.FLUID_FIRE: 0.6,
            SimulationType.FLUID_LIQUID: 0.7,
        }
        score += type_complexity.get(plan.simulation_type, 0.3)

        # Object count
        total_objects = sum(obj.count for obj in plan.objects)
        if total_objects > 100:
            score += 0.2
        elif total_objects > 50:
            score += 0.1

        # Frame count
        if plan.duration_frames > 300:
            score += 0.1

        # Fluid resolution
        if plan.physics_settings.resolution_max and plan.physics_settings.resolution_max > 200:
            score += 0.2

        return min(score, 1.0)

    def _estimate_execution_time(self, plan: SimulationPlan) -> int:
        """
        Estimate execution time in seconds.

        This is a rough estimate for user expectations.

        Args:
            plan: Simulation plan

        Returns:
            Estimated seconds
        """
        base_time = 10  # Base overhead

        # Time per simulation type
        if plan.simulation_type == SimulationType.RIGID_BODY:
            base_time += plan.duration_frames * 0.1
        elif plan.simulation_type in [SimulationType.FLUID_SMOKE, SimulationType.FLUID_FIRE]:
            res = plan.physics_settings.resolution_max or 128
            base_time += plan.duration_frames * (res / 64) * 0.5
        elif plan.simulation_type == SimulationType.FLUID_LIQUID:
            res = plan.physics_settings.resolution_max or 128
            base_time += plan.duration_frames * (res / 32) * 1.0
        elif plan.simulation_type == SimulationType.CLOTH:
            base_time += plan.duration_frames * 0.2

        # Object count multiplier
        total_objects = sum(obj.count for obj in plan.objects)
        if total_objects > 100:
            base_time *= 1.5

        return int(base_time)
