import json
from pathlib import Path
from typing import Any
import tomli_w

from config.loader import load_config, DEFAULT_CONFIG, _unflatten

class SettingsManager:
    def __init__(self):
        self.global_dir = Path.home() / ".compass"
        self.project_dir = Path.cwd() / ".compass"
        self.global_json = self.global_dir / "config.json"
        self.global_toml = self.global_dir / "config.toml"
        self.project_toml = self.project_dir / "config.toml"
        
        self._migrate_json()
        self.config = load_config()

    def _migrate_json(self):
        """Migrate existing config.json to config.toml if needed."""
        if self.global_json.exists() and not self.global_toml.exists():
            try:
                with open(self.global_json, "r", encoding="utf-8") as f:
                    old_config = json.load(f)
                
                # Map old keys to new keys if needed
                new_config = {}
                if "theme" in old_config:
                    new_config["theme"] = old_config["theme"]
                if "max_results" in old_config:
                    new_config["tools.max_results"] = old_config["max_results"]
                if "safety_mode" in old_config:
                    new_config["safety.mode"] = old_config["safety_mode"]
                
                unflattened = _unflatten(new_config)
                with open(self.global_toml, "wb") as f:
                    tomli_w.dump(unflattened, f)
                
                # We can leave the old json file as backup or remove it
                self.global_json.unlink(missing_ok=True)
            except Exception as e:
                print(f"[config] Warning: Failed to migrate config.json: {e}")

    def save(self):
        """Save settings to the project config TOML file."""
        self.project_dir.mkdir(parents=True, exist_ok=True)
        
        # Save all current settings to project TOML
        unflattened = _unflatten(self.config)
        with open(self.project_toml, "wb") as f:
            tomli_w.dump(unflattened, f)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        """Set a configuration value and save."""
        if key in DEFAULT_CONFIG:
            default_val = DEFAULT_CONFIG[key]
            if isinstance(default_val, int):
                try:
                    value = int(value)
                except ValueError:
                    pass
            elif isinstance(default_val, bool):
                value = str(value).lower() in ("true", "1", "yes", "y")
        
        self.config[key] = value
        self.save()

    def get_all(self) -> dict[str, Any]:
        """Get all configuration values."""
        return self.config.copy()

# Singleton instance
settings = SettingsManager()
