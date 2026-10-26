"""Compass UI Theme definitions."""

from rich.theme import Theme


COMPASS_THEME = Theme(
    {
        "compass.prompt": "bold bright_cyan",
        "compass.thinking": "dim italic cyan",
        "compass.tool_name": "bold yellow",
        "compass.tool_args": "dim white",
        "compass.success": "bold green",
        "compass.error": "bold red",
        "compass.info": "bold blue",
        "compass.border": "bright_black",
        "compass.dim": "dim white",
        "compass.accent": "bold bright_cyan",
        "compass.warn": "bold yellow",
        "compass.highlight": "bold bright_white on rgb(40,40,60)",
        "compass.cost": "dim bright_green",
        "compass.status": "dim bright_white",
    }
)

HIGH_CONTRAST_THEME = Theme(
    {
        "compass.prompt": "bold bright_white on blue",
        "compass.thinking": "bold bright_white on magenta",
        "compass.tool_name": "bold bright_white on magenta",
        "compass.tool_args": "bright_white",
        "compass.success": "bold bright_white on green",
        "compass.error": "bold bright_white on red",
        "compass.info": "bold bright_white on blue",
        "compass.border": "bright_white",
        "compass.dim": "bright_white",
        "compass.accent": "bold bright_white on blue",
        "compass.warn": "bold black on yellow",
        "compass.highlight": "bold black on bright_white",
        "compass.cost": "bold bright_white on green",
        "compass.status": "bright_white",
    }
)


def theme_for_preference() -> Theme:
    """Resolve the configured UI-only terminal theme."""
    from agent.config import settings

    return HIGH_CONTRAST_THEME if settings.get("theme") == "high-contrast" else COMPASS_THEME
