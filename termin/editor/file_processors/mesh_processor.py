"""Mesh file processor for 3D model files."""

from __future__ import annotations

import os
from typing import Set

from termin.editor.project_file_watcher import FileTypeProcessor


class MeshFileProcessor(FileTypeProcessor):
    """Handles 3D mesh files (.stl)."""

    @property
    def priority(self) -> int:
        return 10  # Meshes have no dependencies

    @property
    def extensions(self) -> Set[str]:
        return {".stl", ".obj", ".spec"}

    @property
    def resource_type(self) -> str:
        return "mesh"

    def on_file_added(self, path: str) -> None:
        """Load new mesh file or handle spec file."""
        ext = os.path.splitext(path)[1].lower()

        # .spec file - reload corresponding mesh
        if ext == ".spec":
            self._handle_spec_change(path)
            return

        name = os.path.splitext(os.path.basename(path))[0]

        if name in self._resource_manager.meshes:
            return

        try:
            drawable = self._load_mesh_file(path, name)
            if drawable is not None:
                self._resource_manager.register_mesh(name, drawable, source_path=path)

                if path not in self._file_to_resources:
                    self._file_to_resources[path] = set()
                self._file_to_resources[path].add(name)

                print(f"[MeshProcessor] Loaded: {name}")
                self._notify_reloaded(name)

        except Exception as e:
            print(f"[MeshProcessor] Failed to load {path}: {e}")

    def on_file_changed(self, path: str) -> None:
        """Reload modified mesh or handle spec change."""
        ext = os.path.splitext(path)[1].lower()

        # .spec file - reload corresponding mesh
        if ext == ".spec":
            self._handle_spec_change(path)
            return

        name = os.path.splitext(os.path.basename(path))[0]

        # Only reload if mesh is already registered
        if name not in self._resource_manager.meshes:
            return

        try:
            drawable = self._load_mesh_file(path, name)
            if drawable is not None:
                # register_mesh handles cleanup via keeper
                self._resource_manager.register_mesh(name, drawable, source_path=path)
                print(f"[MeshProcessor] Reloaded: {name}")
                self._notify_reloaded(name)

        except Exception as e:
            print(f"[MeshProcessor] Failed to reload {name}: {e}")

    def _handle_spec_change(self, spec_path: str) -> None:
        """Handle .spec file change - reload corresponding mesh."""
        # spec_path is like "model.stl.spec" - find the mesh file
        if not spec_path.endswith(".spec"):
            return

        mesh_path = spec_path[:-5]  # Remove ".spec"
        if not os.path.exists(mesh_path):
            return

        name = os.path.splitext(os.path.basename(mesh_path))[0]

        # Reload the mesh with new spec
        try:
            drawable = self._load_mesh_file(mesh_path, name)
            if drawable is not None:
                # register_mesh handles cleanup via keeper
                self._resource_manager.register_mesh(name, drawable, source_path=mesh_path)
                print(f"[MeshProcessor] Reloaded with new spec: {name}")
                self._notify_reloaded(name)

        except Exception as e:
            print(f"[MeshProcessor] Failed to reload {name} with spec: {e}")

    def on_file_removed(self, path: str) -> None:
        """Handle mesh file deletion."""
        if path in self._file_to_resources:
            for name in self._file_to_resources[path]:
                self._resource_manager.unregister_mesh(name)
                print(f"[MeshProcessor] Removed: {name}")
            del self._file_to_resources[path]

    def _load_mesh_file(self, path: str, name: str):
        """Load mesh from file (.stl, .obj), applying spec if present."""
        from termin.loaders.mesh_spec import MeshSpec
        from termin.mesh.mesh import Mesh3
        from termin.visualization.core.mesh import MeshDrawable

        ext = os.path.splitext(path)[1].lower()

        # Load spec if exists
        spec = MeshSpec.for_mesh_file(path)

        if ext == ".stl":
            from termin.loaders.stl_loader import load_stl_file
            scene_data = load_stl_file(path, spec=spec)
        elif ext == ".obj":
            from termin.loaders.obj_loader import load_obj_file
            scene_data = load_obj_file(path, spec=spec)
        else:
            print(f"[MeshProcessor] Unsupported format: {ext}")
            return None

        if not scene_data.meshes:
            print(f"[MeshProcessor] No meshes found in {path}")
            return None

        mesh_data = scene_data.meshes[0]
        mesh3 = Mesh3(
            vertices=mesh_data.vertices,
            triangles=mesh_data.indices.reshape(-1, 3),
        )
        if mesh_data.normals is not None:
            mesh3.vertex_normals = mesh_data.normals

        drawable = MeshDrawable(mesh3, source_id=path, name=name)
        return drawable

    def _notify_reloaded(self, name: str) -> None:
        """Notify listeners about resource reload."""
        if self._on_resource_reloaded is not None:
            self._on_resource_reloaded(self.resource_type, name)
