"""Project management for the launcher: persistence and creation."""

from __future__ import annotations

import json
import os
import time
import uuid

from termin._native import log

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


# Built-in asset UUIDs
_MESH_CUBE = "00000000-0000-0000-0003-000000000001"
_MESH_PLANE = "00000000-0000-0000-0003-000000000003"
_MATERIAL_DEFAULT = "00000000-0000-0000-0002-000000000001"


def _make_default_scene(name: str) -> dict:
    """Create a default scene with a cube, a plane, and lighting."""
    return {
        "version": "1.0",
        "scene": {
            "uuid": str(uuid.uuid4()),
            "background_color": [0.05, 0.05, 0.08, 1.0],
            "light_direction": [0.3, 1.0, -0.5],
            "light_color": [1.0, 1.0, 1.0],
            "ambient_color": [1.0, 1.0, 1.0],
            "ambient_intensity": 0.15,
            "shadow_settings": {
                "method": 1,
                "softness": 1.0,
                "bias": 0.005,
            },
            "skybox_type": "gradient",
            "skybox_color": [0.5, 0.7, 0.9],
            "skybox_top_color": [0.4, 0.6, 0.9],
            "skybox_bottom_color": [0.6, 0.5, 0.4],
            "entities": [
                {
                    "uuid": str(uuid.uuid4()),
                    "name": "Cube",
                    "priority": 0,
                    "visible": True,
                    "enabled": True,
                    "pickable": True,
                    "selectable": True,
                    "layer": 0,
                    "flags": 0,
                    "pose": {
                        "position": [0, 0.5, 0],
                        "rotation": [0, 0, 0, 1],
                    },
                    "scale": [1, 1, 1],
                    "children": [],
                    "components": [
                        {
                            "type": "MeshRenderer",
                            "data": {
                                "mesh": {
                                    "uuid": _MESH_CUBE,
                                    "type": "named",
                                    "name": "Cube",
                                },
                                "material": {
                                    "type": "uuid",
                                    "uuid": _MATERIAL_DEFAULT,
                                },
                                "cast_shadow": True,
                            },
                        }
                    ],
                },
                {
                    "uuid": str(uuid.uuid4()),
                    "name": "Ground",
                    "priority": 0,
                    "visible": True,
                    "enabled": True,
                    "pickable": True,
                    "selectable": True,
                    "layer": 0,
                    "flags": 0,
                    "pose": {
                        "position": [0, 0, 0],
                        "rotation": [0, 0, 0, 1],
                    },
                    "scale": [5, 5, 5],
                    "children": [],
                    "components": [
                        {
                            "type": "MeshRenderer",
                            "data": {
                                "mesh": {
                                    "uuid": _MESH_PLANE,
                                    "type": "named",
                                    "name": "Plane",
                                },
                                "material": {
                                    "type": "uuid",
                                    "uuid": _MATERIAL_DEFAULT,
                                },
                                "cast_shadow": False,
                            },
                        }
                    ],
                },
            ],
            "layer_names": {},
            "flag_names": {},
            "viewport_configs": [],
            "scene_pipelines": [],
        },
        "editor": {
            "camera": {
                "target": [0.0, 0.5, 0.0],
                "radius": 6.0,
                "azimuth": 0.8,
                "elevation": 0.45,
            },
            "selected_entity": None,
            "displays": [],
            "expanded_entities": [],
        },
        "resources": {
            "textures": {},
        },
    }


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

    # Default scene
    with open(scene_file, "w", encoding="utf-8") as f:
        json.dump(_make_default_scene(name), f, indent=2)

    return proj_file
