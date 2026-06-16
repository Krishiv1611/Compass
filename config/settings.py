import json
import os
from pathlib import Path
from typing import Any

# Default configuration
DEFAULT_CONFIG = {
    "theme": "default",
    "max_results": 50,
    "safety_mode": "auto",
}

class SettingsManager:
    def __init__(self):
        self.config_dir = Path.home() / ".compass"
        self.config_file = self.config_dir / "config.json"
        self.config = self._load()

    def _load(self) -> dict[str, Any]:
        """Load settings from the JSON config file."""
        if not self.config_file.exists():
            return DEFAULT_CONFIG.copy()
        
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                # Merge with defaults to ensure all keys exist
                return {**DEFAULT_CONFIG, **loaded}
        except (json.JSONDecodeError, IOError):
            return DEFAULT_CONFIG.copy()

    def save(self):
        """Save settings to the JSON config file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        """Set a configuration value and save."""
        # Optional: Add type casting based on defaults
        if key in DEFAULT_CONFIG:
            default_val = DEFAULT_CONFIG[key]
            if isinstance(default_val, int):
                value = int(value)
            elif isinstance(default_val, bool):
                value = str(value).lower() in ("true", "1", "yes", "y")
        
        self.config[key] = value
        self.save()

    def get_all(self) -> dict[str, Any]:
        """Get all configuration values."""
        return self.config.copy()

# Singleton instance
settings = SettingsManager()
