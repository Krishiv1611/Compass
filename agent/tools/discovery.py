import importlib.util
import inspect
from pathlib import Path
from typing import List

from langchain_core.tools import BaseTool


def get_custom_tools() -> List[BaseTool]:
    """Dynamically load and return custom tools from .compass/tools/"""
    custom_tools = []

    # Check both global (~/.compass/tools) and local (./.compass/tools) directories
    # Local directory is checked second so it can override global tools with the same name.
    search_dirs = [
        Path.home() / ".compass" / "tools",
        Path.cwd() / ".compass" / "tools",
    ]

    for tools_dir in search_dirs:
        if not tools_dir.exists() or not tools_dir.is_dir():
            continue

        # Scan for Python files
        for file_path in tools_dir.glob("*.py"):
            if file_path.name == "__init__.py":
                continue

            module_name = f"compass_custom_tools_{file_path.stem}"

            # Dynamically import the module
            spec = importlib.util.spec_from_file_location(module_name, str(file_path))
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(module)

                    # Inspect the module for LangChain tools
                    for name, obj in inspect.getmembers(module):
                        if isinstance(obj, BaseTool):
                            # Avoid loading duplicates if the same tool name is in both dirs
                            # local overrides global if they have the same name
                            existing_names = [t.name for t in custom_tools]
                            if obj.name not in existing_names:
                                custom_tools.append(obj)
                            else:
                                # Replace existing global tool with local tool of same name
                                idx = existing_names.index(obj.name)
                                custom_tools[idx] = obj

                except Exception as e:
                    print(
                        f"[tools] Error loading custom tool from {file_path.name}: {e}"
                    )

    return custom_tools
