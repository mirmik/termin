
import numpy as np

# CubeMesh, UVSphereMesh, IcoSphereMesh, PlaneMesh, CylinderMesh, ConeMesh

class Mesh:
    """Simple triangle mesh storing vertex positions and triangle indices."""

    def __init__(self, vertices: np.ndarray, triangles: np.ndarray, uvs: np.ndarray | None = None):
        self.vertices = np.asarray(vertices, dtype=float)
        self.triangles = np.asarray(triangles, dtype=int)
        self.uv = np.asarray(uvs, dtype=float) if uvs is not None else None
        self._validate_mesh()
        self.vertex_normals = None
        self.face_normals = None

    def _validate_mesh(self):
        """Ensure that the vertex/index arrays have correct shapes and bounds."""
        if self.vertices.ndim != 2 or self.vertices.shape[1] != 3:
            raise ValueError("Vertices must be a Nx3 array.")
        if self.triangles.ndim != 2 or self.triangles.shape[1] != 3:
            raise ValueError("Triangles must be a Mx3 array.")
        if np.any(self.triangles < 0) or np.any(self.triangles >= self.vertices.shape[0]):
            raise ValueError("Triangle indices must be valid vertex indices.")

    def translate(self, offset: np.ndarray):
        """Apply translation by vector ``offset`` to all vertices."""
        offset = np.asarray(offset, dtype=float)
        if offset.shape != (3,):
            raise ValueError("Offset must be a 3-dimensional vector.")
        self.vertices += offset

    @staticmethod
    def from_assimp_mesh(assimp_mesh) -> "Mesh":
            verts = np.asarray(assimp_mesh.vertices, dtype=float)
            idx = np.asarray(assimp_mesh.indices, dtype=int).reshape(-1, 3)

            if assimp_mesh.uvs is not None:
                uvs = np.asarray(assimp_mesh.uvs, dtype=float)
            else:
                uvs = None

            mesh = Mesh(vertices=verts, triangles=idx, uvs=uvs)

            # если нормали есть – присвоим
            if assimp_mesh.normals is not None:
                mesh.vertex_normals = np.asarray(assimp_mesh.normals, dtype=float)
            else:
                mesh.compute_vertex_normals()

            return mesh


    def scale(self, factor: float):
        """Uniformly scale vertex positions by ``factor``."""
        self.vertices *= factor

    def get_vertex_count(self) -> int:
        return self.vertices.shape[0]

    def get_face_count(self) -> int:
        return self.triangles.shape[0]

    def compute_faces_normals(self):
        """Compute per-face normals ``n = (v1-v0) × (v2-v0) / ||...||``."""
        v0 = self.vertices[self.triangles[:, 0], :]
        v1 = self.vertices[self.triangles[:, 1], :]
        v2 = self.vertices[self.triangles[:, 2], :]
        normals = np.cross(v1 - v0, v2 - v0)
        norms = np.linalg.norm(normals, axis=1, keepdims=True)
        norms[norms == 0] = 1  # Prevent division by zero
        self.face_normals = normals / norms
        return self.face_normals

    def compute_vertex_normals(self):
        """Compute area-weighted vertex normals: ``n_v = sum_{t∈F(v)} ( (v1-v0) × (v2-v0) ).``"""
        normals = np.zeros_like(self.vertices, dtype=np.float64)
        v0 = self.vertices[self.triangles[:, 0], :]
        v1 = self.vertices[self.triangles[:, 1], :]
        v2 = self.vertices[self.triangles[:, 2], :]
        face_normals = np.cross(v1 - v0, v2 - v0)
        for face, normal in zip(self.triangles, face_normals):
            normals[face] += normal
        norms = np.linalg.norm(normals, axis=1)
        norms[norms == 0] = 1.0
        self.vertex_normals = (normals.T / norms).T.astype(np.float32)
        return self.vertex_normals

    def from_convex_hull(hull) -> "Mesh":
        """Create a Mesh from a scipy.spatial.ConvexHull object."""
        vertices = hull.points
        triangles = hull.simplices

        center = np.mean(vertices, axis=0)

        for i in range(triangles.shape[0]):
            v0 = vertices[triangles[i, 0]]
            v1 = vertices[triangles[i, 1]]
            v2 = vertices[triangles[i, 2]]
            normal = np.cross(v1 - v0, v2 - v0)
            to_center = center - v0
            if np.dot(normal, to_center) > 0:
                triangles[i, [1, 2]] = triangles[i, [2, 1]]

        return Mesh(vertices=vertices, triangles=triangles)

class CubeMesh(Mesh):
    def __init__(self, size: float = 1.0, y: float = None, z: float = None):
        x = size
        if y is None:
            y = x
        if z is None:
            z = x
        s_x = x * 0.5
        s_y = y * 0.5
        s_z = z * 0.5
        vertices = np.array(
            [
                [-s_x, -s_y, -s_z],
                [s_x, -s_y, -s_z],
                [s_x, s_y, -s_z],
                [-s_x, s_y, -s_z],
                [-s_x, -s_y, s_z],
                [s_x, -s_y, s_z],
                [s_x, s_y, s_z],
                [-s_x, s_y, s_z],
            ],
            dtype=float,
        )
        triangles = np.array(
            [
                [1, 0, 2],
                [2, 0, 3],
                [4, 5, 7],
                [5, 6, 7],
                [0, 1, 4],
                [1, 5, 4],
                [2, 3, 6],
                [3, 7, 6],
                [3, 0, 4],
                [7, 3, 4],
                [1, 2, 5],
                [2, 6, 5],
            ],
            dtype=int,
        )
        uvs = np.array([
            [0.0, 0.0],
            [1.0, 0.0],
            [1.0, 1.0],
            [0.0, 1.0],
            [0.0, 0.0],
            [1.0, 0.0],
            [1.0, 1.0],
            [0.0, 1.0],
        ], dtype=float)
        super().__init__(vertices=vertices, triangles=triangles, uvs=uvs)


class TexturedCubeMesh(Mesh):
    def __init__(self, size: float = 1.0, y: float = None, z: float = None):
        x = size
        if y is None:
            y = x
        if z is None:
            z = x
        s_x = x * 0.5
        s_y = y * 0.5
        s_z = z * 0.5
        vertices = np.array([
        [-0.5, -0.5, -0.5],  #0.0f, 0.0f,
        [0.5, -0.5, -0.5],  #1.0f, 0.0f,
        [0.5,  0.5, -0.5],  #1.0f, 1.0f,
        [ 0.5,  0.5, -0.5],  #1.0f, 1.0f,
        [-0.5,  0.5, -0.5],  #0.0f, 1.0f,
        [-0.5, -0.5, -0.5],  #0.0f, 0.0f,

        [-0.5, -0.5,  0.5],  #0.0f, 0.0f,
         [0.5, -0.5,  0.5],  #1.0f, 0.0f,
         [0.5,  0.5,  0.5],  #1.0f, 1.0f,
         [0.5,  0.5,  0.5],  #1.0f, 1.0f,
        [-0.5,  0.5,  0.5],  #0.0f, 1.0f,
        [-0.5, -0.5,  0.5],  #0.0f, 0.0f,

        [-0.5,  0.5,  0.5],  #1.0f, 0.0f,
        [-0.5,  0.5, -0.5],  #1.0f, 1.0f,
        [-0.5, -0.5, -0.5],  #0.0f, 1.0f,
        [-0.5, -0.5, -0.5],  #0.0f, 1.0f,
        [-0.5, -0.5,  0.5],  #0.0f, 0.0f,
        [-0.5,  0.5,  0.5],  #1.0f, 0.0f,

         [0.5,  0.5,  0.5],  #1.0f, 0.0f,
         [0.5,  0.5, -0.5],  #1.0f, 1.0f,
         [0.5, -0.5, -0.5],  #0.0f, 1.0f,
         [0.5, -0.5, -0.5],  #0.0f, 1.0f,
         [0.5, -0.5,  0.5],  #0.0f, 0.0f,
         [0.5,  0.5,  0.5],  #1.0f, 0.0f,

        [-0.5, -0.5, -0.5],  #0.0f, 1.0f,
         [0.5, -0.5, -0.5],  #1.0f, 1.0f,
         [0.5, -0.5,  0.5],  #1.0f, 0.0f,
         [0.5, -0.5,  0.5],  #1.0f, 0.0f,
        [-0.5, -0.5,  0.5],  #0.0f, 0.0f,
        [-0.5, -0.5, -0.5],  #0.0f, 1.0f,

        [-0.5,  0.5, -0.5],  #0.0f, 1.0f,
         [0.5,  0.5, -0.5],  #1.0f, 1.0f,
         [0.5,  0.5,  0.5],  #1.0f, 0.0f,
         [0.5,  0.5,  0.5],  #1.0f, 0.0f,
        [-0.5,  0.5,  0.5],  #0.0f, 0.0f,
        [-0.5,  0.5, -0.5],  #0.0f, 1.0f
            ])

        uvs = np.array([
        [0.0, 0.0],
        [1.0, 0.0],
        [1.0, 1.0],
        [1.0, 1.0],
        [0.0, 1.0],
        [0.0, 0.0],
        
        [0.0, 0.0],
        [1.0, 0.0],
        [1.0, 1.0],
        [1.0, 1.0],
        [0.0, 1.0],
        [0.0, 0.0],

        [0.0, 0.0],
        [1.0, 0.0],
        [1.0, 1.0],
        [1.0, 1.0],
        [0.0, 1.0],
        [0.0, 0.0],

        [0.0, 0.0],
        [1.0, 0.0],
        [1.0, 1.0],
        [1.0, 1.0],
        [0.0, 1.0],
        [0.0, 0.0],

        [0.0, 0.0],
        [1.0, 0.0],
        [1.0, 1.0],
        [1.0, 1.0],
        [0.0, 1.0],
        [0.0, 0.0],

        [0.0, 0.0],
        [1.0, 0.0],
        [1.0, 1.0],
        [1.0, 1.0],
        [0.0, 1.0],
        [0.0, 0.0],
            ])

        triangles = np.array([
        [1, 0, 2],
        [4, 3, 5],
        [6, 7, 8],
        [9, 10,11],
        [12,13,14],
        [15,16,17],
        [19,18,20],
        [22,21,23],
        [24,25,26],
        [27,28,29],
        [31,30,32],
        [34,33,35],
            ])
        super().__init__(vertices=vertices, triangles=triangles, uvs=uvs)


class UVSphereMesh(Mesh):
    def __init__(self, radius: float = 1.0, n_meridians: int = 16, n_parallels: int = 16):
        rings = n_parallels
        segments = n_meridians
        
        vertices = []
        triangles = []
        for r in range(rings + 1):
            theta = r * np.pi / rings
            sin_theta = np.sin(theta)
            cos_theta = np.cos(theta)
            for s in range(segments):
                phi = s * 2 * np.pi / segments
                x = radius * sin_theta * np.cos(phi)
                y = radius * sin_theta * np.sin(phi)
                z = radius * cos_theta
                vertices.append([x, y, z])
        for r in range(rings):
            for s in range(segments):
                next_r = r + 1
                next_s = (s + 1) % segments
                triangles.append([r * segments + s, next_r * segments + s, next_r * segments + next_s])
                triangles.append([r * segments + s, next_r * segments + next_s, r * segments + next_s])
        super().__init__(vertices=np.array(vertices, dtype=float), triangles=np.array(triangles, dtype=int))

class IcoSphereMesh(Mesh):
    def __init__(self, radius: float = 1.0, subdivisions: int = 2):
        t = (1.0 + np.sqrt(5.0)) / 2.0
        vertices = np.array(
            [
                [-1, t, 0],
                [1, t, 0],
                [-1, -t, 0],
                [1, -t, 0],
                [0, -1, t],
                [0, 1, t],
                [0, -1, -t],
                [0, 1, -t],
                [t, 0, -1],
                [t, 0, 1],
                [-t, 0, -1],
                [-t, 0, 1],
            ],
            dtype=float,
        )
        vertices /= np.linalg.norm(vertices[0])
        vertices *= radius
        triangles = np.array(
            [
                [0, 11, 5],
                [0, 5, 1],
                [0, 1, 7],
                [0, 7, 10],
                [0, 10, 11],
                [1, 5, 9],
                [5, 11, 4],
                [11, 10, 2],
                [10, 7, 6],
                [7, 1, 8],
                [3, 9, 4],
                [3, 4, 2],
                [3, 2, 6],
                [3, 6, 8],
                [3, 8, 9],
                [4, 9, 5],
                [2, 4, 11],
                [6, 2, 10],
                [8, 6, 7],
                [9, 8, 1],
            ],
            dtype=int,
        )
        super().__init__(vertices=vertices, triangles=triangles)
        for _ in range(subdivisions):
            self._subdivide()

    def _subdivide(self):
        midpoint_cache = {}

        def get_midpoint(v1_idx, v2_idx):
            key = tuple(sorted((v1_idx, v2_idx)))
            if key in midpoint_cache:
                return midpoint_cache[key]
            v1 = self.vertices[v1_idx]
            v2 = self.vertices[v2_idx]
            midpoint = (v1 + v2) / 2.0
            midpoint /= np.linalg.norm(midpoint)
            midpoint *= np.linalg.norm(v1)
            self.vertices = np.vstack((self.vertices, midpoint))
            mid_idx = self.vertices.shape[0] - 1
            midpoint_cache[key] = mid_idx
            return mid_idx

        new_triangles = []
        for tri in self.triangles:
            v0, v1, v2 = tri
            a = get_midpoint(v0, v1)
            b = get_midpoint(v1, v2)
            c = get_midpoint(v2, v0)
            new_triangles.append([v0, a, c])
            new_triangles.append([v1, b, a])
            new_triangles.append([v2, c, b])
            new_triangles.append([a, b, c])
        self.triangles = np.array(new_triangles, dtype=int)

class PlaneMesh(Mesh):
    def __init__(self, width: float = 1.0, depth: float = 1.0, segments_w: int = 1, segments_d: int = 1):
        vertices = []
        triangles = []
        for d in range(segments_d + 1):
            z = (d / segments_d - 0.5) * depth
            for w in range(segments_w + 1):
                x = (w / segments_w - 0.5) * width
                vertices.append([x, 0.0, z])
        for d in range(segments_d):
            for w in range(segments_w):
                v0 = d * (segments_w + 1) + w
                v1 = v0 + 1
                v2 = v0 + (segments_w + 1)
                v3 = v2 + 1
                triangles.append([v0, v2, v1])
                triangles.append([v1, v2, v3])
        super().__init__(vertices=np.array(vertices, dtype=float), triangles=np.array(triangles, dtype=int))

class CylinderMesh(Mesh):
    def __init__(self, radius: float = 1.0, height: float = 1.0, segments: int = 16):
        vertices = []
        triangles = []
        half_height = height * 0.5
        for y in [-half_height, half_height]:
            for s in range(segments):
                theta = s * 2 * np.pi / segments
                x = radius * np.cos(theta)
                z = radius * np.sin(theta)
                vertices.append([x, y, z])
        for s in range(segments):
            next_s = (s + 1) % segments
            bottom0 = s
            bottom1 = next_s
            top0 = s + segments
            top1 = next_s + segments
            triangles.append([bottom0, top0, bottom1])
            triangles.append([bottom1, top0, top1])
        super().__init__(vertices=np.array(vertices, dtype=float), triangles=np.array(triangles, dtype=int))

class ConeMesh(Mesh):
    def __init__(self, radius: float = 1.0, height: float = 1.0, segments: int = 16):
        vertices = []
        triangles = []
        half_height = height * 0.5
        apex = [0.0, half_height, 0.0]
        base_center = [0.0, -half_height, 0.0]
        vertices.append(apex)
        for s in range(segments):
            theta = s * 2 * np.pi / segments
            x = radius * np.cos(theta)
            z = radius * np.sin(theta)
            vertices.append([x, -half_height, z])
        for s in range(segments):
            next_s = (s + 1) % segments
            base0 = s + 1
            base1 = next_s + 1
            triangles.append([0, base0, base1])
            triangles.append([base0, base1, len(vertices)])
        vertices.append(base_center)
        super().__init__(vertices=np.array(vertices, dtype=float), triangles=np.array(triangles, dtype=int))