"""
Quality Validator Agent - Sixth and final agent in the pipeline.

Responsibility: Inspect generated .blend file and calculate quality score.

This agent runs Blender again to:
1. Open the .blend file
2. Inspect scene contents (objects, physics, camera, lights)
3. Validate physics setup
4. Calculate quality score (0-1)
5. Identify issues

This is the final verification step before returning results to the user.
"""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any

from src.agents.base_agent import BaseAgent
from src.models.schemas import (
    SimulationPlan,
    QualityMetrics,
    ExecutionResult
)
from src.utils.errors import QualityError


class QualityValidatorAgent(BaseAgent):
    """
    Quality Validator Agent: Inspect and score generated simulations.

    This agent provides automated quality assurance by:
    - Verifying object counts match plan
    - Checking physics setup
    - Validating camera and lighting
    - Identifying common issues

    Example:
        validator = QualityValidatorAgent()
        metrics = validator.run(
            blend_file="/tmp/sim.blend",
            expected_plan=plan
        )
        if metrics.quality_score > 0.8:
            print("High quality simulation!")
    """

    def __init__(self, blender_executable: str = None):
        """Initialize Quality Validator Agent."""
        super().__init__("QualityValidatorAgent")
        self.blender_executable = blender_executable or self.config.blender.executable

    def execute(
        self,
        execution_result: ExecutionResult,
        expected_plan: SimulationPlan
    ) -> QualityMetrics:
        """
        Validate quality of generated simulation.

        Args:
            execution_result: Result from ExecutorAgent
            expected_plan: The plan used to generate the simulation

        Returns:
            QualityMetrics with score and details

        Raises:
            QualityError: If quality check fails
        """
        if not execution_result.success or not execution_result.blend_file_path:
            raise QualityError(
                "Cannot validate quality: execution failed",
                quality_score=0.0,
                threshold=0.8
            )

        blend_file = execution_result.blend_file_path

        self.logger.info(f"Validating quality of {blend_file}")

        # Run inspection script in Blender
        inspection_data = self._inspect_blend_file(blend_file, expected_plan)

        # Calculate metrics
        metrics = self._calculate_metrics(inspection_data, expected_plan)

        # Check threshold
        min_threshold = self.config.quality.get("min_quality_score", 0.8)
        if metrics.quality_score < min_threshold:
            self.logger.warning(
                f"Quality score {metrics.quality_score:.2f} below threshold {min_threshold}",
                issues=metrics.issues
            )

        self.logger.success(
            "execute",
            quality_score=metrics.quality_score,
            issues=len(metrics.issues)
        )

        return metrics

    def _inspect_blend_file(
        self,
        blend_file: str,
        expected_plan: SimulationPlan
    ) -> Dict[str, Any]:
        """
        Run Blender to inspect the .blend file.

        Args:
            blend_file: Path to .blend file
            expected_plan: Expected simulation plan

        Returns:
            Dictionary with inspection results
        """
        # Create inspection script
        inspection_script = self._create_inspection_script(expected_plan)

        # Write to temp file
        fd, script_path = tempfile.mkstemp(suffix=".py", prefix="inspect_")
        try:
            with open(fd, 'w') as f:
                f.write(inspection_script)

            # Run Blender with inspection script
            cmd = [
                self.blender_executable,
                blend_file,
                "--background",
                "--python", script_path
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            # Extract JSON result from stdout
            stdout = result.stdout

            # Look for our JSON marker
            if "INSPECTION_RESULT:" in stdout:
                json_str = stdout.split("INSPECTION_RESULT:")[1].split('\n')[0]
                return json.loads(json_str)
            else:
                raise QualityError(
                    "Failed to get inspection results from Blender",
                    quality_score=0.0,
                    threshold=0.8
                )

        except subprocess.TimeoutExpired:
            raise QualityError(
                "Inspection timed out",
                quality_score=0.0,
                threshold=0.8
            )

        except json.JSONDecodeError as e:
            raise QualityError(
                f"Failed to parse inspection results: {str(e)}",
                quality_score=0.0,
                threshold=0.8
            )

        finally:
            try:
                Path(script_path).unlink()
            except:
                pass

    def _create_inspection_script(self, expected_plan: SimulationPlan) -> str:
        """
        Create Blender Python script to inspect the scene.

        Args:
            expected_plan: Expected simulation plan

        Returns:
            Python code string
        """
        expected_object_count = sum(obj.count for obj in expected_plan.objects)
        sim_type = expected_plan.simulation_type.value

        script = f'''
import bpy
import json

# Inspection script
result = {{}}

# Basic scene info
result["object_count"] = len(bpy.data.objects)
result["mesh_count"] = len(bpy.data.meshes)

# Check for camera
result["has_camera"] = bpy.context.scene.camera is not None
if result["has_camera"]:
    cam = bpy.context.scene.camera
    result["camera_location"] = list(cam.location)

# Check for lights
result["light_count"] = len([obj for obj in bpy.data.objects if obj.type == 'LIGHT'])
if result["light_count"] > 0:
    first_light = next(obj for obj in bpy.data.objects if obj.type == 'LIGHT')
    result["lighting_energy"] = first_light.data.energy

# Frame range
result["frame_start"] = bpy.context.scene.frame_start
result["frame_end"] = bpy.context.scene.frame_end
result["frame_range"] = result["frame_end"] - result["frame_start"] + 1

# Physics checks based on simulation type
sim_type = "{sim_type}"

if sim_type == "rigid_body":
    # Check rigid body world
    result["has_rigidbody_world"] = bpy.context.scene.rigidbody_world is not None

    if result["has_rigidbody_world"]:
        rbw = bpy.context.scene.rigidbody_world
        # In Blender 4.5+, gravity is on scene, not rigidbody_world
        result["gravity"] = list(bpy.context.scene.gravity)
        result["substeps"] = rbw.substeps_per_frame

    # Count rigid body objects
    result["rigid_body_count"] = len([obj for obj in bpy.data.objects if obj.rigid_body])
    result["active_rigid_bodies"] = len([obj for obj in bpy.data.objects
                                         if obj.rigid_body and obj.rigid_body.type == 'ACTIVE'])
    result["passive_rigid_bodies"] = len([obj for obj in bpy.data.objects
                                          if obj.rigid_body and obj.rigid_body.type == 'PASSIVE'])

elif "fluid" in sim_type:
    # Check for fluid domain
    result["has_fluid_domain"] = any(
        obj for obj in bpy.data.objects
        if any(mod.type == 'FLUID' and mod.fluid_type == 'DOMAIN' for mod in obj.modifiers)
    )

    # Count flow objects
    result["fluid_flow_count"] = len([
        obj for obj in bpy.data.objects
        if any(mod.type == 'FLUID' and mod.fluid_type == 'FLOW' for mod in obj.modifiers)
    ])

elif sim_type == "cloth":
    # Check for cloth objects
    result["cloth_count"] = len([
        obj for obj in bpy.data.objects
        if any(mod.type == 'CLOTH' for mod in obj.modifiers)
    ])

    # Check for collision objects
    result["collision_count"] = len([
        obj for obj in bpy.data.objects
        if any(mod.type == 'COLLISION' for mod in obj.modifiers)
    ])

# Expected vs actual
result["expected_object_count"] = {expected_object_count}

# Output result as JSON
print("INSPECTION_RESULT:" + json.dumps(result))
'''

        return script

    def _calculate_metrics(
        self,
        inspection_data: Dict[str, Any],
        expected_plan: SimulationPlan
    ) -> QualityMetrics:
        """
        Calculate quality metrics from inspection data.

        Args:
            inspection_data: Data from Blender inspection
            expected_plan: Expected simulation plan

        Returns:
            QualityMetrics object
        """
        issues = []
        score_components = []

        # Check 1: Object count
        expected_count = sum(obj.count for obj in expected_plan.objects)
        actual_count = inspection_data.get("object_count", 0)

        object_count_correct = abs(actual_count - expected_count) <= 2  # Allow 2 object tolerance (camera, light)
        score_components.append(1.0 if object_count_correct else 0.5)

        if not object_count_correct:
            issues.append(
                f"Object count mismatch: expected ~{expected_count}, got {actual_count}"
            )

        # Check 2: Camera
        has_camera = inspection_data.get("has_camera", False)
        score_components.append(1.0 if has_camera else 0.0)

        if not has_camera:
            issues.append("No camera found in scene")

        # Check 3: Lighting
        light_count = inspection_data.get("light_count", 0)
        has_lighting = light_count > 0
        score_components.append(1.0 if has_lighting else 0.5)

        if not has_lighting:
            issues.append("No lighting found in scene")

        # Check 4: Physics setup (simulation-specific)
        has_physics = False
        sim_type = expected_plan.simulation_type

        if sim_type.value == "rigid_body":
            has_physics = inspection_data.get("has_rigidbody_world", False)
            rigid_body_count = inspection_data.get("rigid_body_count", 0)

            if not has_physics:
                issues.append("Rigid body world not configured")
            elif rigid_body_count == 0:
                issues.append("No rigid body objects found")

        elif "fluid" in sim_type.value:
            has_physics = inspection_data.get("has_fluid_domain", False)
            flow_count = inspection_data.get("fluid_flow_count", 0)

            if not has_physics:
                issues.append("Fluid domain not found")
            elif flow_count == 0:
                issues.append("No fluid emitters found")

        elif sim_type.value == "cloth":
            cloth_count = inspection_data.get("cloth_count", 0)
            has_physics = cloth_count > 0

            if not has_physics:
                issues.append("No cloth objects found")

        score_components.append(1.0 if has_physics else 0.0)

        # Check 5: Frame range
        frame_range = inspection_data.get("frame_range", 0)
        expected_frames = expected_plan.duration_frames
        frames_match = abs(frame_range - expected_frames) <= 5

        score_components.append(1.0 if frames_match else 0.8)

        if not frames_match:
            issues.append(
                f"Frame range mismatch: expected {expected_frames}, got {frame_range}"
            )

        # Calculate overall score (weighted average)
        weights = [0.2, 0.2, 0.1, 0.4, 0.1]  # Physics setup is most important
        quality_score = sum(s * w for s, w in zip(score_components, weights))

        # Create metrics object
        metrics = QualityMetrics(
            object_count_correct=object_count_correct,
            has_physics_setup=has_physics,
            has_camera=has_camera,
            has_lighting=has_lighting,
            rigid_body_count=inspection_data.get("rigid_body_count"),
            max_interpenetration=None,  # Would need more complex analysis
            lighting_intensity=inspection_data.get("lighting_energy"),
            camera_in_bounds=True,  # Assume true for now
            quality_score=quality_score,
            issues=issues
        )

        return metrics

    def quick_validate(self, blend_file: str) -> bool:
        """
        Quick validation to check if file is a valid .blend file.

        This doesn't open Blender - just checks the file.

        Args:
            blend_file: Path to .blend file

        Returns:
            True if file appears valid
        """
        path = Path(blend_file)

        # Check file exists
        if not path.exists():
            self.logger.warning(f"File not found: {blend_file}")
            return False

        # Check file size (should be at least a few KB)
        size = path.stat().st_size
        if size < 1024:  # Less than 1KB
            self.logger.warning(f"File too small ({size} bytes): {blend_file}")
            return False

        # Check .blend file header (Blender files start with "BLENDER")
        try:
            with open(blend_file, 'rb') as f:
                header = f.read(7)
                if header != b'BLENDER':
                    self.logger.warning(f"Invalid .blend file header: {blend_file}")
                    return False
        except Exception as e:
            self.logger.warning(f"Failed to read file: {str(e)}")
            return False

        return True
