"""Voxel grid file processor for .voxels files."""

from __future__ import annotations

import os
from typing import Set

from termin.editor.project_file_watcher import FileTypeProcessor


class VoxelGridProcessor(FileTypeProcessor):
    """Handles voxel grid files (.voxels)."""

    @property
    def priority(self) -> int:
        return 10  # Voxel grids have no dependencies

    @property
    def extensions(self) -> Set[str]:
        return {".voxels"}

    @property
    def resource_type(self) -> str:
        return "voxel_grid"

    def on_file_added(self, path: str) -> None:
        """Load new voxel grid file."""
        from termin.voxels.persistence import VoxelPersistence

        name = os.path.splitext(os.path.basename(path))[0]

        if name in self._resource_manager.voxel_grids:
            return

        try:
            grid = VoxelPersistence.load(path)
            # Use grid's stored name if available, otherwise use filename
            if grid.name:
                name = grid.name

            self._resource_manager.register_voxel_grid(name, grid)

            if path not in self._file_to_resources:
                self._file_to_resources[path] = set()
            self._file_to_resources[path].add(name)

            print(f"[VoxelGridProcessor] Loaded: {name} ({grid.voxel_count} voxels)")
            self._notify_reloaded(name)

        except Exception as e:
            print(f"[VoxelGridProcessor] Failed to load {path}: {e}")

    def on_file_changed(self, path: str) -> None:
        """Reload modified voxel grid."""
        from termin.voxels.persistence import VoxelPersistence

        # Get previously registered name from this file
        old_names = self._file_to_resources.get(path, set())

        try:
            grid = VoxelPersistence.load(path)
            name = grid.name if grid.name else os.path.splitext(os.path.basename(path))[0]

            # Remove old name if different
            for old_name in old_names:
                if old_name != name and old_name in self._resource_manager.voxel_grids:
                    self._resource_manager.unregister_voxel_grid(old_name)

            self._resource_manager.register_voxel_grid(name, grid)

            self._file_to_resources[path] = {name}

            print(f"[VoxelGridProcessor] Reloaded: {name} ({grid.voxel_count} voxels)")
            self._notify_reloaded(name)

        except Exception as e:
            print(f"[VoxelGridProcessor] Failed to reload {path}: {e}")

    def on_file_removed(self, path: str) -> None:
        """Handle voxel grid file deletion."""
        if path in self._file_to_resources:
            for name in self._file_to_resources[path]:
                self._resource_manager.unregister_voxel_grid(name)
                print(f"[VoxelGridProcessor] Removed: {name}")
            del self._file_to_resources[path]
