# 🚀 Quick Start Guide - Blender AI Simulation Generator

Get up and running in 5 minutes!

---

## Prerequisites

1. **Python 3.10+**
   ```bash
   python3 --version  # Should be 3.10 or higher
   ```

2. **Blender 4.0+** installed and in PATH
   ```bash
   blender --version  # Should show Blender 4.0+
   ```

   **Don't have Blender?**
   - macOS: `brew install --cask blender`
   - Linux: `sudo apt install blender`
   - Windows: Download from [blender.org](https://www.blender.org)

3. **Claude API Key** from [Anthropic](https://console.anthropic.com/)

---

## Installation (2 minutes)

```bash
# 1. Navigate to project
cd Blender_AI

# 2. Create virtual environment
python3 -m venv venv

# 3. Activate virtual environment
# macOS/Linux:
source venv/bin/activate
# Windows:
# venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure environment
cp .env.example .env

# 6. Edit .env and add your API key
# On macOS/Linux:
nano .env
# On Windows:
# notepad .env

# Add this line:
CLAUDE_API_KEY=your_anthropic_api_key_here
```

---

## Quick Test (1 minute)

### Option 1: Command Line

```bash
python example.py
```

Select option 1 (Simple Rigid Body) and watch the magic happen!

### Option 2: Python Script

```python
from src import SimulationOrchestrator

orchestrator = SimulationOrchestrator()

# Check system is ready
is_ready, issues = orchestrator.check_system_ready()
if not is_ready:
    print(f"Issues: {issues}")
    exit(1)

# Generate simulation
result = orchestrator.generate_simulation(
    "10 wooden blocks falling on a concrete floor"
)

if result.success:
    print(f"✅ Success! File: {result.blend_file}")
    print(f"Quality: {result.quality_metrics.quality_score:.2f}/1.0")
    print(f"Time: {result.total_time_seconds:.1f}s")
else:
    print(f"❌ Failed: {result.errors}")
```

### Option 3: Web Interface

```bash
# Start the web server
cd web
python main.py

# Then open your browser to:
# http://localhost:8000
```

---

## Usage Examples

### Simple Rigid Body

```python
result = orchestrator.generate_simulation(
    "20 wooden blocks falling and stacking"
)
```

**Expected Output:**
- Quality: ~0.90/1.0
- Time: ~30 seconds
- File: `.blend` file ready to open in Blender

### Smoke Simulation

```python
result = orchestrator.generate_simulation(
    "Smoke rising slowly from a sphere"
)
```

**Expected Output:**
- Quality: ~0.75/1.0
- Time: ~60 seconds (fluid simulations are slower)

### With Refinement

```python
result = orchestrator.generate_simulation(
    "15 metal spheres bouncing on glass floor",
    enable_refinement=True,
    max_refinement_iterations=3
)
```

**What Refinement Does:**
- Automatically improves quality if below 0.9
- Retries with adjusted parameters
- Can take 2-3x longer but higher quality

### With Progress Tracking

```python
def show_progress(step, progress):
    print(f"[{progress:.0%}] {step}")

result = orchestrator.generate_simulation(
    "Your prompt here",
    progress_callback=show_progress
)
```

---

## Viewing Your Simulation

Once generated, open the `.blend` file in Blender:

```bash
# Find your file location from the result
blender /tmp/blender_simulations/simulation_TIMESTAMP.blend

# In Blender:
# 1. Press SPACE to play the simulation
# 2. Use mouse to rotate view
# 3. Scroll to zoom in/out
```

---

## Testing

Run the test suite to verify everything works:

```bash
# Run all tests
pytest tests/ -v

# Run specific test categories
pytest tests/test_agents.py -v  # Unit tests
pytest tests/test_integration.py -v  # Integration tests

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

---

## Common Issues

### Issue 1: "Blender not found"

**Solution:**
```bash
# Check if Blender is in PATH
which blender  # macOS/Linux
where blender  # Windows

# If not found, add to PATH or set explicitly:
# In .env file:
BLENDER_EXECUTABLE=/path/to/blender
```

### Issue 2: "Claude API rate limit"

**Solution:**
Wait a few seconds between requests, or adjust in `config/config.yaml`:
```yaml
agents:
  max_retries: 5
  retry_delay_seconds: 3
```

### Issue 3: "Quality score too low"

**Solution:**
Enable refinement:
```python
result = orchestrator.generate_simulation(
    prompt,
    enable_refinement=True  # Automatically improves quality
)
```

### Issue 4: "Generation too slow"

**Causes & Solutions:**
- **High object count (>100 objects)**: Reduce count or expect longer times
- **Fluid simulations**: These are inherently slow. Try lower resolution:
  - Edit the plan manually before code generation
- **Complex materials**: Some materials require more computation

---

## What to Try Next

### 1. Explore Different Simulation Types

```python
# Rigid body physics
"30 cubes stacking into a tower"

# Fluid smoke
"Dark smoke rising from multiple emitters"

# Fluid fire
"Fire spreading from a small flame"

# Cloth physics
"A red cloth draping over a sphere"

# Multiple materials
"5 glass marbles, 3 wooden blocks, 2 metal cylinders on rubber mat"
```

### 2. Use the Web Interface

```bash
cd web
python main.py

# Open http://localhost:8000
# - Type your prompt
# - Watch real-time progress
# - Download the result
```

### 3. Explore Available Materials

```python
materials = orchestrator.list_available_materials()

print(f"Woods: {materials['woods']}")
# Output: ['wood_pine', 'wood_oak', 'wood_balsa', ...]

print(f"Metals: {materials['metals']}")
# Output: ['metal_steel', 'metal_aluminum', 'metal_copper', ...]
```

### 4. Check Pipeline Stats

```python
stats = orchestrator.get_pipeline_stats()

for agent, agent_stats in stats.items():
    print(f"{agent}: {agent_stats['average_time']:.2f}s average")
```

---

## Next Steps

1. **Read the Full Documentation**
   - API Reference: `docs/API.md`
   - Implementation Status: `IMPLEMENTATION_STATUS.md`

2. **Try the Test Scenarios**
   - See `tests/test_integration.py` for 10+ example scenarios

3. **Customize Configuration**
   - Edit `config/config.yaml` for global settings
   - Edit `config/materials.yaml` to add custom materials

4. **Integrate into Your Project**
   ```python
   from src import SimulationOrchestrator

   orch = SimulationOrchestrator(output_dir="/your/custom/dir")
   result = orch.generate_simulation("your prompt")
   ```

---

## Performance Expectations

| Simulation Type | Object Count | Typical Time | Quality Score |
|----------------|--------------|--------------|---------------|
| Simple Rigid Body | 5-20 | 20-40s | 0.85-0.95 |
| Complex Rigid Body | 20-50 | 40-90s | 0.80-0.90 |
| Smoke/Fire | 1-5 emitters | 60-120s | 0.70-0.85 |
| Cloth | 1-2 fabrics | 60-90s | 0.75-0.85 |

**Note:** Times are approximate and depend on:
- Your machine specs
- Blender version
- Frame count (default 150-250 frames)
- Physics resolution settings

---

## Support

**Got issues?**
1. Check `logs/blender_ai.log` for detailed logs
2. Run with verbose mode: `python example.py` (logs to console)
3. Test individual agents: See `tests/test_agents.py` for examples

**Want to contribute?**
1. Fork the repo
2. Add your feature or fix
3. Write tests
4. Submit a PR

---

## Summary

You now have a **production-ready AI system** that can:
- ✅ Parse natural language into simulations
- ✅ Generate physically accurate Blender code
- ✅ Execute simulations automatically
- ✅ Validate quality
- ✅ Improve results through refinement
- ✅ Track progress in real-time
- ✅ Serve via web interface

**Total setup time: ~5 minutes**
**First simulation: ~30 seconds**

**Ready to create amazing simulations!** 🎨🚀

---

For detailed information, see:
- `README.md` - Project overview
- `docs/API.md` - Complete API reference
- `IMPLEMENTATION_STATUS.md` - Technical details
- `tests/` - Example test cases
