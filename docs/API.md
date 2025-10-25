# API Reference - Blender AI Simulation Generator

Complete API documentation for all components.

---

## Table of Contents

1. [Orchestrator API](#orchestrator-api)
2. [Agent APIs](#agent-apis)
3. [Data Models](#data-models)
4. [Utilities](#utilities)
5. [Configuration](#configuration)

---

## Orchestrator API

### `SimulationOrchestrator`

The main entry point for generating simulations.

#### Constructor

```python
SimulationOrchestrator(
    claude_client: Optional[ClaudeClient] = None,
    output_dir: Optional[Path] = None,
    enable_auto_retry: bool = True
)
```

**Parameters:**
- `claude_client`: Optional Claude API client (creates new if not provided)
- `output_dir`: Directory for output files (defaults to config)
- `enable_auto_retry`: Enable automatic retry on recoverable errors

#### Methods

##### `generate_simulation()`

Generate a complete simulation from natural language.

```python
def generate_simulation(
    user_prompt: str,
    output_path: Optional[str] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None,
    enable_refinement: bool = False,
    max_refinement_iterations: int = 2
) -> SimulationResult
```

**Parameters:**
- `user_prompt`: Natural language description
- `output_path`: Where to save .blend file (auto-generated if not provided)
- `progress_callback`: Optional callback function for progress updates
- `enable_refinement`: Enable quality-based refinement loop
- `max_refinement_iterations`: Maximum refinement attempts

**Returns:** `SimulationResult` object

**Example:**
```python
orchestrator = SimulationOrchestrator()

result = orchestrator.generate_simulation(
    "20 wooden blocks falling on concrete floor",
    enable_refinement=True
)

if result.success:
    print(f"Simulation saved to: {result.blend_file}")
    print(f"Quality score: {result.quality_metrics.quality_score}")
```

##### `check_system_ready()`

Check if the system is ready to generate simulations.

```python
def check_system_ready() -> Tuple[bool, List[str]]
```

**Returns:** Tuple of (is_ready, list_of_issues)

**Example:**
```python
is_ready, issues = orchestrator.check_system_ready()
if not is_ready:
    for issue in issues:
        print(f"Issue: {issue}")
```

##### `list_available_materials()`

Get list of available materials organized by category.

```python
def list_available_materials() -> Dict[str, List[str]]
```

**Returns:** Dictionary with material categories

**Example:**
```python
materials = orchestrator.list_available_materials()
print(f"Woods: {materials['woods']}")
print(f"Metals: {materials['metals']}")
```

##### `estimate_generation_time()`

Estimate how long generation will take.

```python
def estimate_generation_time(user_prompt: str) -> int
```

**Parameters:**
- `user_prompt`: User's simulation request

**Returns:** Estimated seconds

---

## Agent APIs

### `PlannerAgent`

Parse natural language into structured simulation plan.

```python
from src.agents import PlannerAgent

planner = PlannerAgent()
plan = planner.run("20 cubes falling on a table")

# Access plan properties
print(plan.simulation_type)  # SimulationType.RIGID_BODY
print(plan.objects)  # List of SimulationObject
print(plan.duration_frames)  # int
```

### `PhysicsValidatorAgent`

Enrich plan with realistic material properties.

```python
from src.agents import PhysicsValidatorAgent

validator = PhysicsValidatorAgent()
enriched_plan = validator.run(plan)

# All objects now have physics_properties
for obj in enriched_plan.objects:
    print(f"{obj.name}: density={obj.physics_properties.density}")
```

### `CodeGeneratorAgent`

Generate Blender Python code from plan.

```python
from src.agents import CodeGeneratorAgent

generator = CodeGeneratorAgent()
code = generator.run(enriched_plan, "/tmp/sim.blend")

print(f"Generated {len(code.code)} characters of code")
print(f"Complexity: {code.complexity_score}")
```

### `SyntaxValidatorAgent`

Validate Python code syntax and security.

```python
from src.agents import SyntaxValidatorAgent

validator = SyntaxValidatorAgent()
result = validator.run(code)

if result.is_valid:
    print("Code is valid")
else:
    print(f"Errors: {result.errors}")
```

### `ExecutorAgent`

Execute Blender code in headless mode.

```python
from src.agents import ExecutorAgent

executor = ExecutorAgent()
result = executor.run(code, "/tmp/sim.blend")

if result.success:
    print(f"Simulation saved: {result.blend_file_path}")
    print(f"Execution time: {result.execution_time_seconds}s")
```

### `QualityValidatorAgent`

Inspect and score generated simulations.

```python
from src.agents import QualityValidatorAgent

validator = QualityValidatorAgent()
metrics = validator.run(execution_result, plan)

print(f"Quality score: {metrics.quality_score}")
print(f"Physics setup: {metrics.has_physics_setup}")
print(f"Issues: {metrics.issues}")
```

### `RefinementAgent`

Improve simulation quality iteratively.

```python
from src.agents import RefinementAgent

refiner = RefinementAgent()

# Check if refinement is needed
should_refine, reason = refiner.should_refine(metrics, threshold=0.8)

if should_refine:
    # Get refined plan
    refined_plan = refiner.run(plan, metrics, iteration=1)
```

---

## Data Models

### `SimulationPlan`

Complete specification of a simulation.

```python
from src.models.schemas import SimulationPlan, SimulationType

plan = SimulationPlan(
    simulation_type=SimulationType.RIGID_BODY,
    objects=[...],
    physics_settings=PhysicsSettings(gravity=-9.81),
    duration_frames=250,
    user_prompt="original prompt"
)
```

**Fields:**
- `simulation_type`: Type of simulation (rigid_body, fluid_smoke, etc.)
- `objects`: List of `SimulationObject`
- `physics_settings`: `PhysicsSettings` object
- `camera_settings`: `CameraSettings` object
- `lighting_settings`: `LightingSettings` object
- `duration_frames`: Animation length
- `frame_rate`: Frames per second
- `user_prompt`: Original user input
- `created_at`: Timestamp

### `SimulationObject`

Definition of an object in the simulation.

```python
from src.models.schemas import SimulationObject, ObjectType

obj = SimulationObject(
    name="block",
    object_type=ObjectType.CUBE,
    count=10,
    material="wood",
    scale=1.0,
    is_static=False,
    physics_properties=MaterialProperties(...)
)
```

### `SimulationResult`

Final result from orchestrator.

```python
result: SimulationResult

# Check success
if result.success:
    print(result.blend_file)
    print(result.quality_metrics.quality_score)
    print(result.total_time_seconds)

    # Agent timing breakdown
    for agent, time in result.agent_times.items():
        print(f"{agent}: {time}s")
else:
    print(result.errors)
    print(result.warnings)
```

### `MaterialProperties`

Physics properties for a material.

```python
from src.models.schemas import MaterialProperties

mat = MaterialProperties(
    name="Wood",
    density=600,  # kg/m³
    friction=0.7,
    restitution=0.15,
    linear_damping=0.04,
    angular_damping=0.10,
    collision_shape="BOX",
    collision_margin=0.001
)
```

### `QualityMetrics`

Quality validation results.

```python
metrics: QualityMetrics

print(f"Score: {metrics.quality_score}/1.0")
print(f"Object count correct: {metrics.object_count_correct}")
print(f"Has physics: {metrics.has_physics_setup}")
print(f"Has camera: {metrics.has_camera}")
print(f"Has lighting: {metrics.has_lighting}")

if metrics.issues:
    for issue in metrics.issues:
        print(f"Issue: {issue}")
```

---

## Utilities

### Configuration

```python
from src.utils.config import get_config, get_material_properties

# Get global configuration
config = get_config()

# Access settings
print(config.claude.model)
print(config.blender.executable)
print(config.paths.output_dir)

# Get material properties
props = get_material_properties("wood_pine")
print(f"Density: {props['density']} kg/m³")
```

### Logging

```python
from src.utils.logger import get_logger

logger = get_logger("MyModule")

logger.info("Starting operation", param=value)
logger.success("Operation complete", duration=1.5)
logger.warning("Potential issue detected")
logger.error("Operation failed", exception)
```

### Error Handling

```python
from src.utils.errors import (
    BlenderAIError,
    PlanningError,
    ValidationError,
    ExecutionError,
    QualityError
)

try:
    result = orchestrator.generate_simulation(prompt)
except PlanningError as e:
    print(f"Failed to parse prompt: {e.message}")
    print(f"Suggestion: {e.suggested_action}")
except ExecutionError as e:
    print(f"Blender execution failed: {e.message}")
    print(f"Blender output: {e.blender_output}")
except QualityError as e:
    print(f"Quality too low: {e.quality_score}")
    print(f"Issues: {e.issues}")
```

---

## Configuration

### Environment Variables

```bash
# Required
CLAUDE_API_KEY=your_anthropic_api_key

# Optional
BLENDER_EXECUTABLE=blender
BLENDER_TIMEOUT_SECONDS=300
OUTPUT_DIR=/tmp/blender_simulations
LOG_LEVEL=INFO
```

### config.yaml

```yaml
llm:
  model: "claude-sonnet-4-5-20250929"
  max_tokens: 4096
  temperature: 0.2

blender:
  timeout_seconds: 300
  enable_gpu: false

agents:
  max_retries: 3

quality:
  min_quality_score: 0.8
```

### materials.yaml

Add custom materials:

```yaml
materials:
  my_custom_material:
    name: "My Custom Material"
    density: 1500
    friction: 0.6
    restitution: 0.3
    linear_damping: 0.05
    angular_damping: 0.08
    collision_shape: "CONVEX_HULL"
    collision_margin: 0.001
```

---

## Progress Callbacks

Track generation progress in real-time:

```python
def my_progress_callback(step: str, progress: float):
    """
    Args:
        step: Human-readable step name
        progress: Progress from 0.0 to 1.0
    """
    print(f"[{progress:.0%}] {step}")

result = orchestrator.generate_simulation(
    prompt="10 cubes falling",
    progress_callback=my_progress_callback
)
```

Expected callbacks:
1. Planning (10%)
2. Validating physics (25%)
3. Generating code (40%)
4. Validating syntax (55%)
5. Executing in Blender (70%)
6. Validating quality (90%)
7. Complete (100%)

---

## Best Practices

### 1. Always Check System Ready

```python
is_ready, issues = orchestrator.check_system_ready()
if not is_ready:
    print("System not ready:")
    for issue in issues:
        print(f"  - {issue}")
    exit(1)
```

### 2. Use Progress Callbacks

For long-running operations, always provide progress feedback:

```python
result = orchestrator.generate_simulation(
    prompt,
    progress_callback=lambda s, p: print(f"{s} ({p:.0%})")
)
```

### 3. Enable Refinement for Quality

For important simulations:

```python
result = orchestrator.generate_simulation(
    prompt,
    enable_refinement=True,
    max_refinement_iterations=3
)
```

### 4. Handle Errors Gracefully

```python
try:
    result = orchestrator.generate_simulation(prompt)
    if result.success:
        # Success path
        pass
    else:
        # Handle failure
        for error in result.errors:
            print(f"Error: {error}")
except BlenderAIError as e:
    # Handle known errors
    if e.recoverable:
        # Retry logic
        pass
```

### 5. Monitor Performance

```python
result = orchestrator.generate_simulation(prompt)

if result.success:
    print(f"Total time: {result.total_time_seconds:.1f}s")
    print("Agent breakdown:")
    for agent, time in result.agent_times.items():
        print(f"  {agent}: {time:.1f}s")
```

---

## Common Patterns

### Pattern 1: Batch Generation

```python
prompts = [
    "10 cubes falling",
    "smoke rising from sphere",
    "cloth draping over cube"
]

results = []
for prompt in prompts:
    result = orchestrator.generate_simulation(prompt)
    results.append(result)

# Analyze results
successful = [r for r in results if r.success]
print(f"Success rate: {len(successful)}/{len(results)}")
```

### Pattern 2: Custom Material

```python
# First, check available materials
materials = orchestrator.list_available_materials()
print(f"Available: {materials}")

# Use specific material
result = orchestrator.generate_simulation(
    "5 aluminum spheres rolling down glass ramp"
)
```

### Pattern 3: Quality-Focused Generation

```python
result = orchestrator.generate_simulation(
    prompt,
    enable_refinement=True,
    max_refinement_iterations=5  # Try harder
)

if result.quality_metrics:
    if result.quality_metrics.quality_score < 0.8:
        print("Warning: Quality below threshold")
        print(f"Issues: {result.quality_metrics.issues}")
```

---

## Troubleshooting

### Issue: "Blender not found"

```python
# Check Blender availability
from src.agents import ExecutorAgent

executor = ExecutorAgent()
available, message = executor.check_blender_available()

if not available:
    print(f"Blender issue: {message}")
```

**Solution:** Install Blender and ensure it's in PATH.

### Issue: "Claude API rate limit"

Configure retry settings in `config.yaml`:

```yaml
agents:
  max_retries: 5
  retry_delay_seconds: 3
```

### Issue: "Quality score too low"

Enable refinement:

```python
result = orchestrator.generate_simulation(
    prompt,
    enable_refinement=True
)
```

---

## Type Hints

All APIs use type hints for IDE support:

```python
from src import SimulationOrchestrator
from src.models.schemas import SimulationResult

orchestrator: SimulationOrchestrator = SimulationOrchestrator()
result: SimulationResult = orchestrator.generate_simulation("prompt")

# Full IDE autocomplete and type checking
if result.success:
    file_path: str = result.blend_file
    quality: float = result.quality_metrics.quality_score
```

---

For more examples, see `example.py` and the test suite in `tests/`.
