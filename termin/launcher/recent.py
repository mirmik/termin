"""Project management for the launcher: persistence and creation."""

from __future__ import annotations

import json
import os
import time

from termin._native import log
from termin.default_scene import write_default_scene

MAX_RECENT = 10
CONFIG_DIR = os.path.expanduser("~/.config/termin")
RECENT_FILE = os.path.join(CONFIG_DIR, "recent.json")
LAUNCH_PROJECT_FILE = os.path.join(CONFIG_DIR, "launch_project.json")


class RecentProjects:
    """Manages the list of recently opened projects."""

    def __init__(self):
        self._projects: list[dict] = []
        self.load()

    def load(self):
        """Load recent projects from disk."""
        if not os.path.exists(RECENT_FILE):
            self._projects = []
            return
        try:
            with open(RECENT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._projects = data.get("recent_projects", [])
        except Exception as e:
            log.error(f"Failed to load recent projects: {e}")
            self._projects = []

    def save(self):
        """Save recent projects to disk."""
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(RECENT_FILE, "w", encoding="utf-8") as f:
                json.dump({"recent_projects": self._projects}, f, indent=2)
        except Exception as e:
            log.error(f"Failed to save recent projects: {e}")

    def add(self, project_path: str):
        """Add or bump a project to the top of the list."""
        project_path = os.path.abspath(project_path)

        # Read project name from .terminproj if it exists
        name = self._read_project_name(project_path)

        # Remove if already in list
        self._projects = [p for p in self._projects if p["path"] != project_path]

        # Add to top
        self._projects.insert(0, {
            "path": project_path,
            "name": name,
            "timestamp": int(time.time()),
        })

        # Cap
        self._projects = self._projects[:MAX_RECENT]
        self.save()

    def remove(self, project_path: str):
        """Remove a project from the list."""
        project_path = os.path.abspath(project_path)
        self._projects = [p for p in self._projects if p["path"] != project_path]
        self.save()

    def list(self) -> list[dict]:
        """Return recent projects, newest first."""
        return list(self._projects)

    def _read_project_name(self, project_path: str) -> str:
        """Try to read project name from .terminproj file."""
        if os.path.isfile(project_path) and project_path.endswith(".terminproj"):
            try:
                with open(project_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data.get("name", os.path.basename(os.path.dirname(project_path)))
            except Exception:
                pass
        # Fallback: use directory name
        if os.path.isdir(project_path):
            return os.path.basename(project_path)
        return os.path.basename(os.path.dirname(project_path))


def resolve_project_path(path_str: str) -> str | None:
    """Resolve a CLI argument to an absolute .terminproj path.

    Accepts:
    - Path to .terminproj file
    - Path to directory containing a single .terminproj file

    Returns absolute path or None.
    """
    p = os.path.abspath(path_str)
    if os.path.isfile(p) and p.endswith(".terminproj"):
        return p
    if os.path.isdir(p):
        proj_files = [
            f for f in os.listdir(p)
            if f.endswith(".terminproj") and os.path.isfile(os.path.join(p, f))
        ]
        if len(proj_files) == 1:
            return os.path.join(p, proj_files[0])
        if len(proj_files) > 1:
            print(f"Error: multiple .terminproj files in '{p}'", flush=True)
            return None
    return None


def write_launch_project(project_path: str) -> None:
    """Write a project path for the editor to pick up on startup."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(LAUNCH_PROJECT_FILE, "w", encoding="utf-8") as f:
        json.dump({"project": os.path.abspath(project_path)}, f)


def read_launch_project() -> str | None:
    """Read and consume the launch project file. Returns path or None."""
    if not os.path.exists(LAUNCH_PROJECT_FILE):
        return None
    try:
        with open(LAUNCH_PROJECT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        os.remove(LAUNCH_PROJECT_FILE)
        return data.get("project")
    except Exception as e:
        log.error(f"Failed to read launch project file: {e}")
        return None


def create_project(name: str, location: str) -> str:
    """Create a new project on disk.

    Creates the directory structure, .terminproj manifest,
    project settings, and a default scene with a cube and ground plane.

    Returns the path to the .terminproj file.
    Raises on failure.
    """
    project_dir = os.path.join(location, name)
    proj_file = os.path.join(project_dir, f"{name}.terminproj")
    scene_file = os.path.join(project_dir, "scene.scene")
    settings_dir = os.path.join(project_dir, "project_settings")

    # Create directories
    os.makedirs(project_dir, exist_ok=True)
    os.makedirs(settings_dir, exist_ok=True)

    # Project manifest
    with open(proj_file, "w", encoding="utf-8") as f:
        json.dump({"version": 1, "name": name}, f, indent=2)

    # Project settings
    with open(os.path.join(settings_dir, "project.json"), "w", encoding="utf-8") as f:
        json.dump({"render_sync_mode": "none"}, f, indent=2)

    # Editor state — remember the default scene
    with open(os.path.join(settings_dir, ".editor_state.json"), "w", encoding="utf-8") as f:
        json.dump({"last_scene": scene_file}, f, indent=2)

    # Default scene
    write_default_scene(scene_file)

    return proj_file
