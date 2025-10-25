"""
Cloth simulation template for Blender.

Cloth physics simulates flexible materials like fabric, flags, curtains:
- Deforms based on forces (gravity, wind, collisions)
- Has stiffness and elasticity properties
- Can self-collide

Common uses: Flags, banners, tablecloths, clothing
"""

from src.templates.base import get_complete_base_template


def get_cloth_template() -> str:
    """
    Get complete cloth simulation template.

    Returns:
        Complete Python code string
    """
    base = get_complete_base_template()

    cloth_code = f'''{base}


def add_cloth_physics(obj, mass=0.3, tension_stiffness=15, compression_stiffness=15,
                      shear_stiffness=5, bending_stiffness=0.5, air_damping=1.0):
    """
    Add cloth physics to an object (must be a mesh).

    Args:
        obj: Mesh object to add cloth to
        mass: Mass per square meter (kg/m²) - affects weight
        tension_stiffness: Resistance to stretching (1-1000)
        compression_stiffness: Resistance to compression (1-1000)
        shear_stiffness: Resistance to shearing (1-1000)
        bending_stiffness: Resistance to bending (0-10)
        air_damping: Air resistance (0-1, higher = more drag)

    Material Properties:
    - Silk: light, flows easily (low stiffness)
    - Cotton: medium weight and stiffness
    - Leather: heavy, very stiff

    The cloth will automatically interact with collision objects.
    """
    # Select object
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # Add cloth modifier
    bpy.ops.object.modifier_add(type='CLOTH')

    # Configure cloth settings
    cloth_settings = obj.modifiers["Cloth"].settings

    # Physical properties
    cloth_settings.mass = mass
    cloth_settings.air_damping = air_damping

    # Stiffness properties
    cloth_settings.tension_stiffness = tension_stiffness
    cloth_settings.compression_stiffness = compression_stiffness
    cloth_settings.shear_stiffness = shear_stiffness
    cloth_settings.bending_stiffness = bending_stiffness

    # Quality (higher = more accurate but slower)
    cloth_settings.quality = 5

    # Enable self-collision (prevents cloth passing through itself)
    cloth_settings.use_self_collision = True
    cloth_settings.self_friction = 5.0
    cloth_settings.self_distance_min = 0.01

    print(f"Added cloth physics to {{obj.name}}: mass={{mass}}kg/m²")

    obj.select_set(False)


def add_collision_object(obj):
    """
    Make an object interact with cloth (collision object).

    The cloth will drape over or bounce off this object.

    Args:
        obj: Object to make collidable
    """
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # Add collision modifier
    bpy.ops.object.modifier_add(type='COLLISION')

    # Configure collision settings
    coll_settings = obj.modifiers["Collision"].settings

    # Collision properties
    coll_settings.thickness_outer = 0.02  # Collision distance
    coll_settings.thickness_inner = 0.02
    coll_settings.cloth_friction = 5.0  # Friction with cloth

    print(f"Added collision to {{obj.name}}")

    obj.select_set(False)


def pin_cloth_vertices(obj, pin_group="Pin"):
    """
    Pin (fix) certain vertices of cloth so they don't move.

    This is useful for:
    - Hanging curtains (pin top edge)
    - Flags (pin one side to pole)
    - Tablecloths (pin corners)

    Args:
        obj: Cloth object
        pin_group: Name of vertex group to pin
    """
    # In a real implementation, you would:
    # 1. Create a vertex group
    # 2. Assign specific vertices to it
    # 3. Set the cloth modifier to use that group

    # This is simplified - normally done in edit mode
    if pin_group not in obj.vertex_groups:
        obj.vertex_groups.new(name=pin_group)

    # Set pin group in cloth modifier
    obj.modifiers["Cloth"].settings.vertex_group_mass = pin_group

    print(f"Pinned vertices in group '{{pin_group}}'")


def bake_cloth_simulation():
    """Bake the cloth simulation."""
    print("Baking cloth simulation...")

    # Cloth uses point cache like rigid bodies
    bpy.ops.ptcache.bake_all(bake=True)

    print("Cloth simulation baked")


def create_cloth_simulation(params):
    """
    Create a complete cloth simulation.

    Args:
        params: Dictionary with simulation parameters
    """
    # Step 1: Clear scene
    clear_scene()

    # Step 2: Setup scene
    setup_scene(
        frame_end=params.get("duration_frames", 200),
        frame_rate=params.get("frame_rate", 24)
    )

    # Step 3: Create camera
    camera_settings = params.get("camera_settings", {{}})
    setup_camera(
        location=camera_settings.get("location", (8.0, -8.0, 6.0)),
        rotation=camera_settings.get("rotation", (60.0, 0.0, 45.0))
    )

    # Step 4: Setup lighting
    setup_lighting(energy=1.5)

    # Step 5: Create cloth objects
    cloth_objects = []
    collision_objects = []

    for obj_def in params.get("objects", []):
        obj_type = obj_def.get("object_type", "plane")
        location = obj_def.get("position", (0, 0, 5))
        scale = obj_def.get("scale", 2.0)
        is_cloth = obj_def.get("is_cloth", True)

        # Create object
        if obj_type == "plane":
            # Subdivide plane for cloth deformation
            bpy.ops.mesh.primitive_plane_add(location=location, scale=scale)
            obj = bpy.context.active_object
            obj.name = obj_def["name"]

            # Subdivide to add geometry (cloth needs vertices to deform)
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.subdivide(number_cuts=20)  # Creates grid of vertices
            bpy.ops.object.mode_set(mode='OBJECT')

        elif obj_type == "sphere":
            obj = create_sphere(obj_def["name"], location, scale)
        elif obj_type == "cube":
            obj = create_cube(obj_def["name"], location, scale)
        else:
            obj = create_plane(obj_def["name"], location, scale)

        # Apply material
        mat_color = obj_def.get("color", (0.8, 0.3, 0.3, 1.0))
        material = create_material(obj_def.get("material", "cloth_mat"), color=mat_color)
        apply_material(obj, material)

        # Add physics
        if is_cloth:
            # Get physics properties
            physics_props = obj_def.get("physics_properties", {{}})

            add_cloth_physics(
                obj,
                mass=physics_props.get("mass_per_m2", 0.3),
                tension_stiffness=physics_props.get("tension_stiffness", 15),
                compression_stiffness=physics_props.get("compression_stiffness", 15),
                shear_stiffness=physics_props.get("shear_stiffness", 5),
                bending_stiffness=physics_props.get("bending_stiffness", 0.5),
                air_damping=physics_props.get("air_damping", 1.0)
            )

            cloth_objects.append(obj)
        else:
            # Collision object
            add_collision_object(obj)
            collision_objects.append(obj)

    # Step 6: Bake simulation
    bake_cloth_simulation()

    # Step 7: Save file
    output_path = params.get("output_path", "/tmp/cloth_simulation.blend")
    save_blend_file(output_path)

    print("Cloth simulation complete!")


# Example usage
if __name__ == "__main__":
    example_params = {{
        "duration_frames": 200,
        "objects": [
            {{
                "name": "fabric",
                "object_type": "plane",
                "position": (0, 0, 5),
                "scale": 3.0,
                "is_cloth": True,
                "color": (0.8, 0.2, 0.2, 1.0),
                "physics_properties": {{
                    "mass_per_m2": 0.3,  # Light fabric
                    "tension_stiffness": 15,
                    "bending_stiffness": 0.5
                }}
            }},
            {{
                "name": "sphere_collision",
                "object_type": "sphere",
                "position": (0, 0, 2),
                "scale": 1.0,
                "is_cloth": False
            }}
        ],
        "output_path": "/tmp/cloth_simulation.blend"
    }}

    create_cloth_simulation(example_params)
'''

    return cloth_code
