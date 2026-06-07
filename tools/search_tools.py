import os
import re
from langchain_core.tools import tool


import os
import re
from fnmatch import fnmatch
from langchain_core.tools import tool


@tool
def grep_search(
    query: str,
    path: str = ".",
    include: str = "",
    ignore_case: bool = False,
    is_regex: bool = False,
    max_results: int = 50,
) -> str:
    """Search for text across files."""

    if not os.path.exists(path):
        return f"Error: Path not found: {path}"

    try:
        pattern = re.compile(
            query if is_regex else re.escape(query),
            re.IGNORECASE if ignore_case else 0,
        )
    except re.error as e:
        return f"Error: Invalid regex pattern: {e}"

    matches = []

    def search_file(filepath: str):
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, 1):
                    if pattern.search(line):
                        matches.append(
                            f"{filepath}:{line_num}: {line.rstrip()}"
                        )
                        if len(matches) >= max_results:
                            return True
        except (PermissionError, OSError):
            pass
        return False

    if os.path.isfile(path):
        search_file(path)
    else:
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith(".")]

            for file in files:
                if file.startswith("."):
                    continue
                if include and not fnmatch(file, include):
                    continue

                if search_file(os.path.join(root, file)):
                    break

            if len(matches) >= max_results:
                break

    if not matches:
        return f"No matches found for '{query}'"

    return (
        f"Found {len(matches)} match{'es' if len(matches)!=1 else ''} "
        f"for '{query}':\n"
        + "\n".join(matches)
    )