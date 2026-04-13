"""
Termin Player - standalone game runtime without editor UI.

Usage:
    python -m termin.player path/to/project

Or programmatically:
    from termin.player import run_project
    run_project("path/to/project", "scene.scene")
"""

from .runtime import PlayerRuntime, run_project

__all__ = ["PlayerRuntime", "run_project"]
