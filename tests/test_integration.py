"""
Integration tests for the complete simulation pipeline.

These tests run the entire orchestrator pipeline to verify end-to-end functionality.
"""

import pytest
import os
from pathlib import Path
import tempfile

from src import SimulationOrchestrator
from src.models.schemas import SimulationType


# Test scenarios covering different simulation types and complexity levels
TEST_SCENARIOS = [
    {
        "id": "simple_rigid_body",
        "name": "Simple Rigid Body",
        "prompt": "5 cubes falling on a plane",
        "expected_type": SimulationType.RIGID_BODY,
        "min_quality": 0.7,
        "max_time": 60,
    },
    {
        "id": "material_variety",
        "name": "Multiple Materials",
        "prompt": "10 wooden blocks and 5 metal spheres falling on concrete floor",
        "expected_type": SimulationType.RIGID_BODY,
        "min_quality": 0.7,
        "max_time": 90,
    },
    {
        "id": "smoke_simple",
        "name": "Simple Smoke",
        "prompt": "Smoke rising from a sphere",
        "expected_type": SimulationType.FLUID_SMOKE,
        "min_quality": 0.6,  # Lower for fluid sims
        "max_time": 120,
    },
    {
        "id": "high_count",
        "name": "Many Objects",
        "prompt": "30 small rubber balls bouncing",
        "expected_type": SimulationType.RIGID_BODY,
        "min_quality": 0.6,
        "max_time": 120,
    },
    {
        "id": "cloth_drape",
        "name": "Cloth Draping",
        "prompt": "A cloth draped over a sphere",
        "expected_type": SimulationType.CLOTH,
        "min_quality": 0.6,
        "max_time": 120,
    },
    {
        "id": "realistic_scene",
        "name": "Realistic Physics",
        "prompt": "A glass sphere rolling down a wooden ramp",
        "expected_type": SimulationType.RIGID_BODY,
        "min_quality": 0.7,
        "max_time": 90,
    },
    {
        "id": "fire_simulation",
        "name": "Fire Simulation",
        "prompt": "Fire rising from a small cube",
        "expected_type": SimulationType.FLUID_FIRE,
        "min_quality": 0.6,
        "max_time": 150,
    },
    {
        "id": "bouncing_physics",
        "name": "Bouncing Test",
        "prompt": "3 rubber balls bouncing on metal floor",
        "expected_type": SimulationType.RIGID_BODY,
        "min_quality": 0.7,
        "max_time": 60,
    },
    {
        "id": "static_dynamic",
        "name": "Static and Dynamic",
        "prompt": "5 cubes falling between 2 static walls",
        "expected_type": SimulationType.RIGID_BODY,
        "min_quality": 0.7,
        "max_time": 90,
    },
    {
        "id": "complex_materials",
        "name": "Complex Material Mix",
        "prompt": "5 ice cubes, 3 wooden blocks, and 2 metal spheres on rubber surface",
        "expected_type": SimulationType.RIGID_BODY,
        "min_quality": 0.6,
        "max_time": 120,
    },
]


class TestSimulationGeneration:
    """Test complete simulation generation pipeline."""

    @pytest.fixture(scope="class")
    def orchestrator(self):
        """Create orchestrator for testing."""
        # Check if we can run tests
        orch = SimulationOrchestrator()
        is_ready, issues = orch.check_system_ready()

        if not is_ready:
            pytest.skip(f"System not ready: {issues}")

        return orch

    @pytest.fixture
    def temp_output(self):
        """Create temporary output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.parametrize("scenario", TEST_SCENARIOS, ids=[s["id"] for s in TEST_SCENARIOS])
    def test_scenario(self, orchestrator, temp_output, scenario):
        """Test a specific simulation scenario."""
        print(f"\n\nTesting: {scenario['name']}")
        print(f"Prompt: {scenario['prompt']}")

        output_path = str(temp_output / f"{scenario['id']}.blend")

        # Generate simulation
        result = orchestrator.generate_simulation(
            user_prompt=scenario["prompt"],
            output_path=output_path
        )

        # Assertions
        assert result.success, f"Generation failed: {result.errors}"
        assert result.blend_file is not None
        assert Path(result.blend_file).exists()

        # Check simulation type
        assert result.plan.simulation_type == scenario["expected_type"]

        # Check quality
        if result.quality_metrics:
            print(f"Quality score: {result.quality_metrics.quality_score:.2f}")
            assert result.quality_metrics.quality_score >= scenario["min_quality"], \
                f"Quality too low: {result.quality_metrics.quality_score:.2f} < {scenario['min_quality']}"

            if result.quality_metrics.issues:
                print(f"Issues: {result.quality_metrics.issues}")

        # Check timing
        print(f"Total time: {result.total_time_seconds:.1f}s")
        assert result.total_time_seconds < scenario["max_time"], \
            f"Generation too slow: {result.total_time_seconds:.1f}s > {scenario['max_time']}s"

        # Check file size (should be reasonable)
        file_size = Path(result.blend_file).stat().st_size
        print(f"File size: {file_size / 1024 / 1024:.2f} MB")
        assert file_size > 1024, "File too small (< 1KB)"
        assert file_size < 100 * 1024 * 1024, "File too large (> 100MB)"


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for testing."""
        orch = SimulationOrchestrator()
        is_ready, issues = orch.check_system_ready()

        if not is_ready:
            pytest.skip(f"System not ready: {issues}")

        return orch

    def test_invalid_prompt(self, orchestrator):
        """Test handling of invalid/unclear prompts."""
        # Very vague prompt
        result = orchestrator.generate_simulation("make something")

        # Should either succeed with reasonable defaults or fail gracefully
        if not result.success:
            assert len(result.errors) > 0
            # Error should be informative
            assert any(error for error in result.errors)

    def test_extreme_object_count(self, orchestrator):
        """Test handling of very high object counts."""
        # This should warn but still work (or fail gracefully)
        result = orchestrator.generate_simulation("1000 cubes falling")

        # Either succeeds with warning or fails with clear message
        if not result.success:
            assert len(result.errors) > 0
        else:
            # Should have warnings about high count
            if result.warnings:
                assert any("count" in w.lower() or "performance" in w.lower()
                          for w in result.warnings)

    def test_conflicting_requirements(self, orchestrator):
        """Test handling of conflicting requirements."""
        # Conflicting simulation types
        result = orchestrator.generate_simulation(
            "rigid body blocks with fluid smoke"
        )

        # Should pick one simulation type
        assert result.plan is not None
        assert result.plan.simulation_type in [
            SimulationType.RIGID_BODY,
            SimulationType.FLUID_SMOKE
        ]


class TestSystemHealth:
    """Test system health and readiness checks."""

    def test_system_ready_check(self):
        """Test system readiness check."""
        orchestrator = SimulationOrchestrator()
        is_ready, issues = orchestrator.check_system_ready()

        # Either ready or has clear issues
        if not is_ready:
            assert len(issues) > 0
            for issue in issues:
                assert isinstance(issue, str)
                assert len(issue) > 0

    def test_materials_available(self):
        """Test materials are properly loaded."""
        orchestrator = SimulationOrchestrator()
        materials = orchestrator.list_available_materials()

        assert "woods" in materials
        assert "metals" in materials
        assert len(materials["woods"]) > 0

    def test_pipeline_stats(self):
        """Test pipeline statistics."""
        orchestrator = SimulationOrchestrator()
        stats = orchestrator.get_pipeline_stats()

        # Should have stats for all agents
        expected_agents = ["planner", "physics_validator", "code_generator",
                          "syntax_validator", "executor", "quality_validator"]

        for agent in expected_agents:
            assert agent in stats


class TestProgressTracking:
    """Test progress tracking functionality."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for testing."""
        orch = SimulationOrchestrator()
        is_ready, issues = orch.check_system_ready()

        if not is_ready:
            pytest.skip(f"System not ready: {issues}")

        return orch

    def test_progress_callback(self, orchestrator):
        """Test progress callback is called."""
        progress_calls = []

        def callback(step, progress):
            progress_calls.append({"step": step, "progress": progress})

        result = orchestrator.generate_simulation(
            "3 cubes falling",
            progress_callback=callback
        )

        # Should have multiple progress updates
        assert len(progress_calls) > 0

        # Progress should increase
        if len(progress_calls) > 1:
            assert progress_calls[-1]["progress"] >= progress_calls[0]["progress"]

        # Final progress should be 1.0 if successful
        if result.success:
            assert progress_calls[-1]["progress"] == 1.0


class TestPerformance:
    """Test performance and timing."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for testing."""
        orch = SimulationOrchestrator()
        is_ready, issues = orch.check_system_ready()

        if not is_ready:
            pytest.skip(f"System not ready: {issues}")

        return orch

    def test_simple_generation_speed(self, orchestrator):
        """Test simple generation completes in reasonable time."""
        import time

        start = time.time()

        result = orchestrator.generate_simulation("3 cubes falling")

        elapsed = time.time() - start

        # Should complete in under 2 minutes for simple scene
        assert elapsed < 120, f"Too slow: {elapsed:.1f}s"

        if result.success:
            print(f"\nGeneration time: {elapsed:.1f}s")
            print(f"Agent breakdown: {result.agent_times}")

    def test_estimation_accuracy(self, orchestrator):
        """Test time estimation is reasonable."""
        estimated = orchestrator.estimate_generation_time("5 cubes falling")

        # Estimate should be positive and reasonable
        assert estimated > 0
        assert estimated < 300  # Less than 5 minutes estimate


# Smoke tests - quick checks that basic functionality works
class TestSmokeTests:
    """Quick smoke tests for basic functionality."""

    def test_import_works(self):
        """Test basic imports work."""
        from src import SimulationOrchestrator
        from src.agents import PlannerAgent
        from src.models.schemas import SimulationPlan

        assert SimulationOrchestrator is not None
        assert PlannerAgent is not None
        assert SimulationPlan is not None

    def test_orchestrator_creation(self):
        """Test orchestrator can be created."""
        orchestrator = SimulationOrchestrator()
        assert orchestrator is not None

    def test_config_loaded(self):
        """Test configuration is loaded."""
        from src.utils.config import get_config

        config = get_config()
        assert config is not None
        assert config.materials is not None
        assert len(config.materials) > 0


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
