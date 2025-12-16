"""MeshAsset - Asset for 3D mesh data."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from termin.mesh.mesh import Mesh3
from termin.visualization.core.asset import Asset

if TYPE_CHECKING:
    pass


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

        from termin.visualization.core.resources import ResourceManager

        rm = ResourceManager.instance()
        mesh3 = rm.load_mesh_data(str(self._source_path))
        if mesh3 is not None:
            self._mesh_data = mesh3
            if self._mesh_data.vertex_normals is None:
                self._mesh_data.compute_vertex_normals()
            self._loaded = True
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
