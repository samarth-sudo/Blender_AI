"""
Rigid body physics template for Blender.

Rigid body physics simulates solid objects that don't deform:
- Cubes, spheres, cylinders
- Falling, bouncing, stacking
- Collision detection

This is the most straightforward simulation type to start with.
"""

from src.templates.base import get_complete_base_template


def get_rigid_body_setup() -> str:
    """
    Get code for setting up rigid body world.

    The rigid body world contains global physics settings that affect
    all rigid body objects in the scene.

    Returns:
        Python code string
    """
    return '''
def setup_rigid_body_world(gravity=-9.81, substeps=10, iterations=10):
    """
    Configure rigid body physics world.

    Args:
        gravity: Gravity acceleration in m/s² (negative pulls down)
        substeps: Physics calculations per frame (higher = more accurate)
        iterations: Solver iterations per substep (higher = more stable)

    The rigid body world is created automatically when you add the first
    rigid body object, but we can configure its settings.
    """
    scene = bpy.context.scene

    # Enable rigid body world if not already present
    if scene.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()

    # Configure physics settings
    rbw = scene.rigidbody_world

    # Set gravity on scene (Z-axis is up/down in Blender)
    # In Blender 4.x, gravity is on the scene, not rigidbody_world
    scene.gravity = (0.0, 0.0, gravity)

    # Substeps: More substeps = more accurate but slower
    rbw.substeps_per_frame = substeps

    # Solver iterations: More iterations = more stable
    rbw.solver_iterations = iterations

    # Use split impulse for better stacking stability
    rbw.use_split_impulse = True

    print(f"Rigid body world configured: gravity={gravity}, substeps={substeps}")
'''


def get_rigid_body_object() -> str:
    """
    Get code for adding rigid body physics to objects.

    Returns:
        Python code string
    """
    return '''
def add_rigid_body(obj, body_type='ACTIVE', mass=1.0, friction=0.5, restitution=0.5,
                   linear_damping=0.04, angular_damping=0.1, collision_shape='CONVEX_HULL',
                   collision_margin=0.001):
    """
    Add rigid body physics to an object.

    Args:
        obj: Blender object to add physics to
        body_type: 'ACTIVE' (moves) or 'PASSIVE' (static, doesn't move)
        mass: Object mass in kg (heavier objects are harder to move)
        friction: Surface friction 0-1 (0=slippery ice, 1=rubber)
        restitution: Bounciness 0-1 (0=no bounce, 1=perfect bounce)
        linear_damping: Resistance to linear motion 0-1 (air resistance)
        angular_damping: Resistance to rotation 0-1 (rotational drag)
        collision_shape: Shape for collision detection
        collision_margin: Safety distance around object (prevents tunneling)

    Collision Shapes:
    - BOX: Axis-aligned bounding box (fastest, best for cubes)
    - SPHERE: Sphere (fast, best for balls)
    - CONVEX_HULL: Convex wrapping (good balance)
    - MESH: Exact mesh shape (slowest, most accurate)
    """
    # Select the object
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # Add rigid body physics
    bpy.ops.rigidbody.object_add()

    # Configure rigid body properties
    rb = obj.rigid_body
    rb.type = body_type
    rb.mass = mass
    rb.friction = friction
    rb.restitution = restitution
    rb.linear_damping = linear_damping
    rb.angular_damping = angular_damping
    rb.collision_shape = collision_shape
    rb.collision_margin = collision_margin

    # For passive objects (ground, walls), enable animated so they can be keyframed
    if body_type == 'PASSIVE':
        rb.kinematic = False

    print(f"Added rigid body to {obj.name}: type={body_type}, mass={mass}kg")

    # Deselect
    obj.select_set(False)
'''


def get_bake_simulation() -> str:
    """
    Get code for baking rigid body simulation.

    Baking pre-calculates the physics simulation for all frames.
    This is required before rendering.

    Returns:
        Python code string
    """
    return '''
def bake_rigid_body_simulation():
    """
    Bake (pre-calculate) the rigid body simulation.
    Compatible with Blender 4.5+ and earlier versions.

    Baking runs the physics simulation for all frames and caches the results.
    This is necessary before you can render or save the animation.

    The baking process:
    1. Calculates object positions/rotations for every frame
    2. Stores results in cache
    3. Allows fast playback and rendering
    """
    scene = bpy.context.scene

    # Set frame range for baking
    start_frame = scene.frame_start
    end_frame = scene.frame_end

    print(f"Baking rigid body simulation: frames {start_frame}-{end_frame}")
    print("This may take a while for complex scenes...")

    # Bake the simulation with version-aware context override
    # Blender 4.5+ changed the context override API
    if bpy.app.version >= (4, 5, 0):
        # Use temp_override context manager for Blender 4.5+
        with bpy.context.temp_override(
            scene=scene,
            point_cache=scene.rigidbody_world.point_cache
        ):
            bpy.ops.ptcache.bake_all(bake=True)
    else:
        # Legacy API for Blender < 4.5
        override = bpy.context.copy()
        override['point_cache'] = scene.rigidbody_world.point_cache
        bpy.ops.ptcache.bake(override, bake=True)

    print("Simulation baked successfully")
'''


def get_rigid_body_template() -> str:
    """
    Get complete rigid body template.

    This template includes everything needed for a rigid body simulation:
    - Scene setup
    - Object creation
    - Physics configuration
    - Simulation baking
    - File saving

    Returns:
        Complete Python code string
    """
    base = get_complete_base_template()

    rigid_body_code = f'''{base}

{get_rigid_body_setup()}

{get_rigid_body_object()}

{get_bake_simulation()}


def create_rigid_body_simulation(params):
    """
    Create a complete rigid body simulation from parameters.

    Args:
        params: Dictionary with simulation parameters
            - objects: List of object definitions
            - physics_settings: Global physics settings
            - duration_frames: Animation length
            - output_path: Where to save .blend file
    """
    # Step 1: Clear scene
    clear_scene()

    # Step 2: Setup scene basics
    setup_scene(
        frame_start=1,
        frame_end=params.get("duration_frames", 250),
        frame_rate=params.get("frame_rate", 24)
    )

    # Step 3: Setup rigid body world
    physics = params.get("physics_settings", {{}})
    setup_rigid_body_world(
        gravity=physics.get("gravity", -9.81),
        substeps=physics.get("substeps_per_frame", 10),
        iterations=physics.get("solver_iterations", 10)
    )

    # Step 4: Create camera
    camera_settings = params.get("camera_settings", {{}})
    setup_camera(
        location=camera_settings.get("location", (7.0, -7.0, 5.0)),
        rotation=camera_settings.get("rotation", (63.0, 0.0, 45.0)),
        focal_length=camera_settings.get("focal_length", 50.0)
    )

    # Step 5: Setup lighting
    light_settings = params.get("lighting_settings", {{}})
    setup_lighting(
        light_type=light_settings.get("type", "SUN"),
        energy=light_settings.get("energy", 1.5),
        location=light_settings.get("location", (5.0, 5.0, 10.0)),
        rotation=light_settings.get("rotation", (45.0, 0.0, 45.0))
    )

    # Step 6: Create objects with physics
    for obj_def in params.get("objects", []):
        obj_type = obj_def.get("object_type", "cube")
        count = obj_def.get("count", 1)
        is_static = obj_def.get("is_static", False)
        scale = obj_def.get("scale", 1.0)

        # Get physics properties
        physics_props = obj_def.get("physics_properties", {{}})

        # Create material
        material_name = obj_def.get("material", "default")
        mat_color = obj_def.get("color", (0.8, 0.5, 0.3, 1.0))
        material = create_material(material_name, color=mat_color)

        # Create objects
        for i in range(count):
            # Calculate position (spread objects in grid)
            if is_static:
                location = obj_def.get("position", (0, 0, 0))
            else:
                # Grid layout for multiple objects
                grid_size = int(math.ceil(math.sqrt(count)))
                x = (i % grid_size) * 2.5 * scale - (grid_size * 1.25 * scale)
                y = (i // grid_size) * 2.5 * scale - (grid_size * 1.25 * scale)
                z = 5.0 + (i * 0.5)  # Stack vertically
                location = (x, y, z)

            # Create object based on type
            if obj_type == "cube":
                obj = create_cube(f"{{obj_def['name']}}_{{i}}", location, scale)
            elif obj_type == "sphere":
                obj = create_sphere(f"{{obj_def['name']}}_{{i}}", location, scale)
            elif obj_type == "plane":
                obj = create_plane(f"{{obj_def['name']}}_{{i}}", location, scale)
            elif obj_type == "cylinder":
                obj = create_cylinder(f"{{obj_def['name']}}_{{i}}", location, scale)
            else:
                obj = create_cube(f"{{obj_def['name']}}_{{i}}", location, scale)

            # Apply material
            apply_material(obj, material)

            # Add rigid body physics
            body_type = 'PASSIVE' if is_static else 'ACTIVE'

            # Calculate mass from density and volume
            density = physics_props.get("density", 1000)
            volume = (scale ** 3)  # Approximate volume
            mass = density * volume / 1000  # kg

            add_rigid_body(
                obj,
                body_type=body_type,
                mass=mass,
                friction=physics_props.get("friction", 0.5),
                restitution=physics_props.get("restitution", 0.4),
                linear_damping=physics_props.get("linear_damping", 0.04),
                angular_damping=physics_props.get("angular_damping", 0.10),
                collision_shape=physics_props.get("collision_shape", "CONVEX_HULL"),
                collision_margin=physics_props.get("collision_margin", 0.001)
            )

    # Step 7: Bake simulation
    bake_rigid_body_simulation()

    # Step 8: Save file
    output_path = params.get("output_path", "/tmp/simulation.blend")
    save_blend_file(output_path)

    print("Rigid body simulation complete!")
'''

    return rigid_body_code
