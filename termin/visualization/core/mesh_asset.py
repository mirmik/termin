"""MeshAsset - Asset for 3D mesh data."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from termin.mesh.mesh import Mesh3
from termin.visualization.core.asset import Asset

if TYPE_CHECKING:
    from termin.loaders.mesh_spec import MeshSpec


class MeshAsset(Asset):
    """
    Asset for 3D mesh geometry.

    Stores Mesh3 (CPU data: vertices, triangles, normals, UVs).
    Does NOT handle GPU upload - that's MeshGPU's responsibility.
    """

    def __init__(
        self,
        mesh_data: Mesh3 | None = None,
        name: str = "mesh",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        """
        Initialize MeshAsset.

        Args:
            mesh_data: Mesh3 geometry data (can be None for lazy loading)
            name: Human-readable name
            source_path: Path to source file for loading/reloading
            uuid: Existing UUID or None to generate new one
        """
        super().__init__(name=name, source_path=source_path, uuid=uuid)
        self._mesh_data: Mesh3 | None = mesh_data

        # Compute normals if mesh data provided and normals missing
        if self._mesh_data is not None and self._mesh_data.vertex_normals is None:
            self._mesh_data.compute_vertex_normals()

        self._loaded = mesh_data is not None

    @property
    def mesh_data(self) -> Mesh3 | None:
        """Mesh geometry data."""
        return self._mesh_data

    @mesh_data.setter
    def mesh_data(self, value: Mesh3 | None) -> None:
        """Set mesh data and bump version."""
        self._mesh_data = value
        if self._mesh_data is not None and self._mesh_data.vertex_normals is None:
            self._mesh_data.compute_vertex_normals()
        self._loaded = value is not None
        self._bump_version()

    def load(self) -> bool:
        """
        Load mesh data from source_path.

        Returns:
            True if loaded successfully.
        """
        if self._source_path is None:
            return False

        try:
            # Read file content
            with open(self._source_path, "rb") as f:
                content = f.read()

            # Get spec_data from pending or read from file
            spec_data = getattr(self, "_pending_spec_data", None)
            if spec_data is None:
                from termin.editor.project_file_watcher import FilePreLoader
                spec_data = FilePreLoader.read_spec_file(str(self._source_path))

            # Check if UUID already in spec
            has_uuid = spec_data.get("uuid") is not None if spec_data else False

            return self.load_from_content(content, spec_data=spec_data, has_uuid_in_spec=has_uuid)
        except Exception as e:
            print(f"[MeshAsset] Failed to load from {self._source_path}: {e}")
            return False

    def load_from_content(
        self,
        content: bytes | None,
        spec_data: dict | None = None,
        has_uuid_in_spec: bool = False,
    ) -> bool:
        """
        Load mesh from binary content.

        Args:
            content: Binary mesh data (STL or OBJ format)
            spec_data: Spec file data with scale, axis mappings
            has_uuid_in_spec: If True, spec file already has UUID (don't save)

        Returns:
            True if loaded successfully.
        """
        if content is None or self._source_path is None:
            return False

        try:
            import io
            import os

            from termin.loaders.mesh_spec import MeshSpec

            ext = os.path.splitext(str(self._source_path))[1].lower()

            # Create MeshSpec from spec_data
            spec = MeshSpec(
                scale=spec_data.get("scale", 1.0) if spec_data else 1.0,
                axis_x=spec_data.get("axis_x", "x") if spec_data else "x",
                axis_y=spec_data.get("axis_y", "y") if spec_data else "y",
                axis_z=spec_data.get("axis_z", "z") if spec_data else "z",
                flip_uv_v=spec_data.get("flip_uv_v", False) if spec_data else False,
            )

            # Parse mesh based on format
            mesh_data = None
            if ext == ".stl":
                mesh_data = self._parse_stl_content(content, spec)
            elif ext == ".obj":
                mesh_data = self._parse_obj_content(content, spec)
            else:
                print(f"[MeshAsset] Unsupported format: {ext}")
                return False

            if mesh_data is None:
                return False

            self._mesh_data = mesh_data
            if self._mesh_data.vertex_normals is None:
                self._mesh_data.compute_vertex_normals()
            self._loaded = True

            # Save spec file if no UUID was in spec
            if not has_uuid_in_spec:
                self._save_spec_file(spec_data)

            return True
        except Exception as e:
            print(f"[MeshAsset] Failed to load content: {e}")
            return False

    def _parse_stl_content(self, content: bytes, spec: "MeshSpec") -> Mesh3 | None:
        """Parse STL content from bytes."""
        import io

        from termin.loaders.stl_loader import _load_binary_stl, _load_ascii_stl

        f = io.BytesIO(content)

        # Detect ASCII vs binary
        first_bytes = content[:80]
        is_ascii = (
            first_bytes.strip().lower().startswith(b"solid")
            and b"\x00" not in first_bytes
        )

        if is_ascii:
            try:
                mesh_data = _load_ascii_stl(f, self._name)
            except Exception:
                f.seek(0)
                mesh_data = _load_binary_stl(f, self._name)
        else:
            mesh_data = _load_binary_stl(f, self._name)

        # Apply spec transformations
        mesh_data.vertices = spec.apply_to_vertices(mesh_data.vertices)
        if mesh_data.normals is not None:
            mesh_data.normals = spec.apply_to_normals(mesh_data.normals)

        return Mesh3(
            vertices=mesh_data.vertices,
            triangles=mesh_data.indices.reshape(-1, 3),
            vertex_normals=mesh_data.normals,
        )

    def _parse_obj_content(self, content: bytes, spec: "MeshSpec") -> Mesh3 | None:
        """Parse OBJ content from bytes."""
        from termin.loaders.obj_loader import parse_obj_text

        text = content.decode("utf-8", errors="ignore")

        scene_data = parse_obj_text(text, name=self._name, spec=spec)
        if not scene_data.meshes:
            return None

        mesh_data = scene_data.meshes[0]
        mesh3 = Mesh3(
            vertices=mesh_data.vertices,
            triangles=mesh_data.indices.reshape(-1, 3),
        )
        if mesh_data.normals is not None:
            mesh3.vertex_normals = mesh_data.normals
        if mesh_data.uvs is not None:
            mesh3.uvs = mesh_data.uvs

        return mesh3

    def _save_spec_file(self, existing_spec_data: dict | None = None) -> bool:
        """Save UUID to spec file, preserving existing settings."""
        if self._source_path is None:
            return False

        from termin.editor.project_file_watcher import FilePreLoader

        # Merge existing spec data with UUID
        spec_data = dict(existing_spec_data) if existing_spec_data else {}
        spec_data["uuid"] = self.uuid

        if FilePreLoader.write_spec_file(str(self._source_path), spec_data):
            self.mark_just_saved()
            print(f"[MeshAsset] Added UUID to spec: {self._name}")
            return True
        return False

    def unload(self) -> None:
        """Unload mesh data to free memory."""
        self._mesh_data = None
        self._loaded = False

    # --- Convenience methods for mesh manipulation ---

    def get_vertex_count(self) -> int:
        """Get number of vertices."""
        if self._mesh_data is None or self._mesh_data.vertices is None:
            return 0
        return len(self._mesh_data.vertices)

    def get_triangle_count(self) -> int:
        """Get number of triangles."""
        if self._mesh_data is None or self._mesh_data.triangles is None:
            return 0
        return len(self._mesh_data.triangles)

    def interleaved_buffer(self):
        """Get interleaved vertex buffer for GPU upload."""
        if self._mesh_data is None:
            return None
        return self._mesh_data.interleaved_buffer()

    def get_vertex_layout(self):
        """Get vertex layout for shader binding."""
        if self._mesh_data is None:
            return None
        return self._mesh_data.get_vertex_layout()

    # --- Factory methods ---

    @classmethod
    def from_mesh3(
        cls,
        mesh3: Mesh3,
        name: str = "mesh",
        source_path: Path | str | None = None,
    ) -> "MeshAsset":
        """Create MeshAsset from existing Mesh3."""
        return cls(mesh_data=mesh3, name=name, source_path=source_path)

    @classmethod
    def from_vertices_triangles(
        cls,
        vertices,
        triangles,
        name: str = "mesh",
    ) -> "MeshAsset":
        """Create MeshAsset from vertices and triangles arrays."""
        mesh3 = Mesh3(vertices=vertices, triangles=triangles)
        return cls(mesh_data=mesh3, name=name)
