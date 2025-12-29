"""MeshAsset - Asset for 3D mesh data with GPU rendering support."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from termin.mesh.mesh import Mesh3
from termin.assets.data_asset import DataAsset

if TYPE_CHECKING:
    from termin.loaders.mesh_spec import MeshSpec
    from termin.visualization.render.render_context import RenderContext
    from termin.visualization.core.mesh_gpu import MeshGPU


class MeshAsset(DataAsset[Mesh3]):
    """
    Asset for 3D mesh geometry.

    IMPORTANT: Create through ResourceManager.get_or_create_mesh_asset(),
    not directly. This ensures proper registration and avoids duplicates.

    Stores Mesh3 (CPU data: vertices, triangles, normals, UVs).
    Does NOT handle GPU upload - that's MeshGPU's responsibility.

    Can be loaded from:
    - STL/OBJ files (standalone)
    - GLB files (embedded, via parent asset)
    """

    _uses_binary = True  # STL/OBJ are read as binary

    def __init__(
        self,
        mesh_data: Mesh3 | None = None,
        name: str = "mesh",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        super().__init__(data=mesh_data, name=name, source_path=source_path, uuid=uuid)

        # GPU resources (created on demand)
        self._gpu: MeshGPU | None = None

        # Spec settings (parsed from spec file)
        self._scale: float = 1.0
        self._axis_x: str = "x"
        self._axis_y: str = "y"
        self._axis_z: str = "z"
        self._flip_uv_v: bool = False

        # Compute normals if mesh data provided and normals missing
        if self._data is not None and self._data.vertex_normals is None:
            self._data.compute_vertex_normals()

    # --- Convenience property ---

    @property
    def mesh_data(self) -> Mesh3 | None:
        """Mesh geometry data (lazy-loaded via parent's data property)."""
        return self.data

    @mesh_data.setter
    def mesh_data(self, value: Mesh3 | None) -> None:
        """Set mesh data and bump version."""
        if value is not None and value.vertex_normals is None:
            value.compute_vertex_normals()
        self.data = value

    # --- Spec parsing ---

    def _parse_spec_fields(self, spec_data: dict) -> None:
        """Parse mesh-specific spec fields."""
        self._scale = spec_data.get("scale", 1.0)
        self._axis_x = spec_data.get("axis_x", "x")
        self._axis_y = spec_data.get("axis_y", "y")
        self._axis_z = spec_data.get("axis_z", "z")
        self._flip_uv_v = spec_data.get("flip_uv_v", False)

    def _build_spec_data(self) -> dict:
        """Build spec data with mesh settings."""
        spec = super()._build_spec_data()
        # Only save non-default values
        if self._scale != 1.0:
            spec["scale"] = self._scale
        if self._axis_x != "x":
            spec["axis_x"] = self._axis_x
        if self._axis_y != "y":
            spec["axis_y"] = self._axis_y
        if self._axis_z != "z":
            spec["axis_z"] = self._axis_z
        if self._flip_uv_v:
            spec["flip_uv_v"] = True
        return spec

    def _get_mesh_spec(self) -> "MeshSpec":
        """Create MeshSpec from current settings."""
        from termin.loaders.mesh_spec import MeshSpec

        return MeshSpec(
            scale=self._scale,
            axis_x=self._axis_x,
            axis_y=self._axis_y,
            axis_z=self._axis_z,
            flip_uv_v=self._flip_uv_v,
        )

    # --- Content parsing ---

    def _parse_content(self, content: bytes) -> Mesh3 | None:
        """Parse mesh content (STL or OBJ based on file extension)."""
        if self._source_path is None:
            return None

        import os

        ext = os.path.splitext(str(self._source_path))[1].lower()
        spec = self._get_mesh_spec()

        if ext == ".stl":
            return self._parse_stl_content(content, spec)
        elif ext == ".obj":
            return self._parse_obj_content(content, spec)
        else:
            print(f"[MeshAsset] Unsupported format: {ext}")
            return None

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

        mesh3 = Mesh3(
            name=self._name,
            vertices=mesh_data.vertices,
            triangles=mesh_data.indices.reshape(-1, 3),
            vertex_normals=mesh_data.normals,
        )
        if mesh3.vertex_normals is None:
            mesh3.compute_vertex_normals()
        return mesh3

    def _parse_obj_content(self, content: bytes, spec: "MeshSpec") -> Mesh3 | None:
        """Parse OBJ content from bytes."""
        from termin.loaders.obj_loader import parse_obj_text

        text = content.decode("utf-8", errors="ignore")

        scene_data = parse_obj_text(text, name=self._name, spec=spec)
        if not scene_data.meshes:
            return None

        mesh_data = scene_data.meshes[0]
        mesh3 = Mesh3(
            name=self._name,
            vertices=mesh_data.vertices,
            triangles=mesh_data.indices.reshape(-1, 3),
        )
        if mesh_data.normals is not None:
            mesh3.vertex_normals = mesh_data.normals
        if mesh_data.uvs is not None:
            mesh3.uvs = mesh_data.uvs

        if mesh3.vertex_normals is None:
            mesh3.compute_vertex_normals()
        return mesh3

    # --- Convenience methods for mesh manipulation ---

    def get_vertex_count(self) -> int:
        """Get number of vertices."""
        data = self.data
        if data is None or data.vertices is None:
            return 0
        return len(data.vertices)

    def get_triangle_count(self) -> int:
        """Get number of triangles."""
        data = self.data
        if data is None or data.triangles is None:
            return 0
        return len(data.triangles)

    def interleaved_buffer(self):
        """Get interleaved vertex buffer for GPU upload."""
        data = self.data
        return data.interleaved_buffer() if data else None

    def get_vertex_layout(self):
        """Get vertex layout for shader binding."""
        data = self.data
        return data.get_vertex_layout() if data else None

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
        mesh3 = Mesh3(name=name, vertices=vertices, triangles=triangles)
        return cls(mesh_data=mesh3, name=name)

    # --- GPU access ---

    @property
    def gpu(self) -> "MeshGPU":
        """Get MeshGPU for rendering (created on demand)."""
        if self._gpu is None:
            from termin.visualization.core.mesh_gpu import MeshGPU
            self._gpu = MeshGPU()
        return self._gpu

    def delete_gpu(self) -> None:
        """Delete GPU resources."""
        if self._gpu is not None:
            self._gpu.delete()
            self._gpu = None
