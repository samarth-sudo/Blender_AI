"""
Fluid liquid simulation template for Blender.

Liquid simulations (water, oil, honey) behave differently from gas (smoke):
- Liquids maintain volume and form puddles
- Surface tension creates droplets
- Viscosity affects flow speed

This uses the same Mantaflow solver as smoke but with different parameters.
"""

from src.templates.base import get_complete_base_template


def get_fluid_liquid_template() -> str:
    """
    Get complete fluid liquid simulation template.

    Returns:
        Complete Python code string
    """
    base = get_complete_base_template()

    liquid_code = f'''{base}


def setup_liquid_domain(location=(0, 0, 5), scale=(10, 10, 10), resolution_max=128):
    """Create liquid simulation domain."""
    bpy.ops.mesh.primitive_cube_add(location=location, scale=scale)
    domain = bpy.context.active_object
    domain.name = "LiquidDomain"

    bpy.ops.object.modifier_add(type='FLUID')
    domain.modifiers["Fluid"].fluid_type = 'DOMAIN'

    domain_settings = domain.modifiers["Fluid"].domain_settings
    domain_settings.domain_type = 'LIQUID'
    domain_settings.resolution_max = resolution_max

    # Liquid-specific settings
    domain_settings.use_mesh = True  # Generate mesh surface
    domain_settings.use_flip_particles = True  # Use FLIP solver

    return domain


def add_liquid_flow(obj, flow_behavior='GEOMETRY', velocity=0.0):
    """Make object emit liquid."""
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    bpy.ops.object.modifier_add(type='FLUID')
    obj.modifiers["Fluid"].fluid_type = 'FLOW'

    flow_settings = obj.modifiers["Fluid"].flow_settings
    flow_settings.flow_type = 'LIQUID'
    flow_settings.flow_behavior = flow_behavior
    flow_settings.velocity_factor = velocity

    obj.select_set(False)


def create_fluid_liquid_simulation(params):
    """Create complete liquid simulation."""
    clear_scene()

    setup_scene(
        frame_end=params.get("duration_frames", 150)
    )

    setup_camera(location=(12.0, -12.0, 10.0), rotation=(55.0, 0.0, 45.0))
    setup_lighting(energy=1000.0)

    # Create domain
    physics = params.get("physics_settings", {{}})
    domain = setup_liquid_domain(
        resolution_max=physics.get("resolution_max", 128)
    )

    # Create liquid emitters
    for obj_def in params.get("objects", []):
        if obj_def.get("is_emitter", True):
            location = obj_def.get("position", (0, 0, 5))
            scale = obj_def.get("scale", 1.0)

            emitter = create_sphere(obj_def["name"], location, scale)
            add_liquid_flow(emitter, velocity=obj_def.get("velocity", 0.0))

    # Bake
    bpy.context.view_layer.objects.active = domain
    domain.select_set(True)
    bpy.ops.fluid.bake_all()

    save_blend_file(params.get("output_path", "/tmp/liquid_simulation.blend"))
    print("Liquid simulation complete!")


if __name__ == "__main__":
    example_params = {{
        "duration_frames": 150,
        "physics_settings": {{"resolution_max": 128}},
        "objects": [{{
            "name": "water_source",
            "position": (0, 0, 8),
            "scale": 1.5,
            "velocity": 2.0
        }}],
        "output_path": "/tmp/liquid.blend"
    }}

    create_fluid_liquid_simulation(example_params)
'''

    return liquid_code
