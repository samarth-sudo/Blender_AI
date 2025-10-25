"""
Configuration management for Blender AI Simulation Generator.

Loads settings from:
1. config/config.yaml (base configuration)
2. config/materials.yaml (physics properties)
3. Environment variables (.env file)
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings


# Load environment variables from .env file
load_dotenv()

# Determine project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


class ClaudeSettings(BaseSettings):
    """Claude API configuration."""
    api_key: str = Field(default="", alias="CLAUDE_API_KEY")
    model: str = "claude-sonnet-4-5-20250929"
    max_tokens: int = 4096
    temperature: float = 0.2
    timeout_seconds: int = 60

    class Config:
        env_file = ".env"
        extra = "allow"


class BlenderSettings(BaseSettings):
    """Blender execution configuration."""
    executable: str = Field(default="blender", alias="BLENDER_EXECUTABLE")
    timeout_seconds: int = Field(default=300, alias="BLENDER_TIMEOUT_SECONDS")
    background_mode: bool = True
    enable_gpu: bool = False
    render_engine: str = "CYCLES"

    class Config:
        env_file = ".env"
        extra = "allow"


class PathSettings(BaseSettings):
    """File system paths."""
    output_dir: Path = Field(default="/tmp/blender_simulations", alias="OUTPUT_DIR")
    cache_dir: Path = Field(default="/tmp/blender_cache", alias="CACHE_DIR")
    log_file: Path = Field(default="logs/blender_ai.log", alias="LOG_FILE")

    class Config:
        env_file = ".env"
        extra = "allow"


class Config:
    """
    Central configuration manager.

    Usage:
        config = Config()
        print(config.claude.api_key)
        print(config.materials["wood_pine"]["density"])
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration.

        Args:
            config_path: Optional path to config.yaml. Defaults to config/config.yaml
        """
        self.config_path = config_path or (CONFIG_DIR / "config.yaml")
        self.materials_path = CONFIG_DIR / "materials.yaml"

        # Load configurations
        self._load_yaml_config()
        self._load_materials()
        self._initialize_settings()
        self._ensure_directories()

    def _load_yaml_config(self) -> None:
        """Load main configuration from YAML."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, 'r') as f:
            self.yaml_config: Dict[str, Any] = yaml.safe_load(f)

    def _load_materials(self) -> None:
        """Load materials database from YAML."""
        if not self.materials_path.exists():
            raise FileNotFoundError(f"Materials file not found: {self.materials_path}")

        with open(self.materials_path, 'r') as f:
            materials_data = yaml.safe_load(f)
            self.materials: Dict[str, Dict[str, Any]] = materials_data.get("materials", {})
            self.fluids: Dict[str, Dict[str, Any]] = materials_data.get("fluids", {})
            self.default_material: Dict[str, Any] = materials_data.get("default", {})

    def _initialize_settings(self) -> None:
        """Initialize Pydantic settings objects."""
        # Load from YAML and override with environment variables
        yaml_llm = self.yaml_config.get("llm", {})
        yaml_blender = self.yaml_config.get("blender", {})

        self.claude = ClaudeSettings(
            model=yaml_llm.get("model", "claude-sonnet-4-5-20250929"),
            max_tokens=yaml_llm.get("max_tokens", 4096),
            temperature=yaml_llm.get("temperature", 0.2),
            timeout_seconds=yaml_llm.get("timeout_seconds", 60),
        )

        self.blender = BlenderSettings(
            timeout_seconds=yaml_blender.get("timeout_seconds", 300),
            background_mode=yaml_blender.get("background_mode", True),
            enable_gpu=yaml_blender.get("enable_gpu", False),
            render_engine=yaml_blender.get("render_engine", "CYCLES"),
        )

        self.paths = PathSettings()

        # Store other settings
        self.agents = self.yaml_config.get("agents", {})
        self.simulations = self.yaml_config.get("simulations", {})
        self.quality = self.yaml_config.get("quality", {})
        self.errors = self.yaml_config.get("errors", {})
        self.output = self.yaml_config.get("output", {})
        self.logging = self.yaml_config.get("logging", {})

    def _ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.paths.output_dir.mkdir(parents=True, exist_ok=True)
        self.paths.cache_dir.mkdir(parents=True, exist_ok=True)

        # Create logs directory
        log_dir = Path(self.paths.log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)

    def get_material(self, material_name: str) -> Dict[str, Any]:
        """
        Get material properties by name.

        Args:
            material_name: Name of material (e.g., "wood_pine", "metal_steel")

        Returns:
            Dictionary of material properties

        Raises:
            KeyError: If material not found
        """
        material_name = material_name.lower().replace(" ", "_")

        if material_name in self.materials:
            return self.materials[material_name]

        # Try to find partial match
        for key in self.materials:
            if material_name in key or key in material_name:
                return self.materials[key]

        # Return default material if not found
        return self.default_material

    def get_fluid(self, fluid_name: str) -> Dict[str, Any]:
        """Get fluid properties by name."""
        fluid_name = fluid_name.lower()
        return self.fluids.get(fluid_name, self.fluids.get("water", {}))

    def get_simulation_defaults(self, sim_type: str) -> Dict[str, Any]:
        """Get default parameters for a simulation type."""
        return self.simulations.get(sim_type, {})

    def reload(self) -> None:
        """Reload configuration from files."""
        self._load_yaml_config()
        self._load_materials()
        self._initialize_settings()


# Global configuration instance
_config_instance: Optional[Config] = None


def get_config(reload: bool = False) -> Config:
    """
    Get the global configuration instance (singleton pattern).

    Args:
        reload: Force reload configuration from files

    Returns:
        Config instance
    """
    global _config_instance

    if _config_instance is None or reload:
        _config_instance = Config()

    return _config_instance


# Convenience functions
def get_claude_config() -> ClaudeSettings:
    """Get Claude API configuration."""
    return get_config().claude


def get_blender_config() -> BlenderSettings:
    """Get Blender configuration."""
    return get_config().blender


def get_material_properties(material_name: str) -> Dict[str, Any]:
    """Get material properties by name."""
    return get_config().get_material(material_name)
