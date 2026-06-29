"""
Termin Player - standalone game runtime without editor UI.

Usage:
    python -m termin.player path/to/project

Or programmatically:
    from termin.player import run_project
    run_project("path/to/project", "scene.scene")
"""

from .headless import HeadlessRuntime, HeadlessRuntimeError, HeadlessRunStats, run_headless_project
from .runtime import PlayerRuntime, active_runtime, request_quit, run_bundle, run_project

__all__ = [
    "HeadlessRuntime",
    "HeadlessRuntimeError",
    "HeadlessRunStats",
    "PlayerRuntime",
    "active_runtime",
    "request_quit",
    "run_bundle",
    "run_headless_project",
    "run_project",
]
