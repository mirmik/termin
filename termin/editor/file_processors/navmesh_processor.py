"""NavMesh file processor for .navmesh files."""

from __future__ import annotations

import os
from typing import Set

from termin.editor.project_file_watcher import FileTypeProcessor


class NavMeshProcessor(FileTypeProcessor):
    """Handles navmesh files (.navmesh)."""

    @property
    def priority(self) -> int:
        return 10  # NavMesh has no dependencies

    @property
    def extensions(self) -> Set[str]:
        return {".navmesh"}

    @property
    def resource_type(self) -> str:
        return "navmesh"

    def on_file_added(self, path: str) -> None:
        """Load new navmesh file."""
        from termin.navmesh.persistence import NavMeshPersistence

        name = os.path.splitext(os.path.basename(path))[0]

        if name in self._resource_manager.navmeshes:
            return

        try:
            navmesh = NavMeshPersistence.load(path)
            self._resource_manager.register_navmesh(name, navmesh)

            if path not in self._file_to_resources:
                self._file_to_resources[path] = set()
            self._file_to_resources[path].add(name)

            print(f"[NavMeshProcessor] Loaded: {name} ({navmesh.polygon_count()} polygons)")
            self._notify_reloaded(name)

        except Exception as e:
            print(f"[NavMeshProcessor] Failed to load {path}: {e}")

    def on_file_changed(self, path: str) -> None:
        """Reload modified navmesh."""
        from termin.navmesh.persistence import NavMeshPersistence

        old_names = self._file_to_resources.get(path, set())
        name = os.path.splitext(os.path.basename(path))[0]

        try:
            navmesh = NavMeshPersistence.load(path)

            # Remove old name if different
            for old_name in old_names:
                if old_name != name and old_name in self._resource_manager.navmeshes:
                    self._resource_manager.unregister_navmesh(old_name)

            self._resource_manager.register_navmesh(name, navmesh)

            self._file_to_resources[path] = {name}

            print(f"[NavMeshProcessor] Reloaded: {name} ({navmesh.polygon_count()} polygons)")
            self._notify_reloaded(name)

        except Exception as e:
            print(f"[NavMeshProcessor] Failed to reload {path}: {e}")

    def on_file_removed(self, path: str) -> None:
        """Handle navmesh file deletion."""
        if path in self._file_to_resources:
            for name in self._file_to_resources[path]:
                self._resource_manager.unregister_navmesh(name)
                print(f"[NavMeshProcessor] Removed: {name}")
            del self._file_to_resources[path]
