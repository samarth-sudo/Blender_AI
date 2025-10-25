"""
Physics Validator Agent - Second agent in the pipeline.

Responsibility: Enrich SimulationPlan with realistic material properties.

This agent takes the structured plan from PlannerAgent and adds detailed
physics properties (mass, friction, restitution, damping) based on our
comprehensive materials database.
"""

from typing import Dict, Any
from copy import deepcopy

from src.agents.base_agent import BaseAgent
from src.models.schemas import (
    SimulationPlan,
    SimulationType,
    MaterialProperties,
    ValidationResult,
)
from src.utils.errors import PhysicsError, ValidationError


class PhysicsValidatorAgent(BaseAgent):
    """
    Physics Validator Agent: Enrich plan with realistic material properties.

    This agent ensures physical realism by:
    1. Looking up material properties in database
    2. Validating physics parameters
    3. Applying fallbacks for unknown materials
    4. Adjusting parameters based on simulation type

    Example:
        validator = PhysicsValidatorAgent()
        enriched_plan = validator.run(plan)
        # All objects now have physics_properties filled
    """

    def __init__(self):
        """Initialize Physics Validator Agent."""
        super().__init__("PhysicsValidatorAgent")

        # Cache materials database
        self.materials = self.config.materials
        self.fluids = self.config.fluids
        self.default_material = self.config.default_material

    def execute(self, plan: SimulationPlan) -> SimulationPlan:
        """
        Enrich simulation plan with physics properties.

        Args:
            plan: Plan from PlannerAgent

        Returns:
            Enriched plan with all physics_properties filled

        Raises:
            ValidationError: If physics validation fails
        """
        self.logger.info(f"Validating physics for {len(plan.objects)} objects")

        # Create a deep copy to avoid modifying the original
        enriched_plan = deepcopy(plan)

        # Enrich each object with material properties
        for obj in enriched_plan.objects:
            material_name = obj.material.lower().replace(" ", "_")

            # Look up material properties
            material_props = self._get_material_properties(material_name)

            # Create MaterialProperties object
            obj.physics_properties = MaterialProperties(**material_props)

            self.logger.debug(
                f"Applied material '{material_props['name']}' to {obj.name}",
                density=material_props['density'],
                friction=material_props['friction']
            )

        # Validate physics settings for simulation type
        self._validate_physics_settings(enriched_plan)

        # Adjust parameters based on simulation type
        self._adjust_for_simulation_type(enriched_plan)

        self.logger.success(
            "execute",
            objects_enriched=len(enriched_plan.objects)
        )

        return enriched_plan

    def _get_material_properties(self, material_name: str) -> Dict[str, Any]:
        """
        Look up material properties in database.

        Args:
            material_name: Material name (e.g., "wood_pine", "metal_steel")

        Returns:
            Dictionary of material properties
        """
        # Direct match
        if material_name in self.materials:
            return self.materials[material_name]

        # Try fuzzy matching
        # "wood" → matches "wood_pine"
        # "metal" → matches "metal_steel"
        for key in self.materials:
            if material_name in key or key in material_name:
                self.logger.info(f"Fuzzy matched '{material_name}' to '{key}'")
                return self.materials[key]

        # No match - use default and warn
        self.logger.warning(
            f"Unknown material '{material_name}', using default",
            fallback=self.default_material['name']
        )

        return self.default_material

    def _validate_physics_settings(self, plan: SimulationPlan) -> None:
        """
        Validate physics settings for the simulation type.

        Args:
            plan: The plan to validate

        Raises:
            PhysicsError: If settings are invalid
        """
        physics = plan.physics_settings
        sim_type = plan.simulation_type

        # Validate gravity
        if physics.gravity > 0:
            raise PhysicsError(
                "Gravity should be negative (pulls downward)",
                invalid_params={"gravity": physics.gravity}
            )

        if abs(physics.gravity) > 50:
            self.logger.warning(
                f"Very high gravity ({physics.gravity} m/s²) may cause instability"
            )

        # Validate rigid body settings
        if sim_type == SimulationType.RIGID_BODY:
            if physics.substeps_per_frame < 5:
                self.logger.warning(
                    f"Low substeps ({physics.substeps_per_frame}) may cause instability"
                )

            if physics.solver_iterations < 5:
                self.logger.warning(
                    f"Low solver iterations ({physics.solver_iterations}) may cause instability"
                )

        # Validate fluid settings
        if sim_type in [SimulationType.FLUID_SMOKE, SimulationType.FLUID_FIRE, SimulationType.FLUID_LIQUID]:
            if not physics.resolution_max:
                # Set default if not specified
                physics.resolution_max = 128
                self.logger.info("Set default fluid resolution to 128")

            if physics.resolution_max < 32:
                raise PhysicsError(
                    "Fluid resolution too low (minimum 32)",
                    invalid_params={"resolution_max": physics.resolution_max}
                )

            if physics.resolution_max > 512:
                self.logger.warning(
                    f"Very high fluid resolution ({physics.resolution_max}) will be very slow"
                )

    def _adjust_for_simulation_type(self, plan: SimulationPlan) -> None:
        """
        Adjust parameters based on simulation type.

        Different simulation types have different requirements and best practices.

        Args:
            plan: The plan to adjust (modified in place)
        """
        sim_type = plan.simulation_type

        if sim_type == SimulationType.RIGID_BODY:
            # Ensure reasonable frame count for falling objects
            if plan.duration_frames < 100:
                plan.duration_frames = 250
                self.logger.info("Increased rigid body duration to 250 frames")

        elif sim_type in [SimulationType.FLUID_SMOKE, SimulationType.FLUID_FIRE]:
            # Smoke/fire simulations don't need as many frames
            if plan.duration_frames > 200:
                plan.duration_frames = 150
                self.logger.info("Reduced fluid duration to 150 frames (optimal for smoke)")

        elif sim_type == SimulationType.CLOTH:
            # Cloth needs more quality steps for stability
            if not plan.physics_settings.quality_steps:
                plan.physics_settings.quality_steps = 5
                self.logger.info("Set cloth quality steps to 5")

    def validate_material_properties(self, material: MaterialProperties) -> ValidationResult:
        """
        Validate material properties for physical realism.

        Args:
            material: Material properties to validate

        Returns:
            ValidationResult with warnings if properties are unusual
        """
        warnings = []

        # Check density
        if material.density < 10:
            warnings.append(f"Very low density ({material.density} kg/m³) - lighter than air")
        elif material.density > 20000:
            warnings.append(f"Very high density ({material.density} kg/m³) - denser than most metals")

        # Check friction
        if material.friction > 0.95:
            warnings.append(f"Extremely high friction ({material.friction}) - objects may not slide")

        # Check restitution
        if material.restitution > 0.9:
            warnings.append(f"Very high bounciness ({material.restitution}) - objects will bounce excessively")

        # Check damping
        if material.linear_damping > 0.5:
            warnings.append(f"High linear damping ({material.linear_damping}) - objects will slow quickly")

        is_valid = len(warnings) == 0

        return ValidationResult(
            is_valid=is_valid,
            score=1.0 if is_valid else 0.8,
            warnings=warnings,
            metadata={
                "material": material.name,
                "density": material.density,
                "friction": material.friction
            }
        )

    def get_material_info(self, material_name: str) -> Dict[str, Any]:
        """
        Get information about a material without modifying a plan.

        Useful for debugging or displaying material options to users.

        Args:
            material_name: Material to look up

        Returns:
            Dictionary with material properties and metadata
        """
        props = self._get_material_properties(material_name.lower().replace(" ", "_"))

        return {
            "found": material_name.lower() in self.materials,
            "matched_name": props["name"],
            "properties": props,
            "is_default": props == self.default_material
        }

    def list_available_materials(self) -> Dict[str, list]:
        """
        Get list of all available materials organized by category.

        Returns:
            Dictionary with material categories and names
        """
        categories = {
            "woods": [],
            "metals": [],
            "plastics": [],
            "stones": [],
            "fabrics": [],
            "other": []
        }

        for material_key in self.materials.keys():
            if "wood" in material_key:
                categories["woods"].append(material_key)
            elif "metal" in material_key:
                categories["metals"].append(material_key)
            elif "plastic" in material_key or "rubber" in material_key:
                categories["plastics"].append(material_key)
            elif "stone" in material_key or "concrete" in material_key:
                categories["stones"].append(material_key)
            elif "fabric" in material_key:
                categories["fabrics"].append(material_key)
            else:
                categories["other"].append(material_key)

        return categories
