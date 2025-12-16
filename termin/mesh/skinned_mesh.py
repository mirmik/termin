"""Skinned mesh class for skeletal animation."""

import numpy as np

from .mesh import Mesh3, VertexLayout, VertexAttribute, VertexAttribType


class SkinnedMesh3(Mesh3):
    """
    Triangle mesh with skinning data for skeletal animation.

    Extends Mesh3 with:
    - joint_indices: (N, 4) - up to 4 bone indices per vertex
    - joint_weights: (N, 4) - blend weights (should sum to 1.0)

    Vertex layout: 64 bytes
    - position (3 floats) = 12 bytes
    - normal (3 floats) = 12 bytes
    - uv (2 floats) = 8 bytes
    - joints (4 floats) = 16 bytes (stored as float for shader compatibility)
    - weights (4 floats) = 16 bytes
    """

    def __init__(
        self,
        vertices: np.ndarray,
        triangles: np.ndarray,
        uvs: np.ndarray | None = None,
        vertex_normals: np.ndarray | None = None,
        joint_indices: np.ndarray | None = None,
        joint_weights: np.ndarray | None = None,
        source_path: str | None = None,
    ):
        """
        Initialize skinned mesh.

        Args:
            vertices: (N, 3) vertex positions
            triangles: (M, 3) triangle indices
            uvs: (N, 2) texture coordinates or None
            vertex_normals: (N, 3) vertex normals or None
            joint_indices: (N, 4) bone indices per vertex or None
            joint_weights: (N, 4) blend weights per vertex or None
            source_path: Path to source file
        """
        super().__init__(
            vertices=vertices,
            triangles=triangles,
            uvs=uvs,
            vertex_normals=vertex_normals,
            source_path=source_path,
        )

        n_verts = vertices.shape[0]

        # Initialize joint data - default to no skinning (bone 0, weight 1)
        if joint_indices is not None:
            self.joint_indices = np.asarray(joint_indices, dtype=np.float32)
        else:
            self.joint_indices = np.zeros((n_verts, 4), dtype=np.float32)

        if joint_weights is not None:
            self.joint_weights = np.asarray(joint_weights, dtype=np.float32)
        else:
            # Default: first weight = 1.0, rest = 0.0 (no skinning)
            self.joint_weights = np.zeros((n_verts, 4), dtype=np.float32)
            self.joint_weights[:, 0] = 1.0

        self._validate_skinning_data()

    def _validate_skinning_data(self):
        """Validate skinning arrays have correct shapes."""
        n_verts = self.vertices.shape[0]

        if self.joint_indices.shape != (n_verts, 4):
            raise ValueError(
                f"joint_indices must be ({n_verts}, 4), got {self.joint_indices.shape}"
            )

        if self.joint_weights.shape != (n_verts, 4):
            raise ValueError(
                f"joint_weights must be ({n_verts}, 4), got {self.joint_weights.shape}"
            )

    def copy(self) -> "SkinnedMesh3":
        """Create a copy of the skinned mesh."""
        uvs_copy = self.uvs.copy() if self.uvs is not None else None
        normals_copy = self.vertex_normals.copy() if self.vertex_normals is not None else None

        mesh_copy = SkinnedMesh3(
            vertices=self.vertices.copy(),
            triangles=self.triangles.copy(),
            uvs=uvs_copy,
            vertex_normals=normals_copy,
            joint_indices=self.joint_indices.copy(),
            joint_weights=self.joint_weights.copy(),
            source_path=self.source_path,
        )

        if self.face_normals is not None:
            mesh_copy.face_normals = self.face_normals.copy()

        return mesh_copy

    def build_interleaved_buffer(self) -> np.ndarray:
        """
        Build interleaved vertex buffer with skinning data.

        Layout per vertex: pos(3) + normal(3) + uv(2) + joints(4) + weights(4)
        Total: 16 floats = 64 bytes per vertex
        """
        # Position - always present
        pos = self.vertices.astype(np.float32)

        # Normals - generate zeros if missing
        if self.vertex_normals is None:
            normals = np.zeros_like(self.vertices, dtype=np.float32)
        else:
            normals = self.vertex_normals.astype(np.float32)

        # UVs - generate zeros if missing
        if self.uvs is None:
            uvs = np.zeros((self.vertices.shape[0], 2), dtype=np.float32)
        else:
            uvs = self.uvs.astype(np.float32)

        # Joint indices and weights - already float32
        joints = self.joint_indices.astype(np.float32)
        weights = self.joint_weights.astype(np.float32)

        return np.hstack([pos, normals, uvs, joints, weights])

    def get_vertex_layout(self) -> VertexLayout:
        """
        Get vertex layout for skinned mesh.

        Layout: pos(3) + normal(3) + uv(2) + joints(4) + weights(4)
        Stride: 16 * 4 = 64 bytes
        """
        return VertexLayout(
            stride=16 * 4,  # 64 bytes
            attributes=[
                VertexAttribute("position", 3, VertexAttribType.FLOAT32, 0),
                VertexAttribute("normal", 3, VertexAttribType.FLOAT32, 12),
                VertexAttribute("uv", 2, VertexAttribType.FLOAT32, 24),
                VertexAttribute("joints", 4, VertexAttribType.FLOAT32, 32),
                VertexAttribute("weights", 4, VertexAttribType.FLOAT32, 48),
            ],
        )

    def normalize_weights(self):
        """Normalize joint weights to sum to 1.0 per vertex."""
        sums = self.joint_weights.sum(axis=1, keepdims=True)
        # Avoid division by zero
        sums[sums == 0] = 1.0
        self.joint_weights /= sums
        # Clear interleaved buffer cache
        self._inter = None

    def direct_serialize(self) -> dict:
        """Serialize skinned mesh to dict."""
        result = super().direct_serialize()

        # Add skinning data
        result["joint_indices"] = self.joint_indices.tolist()
        result["joint_weights"] = self.joint_weights.tolist()
        result["skinned"] = True

        return result

    @classmethod
    def direct_deserialize(cls, data: dict) -> "SkinnedMesh3":
        """Deserialize skinned mesh from dict."""
        vertices = np.array(data["vertices"], dtype=np.float32)
        triangles = np.array(data["triangles"], dtype=np.int32)
        uvs = np.array(data["uvs"], dtype=np.float32) if "uvs" in data else None
        normals = np.array(data["normals"], dtype=np.float32) if "normals" in data else None
        joint_indices = (
            np.array(data["joint_indices"], dtype=np.float32)
            if "joint_indices" in data
            else None
        )
        joint_weights = (
            np.array(data["joint_weights"], dtype=np.float32)
            if "joint_weights" in data
            else None
        )
        source_path = data.get("path") if data.get("type") == "path" else None

        return cls(
            vertices=vertices,
            triangles=triangles,
            uvs=uvs,
            vertex_normals=normals,
            joint_indices=joint_indices,
            joint_weights=joint_weights,
            source_path=source_path,
        )
