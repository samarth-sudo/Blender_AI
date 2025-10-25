"""
Example script demonstrating the Blender AI Simulation Generator.

This shows how to use the system to generate simulations from natural language.
"""

import asyncio
from pathlib import Path

from src import SimulationOrchestrator
from src.utils.logger import format_success, format_info, format_error, format_warning


def progress_callback(step: str, progress: float):
    """Callback to display progress."""
    bar_length = 30
    filled = int(bar_length * progress)
    bar = '█' * filled + '░' * (bar_length - filled)
    print(f"\r[{bar}] {progress:.0%} - {step}", end='', flush=True)


def main():
    """Run example simulations."""
    print("="*70)
    print("  BLENDER AI SIMULATION GENERATOR - Example Script")
    print("="*70)
    print()

    # Initialize orchestrator
    print(format_info("Initializing orchestrator..."))
    orchestrator = SimulationOrchestrator()

    # Check system readiness
    print(format_info("Checking system readiness..."))
    is_ready, issues = orchestrator.check_system_ready()

    if not is_ready:
        print(format_error("System not ready:"))
        for issue in issues:
            print(f"  - {issue}")
        print()
        print("Please fix these issues and try again.")
        return

    print(format_success("System ready!"))
    print()

    # Example simulations
    examples = [
        {
            "name": "Simple Rigid Body",
            "prompt": "Create 10 wooden blocks falling on a concrete floor",
            "description": "Basic rigid body physics simulation"
        },
        {
            "name": "Smoke Simulation",
            "prompt": "Smoke rising from a sphere",
            "description": "Fluid smoke simulation"
        },
        {
            "name": "Complex Scene",
            "prompt": "20 metal spheres bouncing on a rubber surface",
            "description": "Complex rigid body with different materials"
        }
    ]

    # Let user choose
    print("Available example simulations:")
    print()
    for i, example in enumerate(examples, 1):
        print(f"{i}. {example['name']}")
        print(f"   {example['description']}")
        print(f"   Prompt: \"{example['prompt']}\"")
        print()

    choice = input("Select simulation (1-3, or 0 for custom): ").strip()

    if choice == "0":
        custom_prompt = input("Enter your simulation description: ").strip()
        if not custom_prompt:
            print(format_error("No prompt provided"))
            return
        selected = {"name": "Custom", "prompt": custom_prompt}
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(examples):
                selected = examples[idx]
            else:
                print(format_error("Invalid selection"))
                return
        except ValueError:
            print(format_error("Invalid input"))
            return

    print()
    print("="*70)
    print(f"Generating: {selected['name']}")
    print(f"Prompt: \"{selected['prompt']}\"")
    print("="*70)
    print()

    # Estimate time
    print(format_info("Estimating generation time..."))
    estimated_time = orchestrator.estimate_generation_time(selected['prompt'])
    print(f"Estimated time: ~{estimated_time} seconds")
    print()

    # Generate simulation
    print(format_info("Starting generation..."))
    print()

    try:
        result = orchestrator.generate_simulation(
            user_prompt=selected['prompt'],
            progress_callback=progress_callback
        )

        # Clear progress bar
        print()
        print()

        # Display results
        if result.success:
            print(format_success("SIMULATION GENERATED SUCCESSFULLY!"))
            print()
            print(f"Output file: {result.blend_file}")
            print(f"Total time: {result.total_time_seconds:.1f} seconds")
            print()

            # Quality metrics
            if result.quality_metrics:
                print("Quality Metrics:")
                print(f"  Overall Score: {result.quality_metrics.quality_score:.2f}/1.0")
                print(f"  Object Count: {'✓' if result.quality_metrics.object_count_correct else '✗'}")
                print(f"  Physics Setup: {'✓' if result.quality_metrics.has_physics_setup else '✗'}")
                print(f"  Camera: {'✓' if result.quality_metrics.has_camera else '✗'}")
                print(f"  Lighting: {'✓' if result.quality_metrics.has_lighting else '✗'}")

                if result.quality_metrics.issues:
                    print()
                    print(format_warning("Issues found:"))
                    for issue in result.quality_metrics.issues:
                        print(f"  - {issue}")

            print()

            # Agent times
            print("Agent Execution Times:")
            for agent, time in result.agent_times.items():
                print(f"  {agent}: {time:.2f}s")

            print()
            print(f"To view the simulation, open in Blender:")
            print(f"  blender {result.blend_file}")

        else:
            print(format_error("SIMULATION GENERATION FAILED"))
            print()
            if result.errors:
                print("Errors:")
                for error in result.errors:
                    print(f"  - {error}")

            if result.warnings:
                print()
                print("Warnings:")
                for warning in result.warnings:
                    print(f"  - {warning}")

    except KeyboardInterrupt:
        print()
        print(format_warning("Generation cancelled by user"))

    except Exception as e:
        print()
        print(format_error(f"Unexpected error: {str(e)}"))
        import traceback
        traceback.print_exc()

    print()
    print("="*70)


if __name__ == "__main__":
    main()
