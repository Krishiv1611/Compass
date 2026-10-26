import os
import json
from pathlib import Path
from typing import Any
import tomli_w

try:
    import tomllib
except ImportError:
    import tomli as tomllib

DEFAULT_CONFIG = {
    # UI
    "theme": "default",
    # Models (per-role overrides: State-of-the-art Open Source)
    "model.planner": "deepseek/deepseek-r1",
    "model.executor": "qwen/qwen-2.5-coder-32b-instruct",
    "model.recovery": "deepseek/deepseek-r1",
    "model.summarizer": "meta-llama/llama-3.3-70b-instruct",
    "model.evaluator": "qwen/qwen-2.5-coder-32b-instruct",
    # Safety
    "safety.mode": "auto",  # auto | yolo | strict
    "safety.blocked_commands": "",  # extra blocked patterns
    # Human-in-the-loop
    "hitl.enabled": True,
    "hitl.auto_approve_safe": True,
    # Tools
    "tools.max_results": 50,
    "tools.shell_timeout": 30,
    "custom_tools.enabled": False,
    "custom_tools.approved_paths": [],
    "hooks.after_edit": [],
    # Context
    "context.summarize_after": 10,  # message count threshold
    "context.loop_max_retries": 3,
    # RAG
    "rag.auto_index": False,
    "rag.chunk_size": 1000,
    # Fast mode
    "fast_mode": False,
    # Orchestration
    "orchestration.enabled": True,
    "orchestration.max_workers": 2,
}


PUBLIC_SETTING_CONSUMERS = {
    "theme": "agent.ui.theme.theme_for_preference",
    "tools.max_results": "agent.tools.search_tools.grep_search",
    "tools.shell_timeout": "agent.tools.shell_tool.shell_execute",
    "context.summarize_after": "agent.graph.routing.needs_compaction",
    "context.loop_max_retries": "agent.loop_detector.is_looping",
    "rag.auto_index": "agent.rag.indexer.index_workspace_if_enabled",
    "rag.chunk_size": "agent.rag.indexer.index_workspace",
    "hitl.enabled": "agent.safety.requires_approval",
    "hitl.auto_approve_safe": "agent.safety.requires_approval",
    "safety.mode": "agent.safety.requires_approval",
    "safety.blocked_commands": "agent.tools.shell_tool.shell_execute",
    "orchestration.enabled": "agent.graph.nodes.planner_node",
    "orchestration.max_workers": "agent.orchestration.coordinator.Coordinator.run",
}


def _flatten(d: dict, parent_key: str = "", sep: str = ".") -> dict:
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def _unflatten(d: dict, sep: str = ".") -> dict:
    result = {}
    for k, v in d.items():
        parts = k.split(sep)
        current = result
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = v
    return result


def _cast(val: str, default_val: any) -> any:
    if isinstance(default_val, bool):
        return str(val).lower() in ("true", "1", "yes", "y")
    if isinstance(default_val, int):
        try:
            return int(val)
        except ValueError:
            return default_val
    return val


def load_config() -> dict:
    """Load config from all layers, merged in priority order."""
    config = DEFAULT_CONFIG.copy()

    # Layer 2: Global (~/.compass/config.toml)
    global_path = Path.home() / ".compass" / "config.toml"
    try:
        has_global = global_path.exists()
    except (PermissionError, OSError):
        has_global = False
    if has_global:
        try:
            config.update(
                _flatten(tomllib.loads(global_path.read_text(encoding="utf-8")))
            )
        except Exception as e:
            print(f"[config] Warning: Failed to parse global config {global_path}: {e}")

    # Layer 3: Project (./.compass/config.toml)
    project_path = Path.cwd() / ".compass" / "config.toml"
    try:
        has_project = project_path.exists()
    except (PermissionError, OSError):
        has_project = False
    if has_project:
        try:
            config.update(
                _flatten(tomllib.loads(project_path.read_text(encoding="utf-8")))
            )
        except Exception as e:
            print(
                f"[config] Warning: Failed to parse project config {project_path}: {e}"
            )

    # Layer 4: Env vars (COMPASS_MODEL_EXECUTOR -> model.executor)
    for key in config:
        env_key = "COMPASS_" + key.replace(".", "_").upper()
        if env_key in os.environ:
            config[key] = _cast(os.environ[env_key], config[key])

    return config


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


def effective_settings_report() -> dict[str, dict[str, Any]]:
    """Return the effective value and runtime consumer for every public setting."""
    return {
        key: {"consumer": consumer, "value": settings.get(key)}
        for key, consumer in PUBLIC_SETTING_CONSUMERS.items()
    }
