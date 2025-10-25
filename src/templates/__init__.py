"""
Blender Python API templates for code generation.

These templates provide production-ready, well-tested Blender scripts
that the Code Generator Agent can use as a foundation.

Each template is heavily documented to help beginners understand
the Blender Python API (bpy).
"""

from src.templates.base import (
    get_base_template,
    get_scene_setup,
    get_camera_setup,
    get_lighting_setup,
)
from src.templates.rigid_body import get_rigid_body_template
from src.templates.fluid_smoke import get_fluid_smoke_template
from src.templates.fluid_liquid import get_fluid_liquid_template
from src.templates.cloth import get_cloth_template

__all__ = [
    "get_base_template",
    "get_scene_setup",
    "get_camera_setup",
    "get_lighting_setup",
    "get_rigid_body_template",
    "get_fluid_smoke_template",
    "get_fluid_liquid_template",
    "get_cloth_template",
]
