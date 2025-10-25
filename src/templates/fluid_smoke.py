"""
Fluid smoke/fire simulation template for Blender.

Fluid simulations in Blender use the Mantaflow solver to create:
- Smoke rising from objects
- Fire and flames
- Gas dynamics

Key concepts:
- Domain: The bounding box where simulation happens
- Flow: Objects that emit smoke/fire
- Resolution: Higher = more detail but slower

This is more complex than rigid body physics!
"""

from src.templates.base import get_complete_base_template


def get_fluid_domain_setup() -> str:
    """
    Get code for creating a fluid domain.

    The domain is the container where the fluid simulation happens.
    Think of it as the "simulation space".

    Returns:
        Python code string
    """
    return '''
def setup_fluid_domain(location=(0, 0, 5), scale=(10, 10, 10), resolution_max=128,
                       domain_type='GAS', time_scale=1.0, use_adaptive=True):
    """
    Create a fluid simulation domain.

    Args:
        location: Domain center position
        scale: Domain size (x, y, z) in meters
        resolution_max: Maximum resolution (32-512, higher=more detail)
        domain_type: 'GAS' for smoke/fire, 'LIQUID' for water
        time_scale: Speed of simulation (1.0=normal, 2.0=2x speed)
        use_adaptive: Use adaptive domain (follows smoke movement)

    The domain contains the entire simulation. Smoke/fire stays inside it.

    Resolution guide:
    - 32-64: Preview quality (fast)
    - 128: Good quality (default)
    - 256: High quality (slow)
    - 512: Production quality (very slow)
    """
    # Create a cube as the domain
    bpy.ops.mesh.primitive_cube_add(location=location, scale=scale)
    domain = bpy.context.active_object
    domain.name = "FluidDomain"

    # Add fluid modifier
    bpy.ops.object.modifier_add(type='FLUID')
    domain.modifiers["Fluid"].fluid_type = 'DOMAIN'

    # Configure domain settings
    domain_settings = domain.modifiers["Fluid"].domain_settings
    domain_settings.domain_type = domain_type

    # Resolution (higher = more detail, longer bake time)
    domain_settings.resolution_max = resolution_max

    # Time scale (simulation speed)
    domain_settings.time_scale = time_scale

    # Adaptive domain follows the smoke (improves performance)
    if use_adaptive:
        domain_settings.use_adaptive_domain = True
        domain_settings.additional_res = 6  # Extra cells around smoke
        domain_settings.margin = 12  # Safety margin

    # Cache settings
    domain_settings.cache_directory = "/tmp/blender_fluid_cache"
    domain_settings.cache_frame_start = bpy.context.scene.frame_start
    domain_settings.cache_frame_end = bpy.context.scene.frame_end

    # Visual settings for smoke
    if domain_type == 'GAS':
        domain_settings.use_noise = True  # Add turbulence detail
        domain_settings.noise_scale = 2
        domain_settings.noise_strength = 1.0

    print(f"Fluid domain created: resolution={resolution_max}, type={domain_type}")
    return domain
'''


def get_fluid_flow_setup() -> str:
    """
    Get code for creating smoke/fire emitters.

    Flow objects emit smoke or fire into the domain.

    Returns:
        Python code string
    """
    return '''
def add_fluid_flow(obj, flow_type='SMOKE', flow_behavior='INFLOW',
                   density=1.0, temperature=1.0, velocity=0.0):
    """
    Make an object emit smoke or fire.

    Args:
        obj: Object to emit from
        flow_type: 'SMOKE', 'FIRE', 'BOTH', or 'LIQUID'
        flow_behavior: 'INFLOW' (continuous) or 'GEOMETRY' (from surface)
        density: Smoke density multiplier (higher = thicker smoke)
        temperature: Temperature difference (affects buoyancy)
        velocity: Initial velocity of emitted fluid

    Flow Types:
    - SMOKE: Just smoke (gray/white)
    - FIRE: Fire with smoke (orange/yellow flames + black smoke)
    - BOTH: Smoke and fire separately controlled
    - LIQUID: For water simulations

    Flow Behavior:
    - INFLOW: Continuously emits from inside the object
    - GEOMETRY: Uses object surface (for moving emitters)
    """
    # Select the object
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # Add fluid modifier
    bpy.ops.object.modifier_add(type='FLUID')
    obj.modifiers["Fluid"].fluid_type = 'FLOW'

    # Configure flow settings
    flow_settings = obj.modifiers["Fluid"].flow_settings
    flow_settings.flow_type = flow_type
    flow_settings.flow_behavior = flow_behavior

    # Smoke/Fire properties
    flow_settings.density = density
    flow_settings.temperature = temperature
    flow_settings.velocity_factor = velocity

    # For fire, configure flame properties
    if flow_type in ['FIRE', 'BOTH']:
        flow_settings.fuel_amount = 1.5  # How much fuel (affects flame size)
        flow_settings.smoke_color = (0.1, 0.1, 0.1)  # Black smoke from fire

    print(f"Added fluid flow to {obj.name}: type={flow_type}")

    # Deselect
    obj.select_set(False)
'''


def get_fluid_bake() -> str:
    """
    Get code for baking fluid simulation.

    Fluid simulations are computationally expensive and must be baked.

    Returns:
        Python code string
    """
    return '''
def bake_fluid_simulation(domain):
    """
    Bake the fluid simulation.

    This pre-calculates the fluid dynamics for all frames.
    WARNING: This can take a LONG time for high resolutions!

    Args:
        domain: The fluid domain object

    Baking process:
    1. Calculates smoke/fire movement frame-by-frame
    2. Stores voxel data in cache files
    3. Can take minutes to hours depending on resolution
    """
    print("Baking fluid simulation...")
    print("This may take several minutes for resolution > 128")

    # Select domain
    bpy.context.view_layer.objects.active = domain
    domain.select_set(True)

    # Get domain settings
    domain_settings = domain.modifiers["Fluid"].domain_settings

    # Start bake
    bpy.ops.fluid.bake_all()

    print("Fluid simulation baked successfully")
    print(f"Cache location: {domain_settings.cache_directory}")

    # Deselect
    domain.select_set(False)
'''


def get_fluid_materials() -> str:
    """
    Get code for creating smoke/fire materials.

    Returns:
        Python code string
    """
    return '''
def create_smoke_material(domain, density_color=(1.0, 1.0, 1.0), absorption=1.0):
    """
    Create a material for smoke visualization.

    Args:
        domain: The fluid domain object
        density_color: RGB color of smoke (1,1,1=white, 0.5,0.5,0.5=gray)
        absorption: How much light is absorbed (0=transparent, 1=opaque)
    """
    # Create new material
    mat = bpy.data.materials.new(name="SmokeMaterial")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Clear default nodes
    nodes.clear()

    # Create nodes for smoke volume rendering
    output = nodes.new(type='ShaderNodeOutputMaterial')
    volume_scatter = nodes.new(type='ShaderNodeVolumeScatter')
    volume_absorption = nodes.new(type='ShaderNodeVolumeAbsorption')
    add_shader = nodes.new(type='ShaderNodeAddShader')
    attribute = nodes.new(type='ShaderNodeAttribute')

    # Configure attribute node to read density
    attribute.attribute_name = 'density'

    # Set colors
    volume_scatter.inputs['Color'].default_value = (*density_color, 1.0)

    # Connect nodes
    links.new(attribute.outputs['Fac'], volume_scatter.inputs['Density'])
    links.new(attribute.outputs['Fac'], volume_absorption.inputs['Density'])
    links.new(volume_scatter.outputs['Volume'], add_shader.inputs[0])
    links.new(volume_absorption.outputs['Volume'], add_shader.inputs[1])
    links.new(add_shader.outputs['Shader'], output.inputs['Volume'])

    # Apply material to domain
    domain.data.materials.clear()
    domain.data.materials.append(mat)

    print("Smoke material created")
'''


def get_fluid_smoke_template() -> str:
    """
    Get complete fluid smoke simulation template.

    Returns:
        Complete Python code string
    """
    base = get_complete_base_template()

    fluid_code = f'''{base}

{get_fluid_domain_setup()}

{get_fluid_flow_setup()}

{get_fluid_bake()}

{get_fluid_materials()}


def create_fluid_smoke_simulation(params):
    """
    Create a complete smoke/fire simulation.

    Args:
        params: Dictionary with simulation parameters
    """
    # Step 1: Clear scene
    clear_scene()

    # Step 2: Setup scene
    setup_scene(
        frame_start=1,
        frame_end=params.get("duration_frames", 150),
        frame_rate=params.get("frame_rate", 24)
    )

    # Step 3: Create camera
    camera_settings = params.get("camera_settings", {{}})
    setup_camera(
        location=camera_settings.get("location", (10.0, -10.0, 8.0)),
        rotation=camera_settings.get("rotation", (60.0, 0.0, 45.0)),
        focal_length=camera_settings.get("focal_length", 50.0)
    )

    # Step 4: Setup lighting (important for volume rendering)
    light_settings = params.get("lighting_settings", {{}})
    setup_lighting(
        light_type="POINT",  # Point light works well for smoke
        energy=1000.0,  # Need strong light for volumes
        location=(5.0, -5.0, 10.0)
    )

    # Step 5: Create fluid domain
    physics = params.get("physics_settings", {{}})
    domain = setup_fluid_domain(
        location=(0, 0, 5),
        scale=(10, 10, 10),
        resolution_max=physics.get("resolution_max", 128),
        domain_type='GAS',
        time_scale=physics.get("time_scale", 1.0),
        use_adaptive=True
    )

    # Step 6: Create emitter objects
    emitters = []
    for obj_def in params.get("objects", []):
        if obj_def.get("is_emitter", True):
            obj_type = obj_def.get("object_type", "sphere")
            location = obj_def.get("position", (0, 0, 1))
            scale = obj_def.get("scale", 1.0)

            # Create emitter object
            if obj_type == "sphere":
                emitter = create_sphere(f"{{obj_def['name']}}", location, scale)
            elif obj_type == "cube":
                emitter = create_cube(f"{{obj_def['name']}}", location, scale)
            else:
                emitter = create_sphere(f"{{obj_def['name']}}", location, scale)

            # Add fluid flow
            flow_type = obj_def.get("flow_type", "SMOKE")
            add_fluid_flow(
                emitter,
                flow_type=flow_type,
                flow_behavior='INFLOW',
                density=obj_def.get("density", 1.0),
                temperature=obj_def.get("temperature", 1.0),
                velocity=obj_def.get("velocity", 0.0)
            )

            emitters.append(emitter)

    # Step 7: Create smoke material
    create_smoke_material(domain, density_color=(0.8, 0.8, 0.8), absorption=0.5)

    # Step 8: Bake simulation
    bake_fluid_simulation(domain)

    # Step 9: Save file
    output_path = params.get("output_path", "/tmp/fluid_smoke_simulation.blend")
    save_blend_file(output_path)

    print("Fluid smoke simulation complete!")


# Example usage
if __name__ == "__main__":
    example_params = {{
        "duration_frames": 150,
        "physics_settings": {{
            "resolution_max": 128,
            "time_scale": 1.0
        }},
        "objects": [
            {{
                "name": "smoke_emitter",
                "object_type": "sphere",
                "position": (0, 0, 1),
                "scale": 0.5,
                "is_emitter": True,
                "flow_type": "SMOKE",
                "density": 1.5,
                "temperature": 2.0,
                "velocity": 0.5
            }}
        ],
        "output_path": "/tmp/smoke_simulation.blend"
    }}

    create_fluid_smoke_simulation(example_params)
'''

    return fluid_code
