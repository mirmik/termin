"""Shared helpers for project build wrappers."""

from __future__ import annotations

import json
import os
from pathlib import Path


def preload_project_resources(project_root: Path, log_prefix: str) -> None:
    """Load project resources into runtime registries for non-editor builds."""
    try:
        from termin.assets.resources import ResourceManager
        from termin.editor_core.default_preloaders import create_default_preloaders

        resource_manager = ResourceManager.instance()
        processors = create_default_preloaders(resource_manager)
        by_extension = {
            extension: processor
            for processor in processors
            for extension in processor.extensions
        }
        pending: list[tuple[int, str]] = []
        for root, dirs, files in os.walk(project_root):
            dirs[:] = [
                directory
                for directory in dirs
                if not directory.startswith((".", "__"))
                and directory not in {"build", "dist"}
            ]
            for filename in files:
                if filename.startswith("."):
                    continue
                path = Path(root) / filename
                extension = path.suffix.lower()
                processor = by_extension.get(extension)
                if processor is not None:
                    pending.append((processor.priority, str(path)))

        for _priority, path in sorted(pending, key=lambda item: (item[0], item[1])):
            by_extension[Path(path).suffix.lower()].on_file_added(path)
    except Exception:
        from tcbase import log
        log.error(f"{log_prefix} Failed to preload project resources", exc_info=True)


def read_project_name(project_root: Path) -> str:
    project_files = sorted(project_root.glob("*.terminproj"))
    if not project_files:
        return project_root.name

    project_file = project_files[0]
    try:
        with open(project_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return project_file.stem

    if not isinstance(data, dict):
        return project_file.stem

    name = data.get("name")
    if isinstance(name, str) and name != "":
        return name
    return project_file.stem
