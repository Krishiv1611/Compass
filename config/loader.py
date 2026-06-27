import os
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib

DEFAULT_CONFIG = {
    # UI
    "theme": "default",
    
    # Models (per-role overrides)
    "model.planner": "google/gemma-4-31b-it:free",
    "model.executor": "google/gemma-4-31b-it:free", 
    "model.recovery": "google/gemma-4-31b-it:free",
    "model.summarizer": "google/gemma-4-31b-it:free",
    
    # Safety
    "safety.mode": "auto",              # auto | yolo | strict
    "safety.blocked_commands": "",       # extra blocked patterns
    
    # Tools
    "tools.max_results": 50,
    "tools.shell_timeout": 30,
    
    # Context
    "context.summarize_after": 10,       # message count threshold
    "context.loop_max_retries": 3,
    
    # RAG
    "rag.auto_index": False,
    "rag.chunk_size": 1000,
}

def _flatten(d: dict, parent_key: str = '', sep: str = '.') -> dict:
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

def _unflatten(d: dict, sep: str = '.') -> dict:
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
    if global_path.exists():
        try:
            config.update(_flatten(tomllib.loads(global_path.read_text(encoding="utf-8"))))
        except Exception as e:
            print(f"[config] Warning: Failed to parse global config {global_path}: {e}")
    
    # Layer 3: Project (./.compass/config.toml)
    project_path = Path.cwd() / ".compass" / "config.toml"
    if project_path.exists():
        try:
            config.update(_flatten(tomllib.loads(project_path.read_text(encoding="utf-8"))))
        except Exception as e:
            print(f"[config] Warning: Failed to parse project config {project_path}: {e}")
            
    # Layer 4: Env vars (COMPASS_MODEL_EXECUTOR -> model.executor)
    for key in config:
        env_key = "COMPASS_" + key.replace(".", "_").upper()
        if env_key in os.environ:
            config[key] = _cast(os.environ[env_key], config[key])
            
    return config
