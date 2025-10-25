"""
Unit tests for individual agents.

Tests each agent in isolation to ensure correct behavior.
"""

import pytest
from pathlib import Path
import tempfile

from src.agents import (
    PlannerAgent,
    PhysicsValidatorAgent,
    CodeGeneratorAgent,
    SyntaxValidatorAgent,
)
from src.models.schemas import (
    SimulationPlan,
    SimulationType,
    SimulationObject,
    ObjectType,
    PhysicsSettings,
    BlenderCode,
)


class TestPlannerAgent:
    """Test PlannerAgent functionality."""

    @pytest.fixture
    def planner(self):
        """Create planner agent for testing."""
        # Skip if no API key
        try:
            return PlannerAgent()
        except Exception:
            pytest.skip("Claude API key not configured")

    def test_simple_rigid_body_parsing(self, planner):
        """Test parsing simple rigid body simulation."""
        result = planner.run("10 cubes falling on a plane")

        assert isinstance(result, SimulationPlan)
        assert result.simulation_type == SimulationType.RIGID_BODY
        assert len(result.objects) >= 2  # At least cubes + ground
        assert result.duration_frames > 0

    def test_smoke_simulation_parsing(self, planner):
        """Test parsing smoke simulation."""
        result = planner.run("Smoke rising from a sphere")

        assert isinstance(result, SimulationPlan)
        assert result.simulation_type in [SimulationType.FLUID_SMOKE, SimulationType.FLUID_FIRE]
        assert len(result.objects) >= 1

    def test_material_extraction(self, planner):
        """Test material name extraction."""
        result = planner.run("20 wooden blocks falling on concrete floor")

        # Should have wood and concrete materials
        materials = [obj.material for obj in result.objects]
        assert any("wood" in mat.lower() for mat in materials)
        assert any("concrete" in mat.lower() for mat in materials)

    def test_object_count_parsing(self, planner):
        """Test correct object count extraction."""
        result = planner.run("Create exactly 15 spheres bouncing")

        # Should have 15 spheres (plus ground)
        spheres = [obj for obj in result.objects if obj.object_type == ObjectType.SPHERE]
        assert len(spheres) > 0
        assert sum(obj.count for obj in spheres) == 15


class TestPhysicsValidatorAgent:
    """Test PhysicsValidatorAgent functionality."""

    @pytest.fixture
    def validator(self):
        """Create physics validator for testing."""
        return PhysicsValidatorAgent()

    @pytest.fixture
    def sample_plan(self):
        """Create sample plan for testing."""
        return SimulationPlan(
            simulation_type=SimulationType.RIGID_BODY,
            objects=[
                SimulationObject(
                    name="block",
                    object_type=ObjectType.CUBE,
                    count=10,
                    material="wood",
                    scale=1.0,
                    is_static=False
                ),
                SimulationObject(
                    name="ground",
                    object_type=ObjectType.PLANE,
                    count=1,
                    material="concrete",
                    scale=10.0,
                    is_static=True
                )
            ],
            physics_settings=PhysicsSettings(gravity=-9.81),
            duration_frames=250,
            user_prompt="test"
        )

    def test_material_enrichment(self, validator, sample_plan):
        """Test material properties are added."""
        result = validator.run(sample_plan)

        # All objects should have physics properties
        for obj in result.objects:
            assert obj.physics_properties is not None
            assert obj.physics_properties.density > 0
            assert 0 <= obj.physics_properties.friction <= 1
            assert 0 <= obj.physics_properties.restitution <= 1

    def test_material_fuzzy_matching(self, validator):
        """Test fuzzy material matching."""
        # "wood" should match "wood_pine"
        props = validator._get_material_properties("wood")
        assert "wood" in props["name"].lower()
        assert props["density"] > 0

    def test_physics_validation(self, validator, sample_plan):
        """Test physics settings validation."""
        # Valid gravity should pass
        validator._validate_physics_settings(sample_plan)

        # Invalid gravity should raise or warn
        sample_plan.physics_settings.gravity = 10  # Positive gravity
        with pytest.raises(Exception):
            validator._validate_physics_settings(sample_plan)

    def test_list_materials(self, validator):
        """Test material listing."""
        materials = validator.list_available_materials()

        assert "woods" in materials
        assert "metals" in materials
        assert len(materials["woods"]) > 0
        assert len(materials["metals"]) > 0


class TestCodeGeneratorAgent:
    """Test CodeGeneratorAgent functionality."""

    @pytest.fixture
    def generator(self):
        """Create code generator for testing."""
        try:
            return CodeGeneratorAgent()
        except Exception:
            pytest.skip("Claude API key not configured")

    @pytest.fixture
    def enriched_plan(self):
        """Create enriched plan for testing."""
        from src.models.schemas import MaterialProperties

        plan = SimulationPlan(
            simulation_type=SimulationType.RIGID_BODY,
            objects=[
                SimulationObject(
                    name="cube",
                    object_type=ObjectType.CUBE,
                    count=5,
                    material="wood",
                    scale=1.0,
                    is_static=False,
                    physics_properties=MaterialProperties(
                        name="Wood",
                        density=600,
                        friction=0.7,
                        restitution=0.15,
                        linear_damping=0.04,
                        angular_damping=0.10,
                        collision_shape="BOX",
                        collision_margin=0.001
                    )
                )
            ],
            physics_settings=PhysicsSettings(gravity=-9.81),
            duration_frames=100,
            user_prompt="test"
        )
        return plan

    def test_code_generation_from_template(self, generator, enriched_plan):
        """Test code generation using templates."""
        code = generator.run(enriched_plan, "/tmp/test.blend")

        assert isinstance(code, BlenderCode)
        assert len(code.code) > 100
        assert "import bpy" in code.code
        assert "rigid_body" in code.code.lower() or "rigidbody" in code.code.lower()

    def test_parameters_conversion(self, generator, enriched_plan):
        """Test plan to parameters conversion."""
        params = generator._plan_to_parameters(enriched_plan, "/tmp/test.blend")

        assert "objects" in params
        assert "physics_settings" in params
        assert params["duration_frames"] == 100
        assert params["output_path"] == "/tmp/test.blend"

    def test_complexity_calculation(self, generator, enriched_plan):
        """Test complexity score calculation."""
        score = generator._calculate_complexity(enriched_plan)

        assert 0.0 <= score <= 1.0
        # Simple rigid body should have low-medium complexity
        assert score < 0.5


class TestSyntaxValidatorAgent:
    """Test SyntaxValidatorAgent functionality."""

    @pytest.fixture
    def validator(self):
        """Create syntax validator for testing."""
        return SyntaxValidatorAgent()

    def test_valid_code(self, validator):
        """Test validation of valid code."""
        valid_code = BlenderCode(
            code="""
import bpy

def test():
    bpy.ops.mesh.primitive_cube_add()

if __name__ == "__main__":
    test()
""",
            complexity_score=0.1
        )

        result = validator.run(valid_code)
        assert result.is_valid
        assert len(result.errors) == 0

    def test_syntax_error_detection(self, validator):
        """Test detection of syntax errors."""
        invalid_code = BlenderCode(
            code="""
import bpy

def test()  # Missing colon
    bpy.ops.mesh.primitive_cube_add()
""",
            complexity_score=0.1
        )

        result = validator.run(invalid_code)
        assert not result.is_valid
        assert len(result.errors) > 0

    def test_security_checks(self, validator):
        """Test security checks."""
        dangerous_code = BlenderCode(
            code="""
import bpy
import os

os.system("rm -rf /")  # Dangerous!
""",
            complexity_score=0.1
        )

        result = validator.run(dangerous_code)
        assert not result.is_valid
        assert any("security" in error.lower() for error in result.errors)

    def test_missing_import_detection(self, validator):
        """Test detection of missing imports."""
        code_no_import = BlenderCode(
            code="""
# Missing 'import bpy'
bpy.ops.mesh.primitive_cube_add()
""",
            complexity_score=0.1
        )

        result = validator.run(code_no_import)
        assert not result.is_valid
        assert any("import" in error.lower() for error in result.errors)

    def test_auto_fix(self, validator):
        """Test automatic fixing of common issues."""
        code_missing_import = BlenderCode(
            code="""
# Missing import
def test():
    bpy.ops.mesh.primitive_cube_add()
""",
            complexity_score=0.1
        )

        fixed_code, result = validator.validate_and_fix(code_missing_import)

        # Should add import
        assert "import bpy" in fixed_code.code
        # Should now be valid
        assert result.is_valid or len(result.errors) < len(validator.execute(code_missing_import).errors)

    def test_code_statistics(self, validator):
        """Test code statistics calculation."""
        code = """
import bpy
import math

# This is a comment

def test():
    bpy.ops.mesh.primitive_cube_add()
    bpy.data.objects["Cube"].location = (0, 0, 0)

if __name__ == "__main__":
    test()
"""

        stats = validator.get_code_statistics(code)

        assert stats["total_lines"] > 0
        assert stats["code_lines"] > 0
        assert stats["comment_lines"] > 0
        assert stats["functions"] == 1
        assert stats["bpy_operators"] >= 1
        assert stats["bpy_data_access"] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
