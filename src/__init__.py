"""
Blender AI Simulation Generator

A production-ready multi-agent system for generating Blender simulations
from natural language descriptions using Claude AI.
"""

__version__ = "0.1.0"
__author__ = "Blender AI Team"

from src.orchestrator.orchestrator import SimulationOrchestrator
from src.models.schemas import (
    SimulationPlan,
    SimulationResult,
    SimulationType,
    PhysicsSettings,
)

__all__ = [
    "SimulationOrchestrator",
    "SimulationPlan",
    "SimulationResult",
    "SimulationType",
    "PhysicsSettings",
]
