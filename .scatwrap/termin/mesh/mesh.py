<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/mesh/mesh.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
<br>
import numpy as np<br>
from enum import Enum<br>
<br>
# CubeMesh, UVSphereMesh, IcoSphereMesh, PlaneMesh, CylinderMesh, ConeMesh<br>
<br>
# GPU COMPATIBILITY<br>
<br>
class VertexAttribType(Enum):<br>
    FLOAT32 = &quot;float32&quot;<br>
    INT32 = &quot;int32&quot;<br>
    UINT32 = &quot;uint32&quot;<br>
<br>
class VertexAttribute:<br>
    def __init__(self, name, size, vtype: VertexAttribType, offset):<br>
        self.name = name<br>
        self.size = size<br>
        self.vtype = vtype<br>
        self.offset = offset<br>
<br>
<br>
<br>
class VertexLayout:<br>
    def __init__(self, stride, attributes):<br>
        self.stride = stride    # размер одной вершины в байтах<br>
        self.attributes = attributes  # список VertexAttribute<br>
<br>
<br>
class Mesh:<br>
    def __init__(self, vertices: np.ndarray, indices: np.ndarray):<br>
        self.vertices = np.asarray(vertices, dtype=np.float32)<br>
        self.indices  = np.asarray(indices,  dtype=np.uint32)<br>
        self.type = &quot;triangles&quot; if indices.shape[1] == 3 else &quot;lines&quot;<br>
        self._inter = None<br>
<br>
    def get_vertex_layout(self) -&gt; VertexLayout:<br>
        raise NotImplementedError(&quot;get_vertex_layout must be implemented in subclasses.&quot;)<br>
<br>
<br>
<br>
class Mesh2(Mesh):<br>
    &quot;&quot;&quot;Simple triangle mesh storing vertex positions and triangle indices.&quot;&quot;&quot;<br>
<br>
    @staticmethod<br>
    def from_lists(vertices: list[tuple[float, float]], indices: list[tuple[int, int]]) -&gt; &quot;Mesh2&quot;:<br>
        verts = np.asarray(vertices, dtype=float)<br>
        idx = np.asarray(indices, dtype=int)<br>
        return Mesh2(verts, idx)<br>
<br>
    def __init__(self, vertices: np.ndarray, indices: np.ndarray):<br>
        super().__init__(vertices, indices)<br>
        self._validate_mesh()<br>
<br>
    def _validate_mesh(self):<br>
        &quot;&quot;&quot;Ensure that the vertex/index arrays have correct shapes and bounds.&quot;&quot;&quot;<br>
        if self.vertices.ndim != 2 or self.vertices.shape[1] != 3:<br>
            raise ValueError(&quot;Vertices must be a Nx3 array.&quot;)<br>
        if self.indices.ndim != 2 or self.indices.shape[1] != 2:<br>
            raise ValueError(&quot;Indices must be a Mx2 array.&quot;)<br>
<br>
    def interleaved_buffer(self):<br>
        return self.vertices.astype(np.float32)<br>
<br>
    def get_vertex_layout(self):<br>
        return VertexLayout(<br>
            stride=3*4,<br>
            attributes=[<br>
                VertexAttribute(&quot;position&quot;, 3, VertexAttribType.FLOAT32, 0)<br>
            ]<br>
        )<br>
<br>
<br>
class Mesh3(Mesh):<br>
    &quot;&quot;&quot;Simple triangle mesh storing vertex positions and triangle indices.&quot;&quot;&quot;<br>
<br>
    def __init__(self, vertices: np.ndarray, triangles: np.ndarray, uvs: np.ndarray | None = None):<br>
        super().__init__(vertices, triangles)<br>
<br>
        self.uv = np.asarray(uvs, dtype=float) if uvs is not None else None<br>
        self._validate_mesh()<br>
        self.vertex_normals = None<br>
        self.face_normals = None<br>
<br>
    def build_interleaved_buffer(self):<br>
        # позиции — всегда есть<br>
        pos = self.vertices.astype(np.float32)<br>
<br>
        # нормали — если нет, генерим нули<br>
        if self.vertex_normals is None:<br>
            normals = np.zeros_like(self.vertices, dtype=np.float32)<br>
        else:<br>
            normals = self.vertex_normals.astype(np.float32)<br>
<br>
        # uv — если нет, ставим (0,0)<br>
        if self.uv is None:<br>
            uvs = np.zeros((self.vertices.shape[0], 2), dtype=np.float32)<br>
        else:<br>
            uvs = self.uv.astype(np.float32)<br>
<br>
        return np.hstack([pos, normals, uvs])<br>
<br>
    def interleaved_buffer(self):<br>
        if self._inter == None:<br>
            self._inter = self.build_interleaved_buffer()<br>
        return self._inter<br>
<br>
    @property<br>
    def triangles(self):<br>
        return self.indices<br>
    <br>
    @triangles.setter<br>
    def triangles(self, value):<br>
        self.indices = value<br>
<br>
    def get_vertex_layout(self) -&gt; VertexLayout:<br>
        return VertexLayout(<br>
            stride=8 * 4,  # всегда: pos(3) + normal(3) + uv(2)<br>
            attributes=[<br>
                VertexAttribute(&quot;position&quot;, 3, VertexAttribType.FLOAT32, 0),<br>
                VertexAttribute(&quot;normal&quot;,   3, VertexAttribType.FLOAT32, 12),<br>
                VertexAttribute(&quot;uv&quot;,       2, VertexAttribType.FLOAT32, 24),<br>
            ]<br>
        )<br>
<br>
    def _validate_mesh(self):<br>
        &quot;&quot;&quot;Ensure that the vertex/index arrays have correct shapes and bounds.&quot;&quot;&quot;<br>
        if self.vertices.ndim != 2 or self.vertices.shape[1] != 3:<br>
            raise ValueError(&quot;Vertices must be a Nx3 array.&quot;)<br>
        if self.triangles.ndim != 2 or self.triangles.shape[1] != 3:<br>
            raise ValueError(&quot;Triangles must be a Mx3 array.&quot;)<br>
        if np.any(self.triangles &lt; 0) or np.any(self.triangles &gt;= self.vertices.shape[0]):<br>
            raise ValueError(&quot;Triangle indices must be valid vertex indices.&quot;)<br>
<br>
    def translate(self, offset: np.ndarray):<br>
        &quot;&quot;&quot;Apply translation by vector ``offset`` to all vertices.&quot;&quot;&quot;<br>
        offset = np.asarray(offset, dtype=float)<br>
        if offset.shape != (3,):<br>
            raise ValueError(&quot;Offset must be a 3-dimensional vector.&quot;)<br>
        self.vertices += offset<br>
<br>
    def show(self):<br>
        &quot;&quot;&quot;Show the mesh in a simple viewer application.&quot;&quot;&quot;<br>
        from .mesh_viewer_miniapp import show_mesh_app<br>
        show_mesh_app(self)<br>
<br>
    @staticmethod<br>
    def from_assimp_mesh(assimp_mesh) -&gt; &quot;Mesh&quot;:<br>
            verts = np.asarray(assimp_mesh.vertices, dtype=float)<br>
            idx = np.asarray(assimp_mesh.indices, dtype=int).reshape(-1, 3)<br>
<br>
            if assimp_mesh.uvs is not None:<br>
                uvs = np.asarray(assimp_mesh.uvs, dtype=float)<br>
            else:<br>
                uvs = None<br>
<br>
            mesh = Mesh3(vertices=verts, triangles=idx, uvs=uvs)<br>
<br>
            # если нормали есть – присвоим<br>
            if assimp_mesh.normals is not None:<br>
                mesh.vertex_normals = np.asarray(assimp_mesh.normals, dtype=float)<br>
            else:<br>
                mesh.compute_vertex_normals()<br>
<br>
            return mesh<br>
<br>
<br>
    def scale(self, factor: float):<br>
        &quot;&quot;&quot;Uniformly scale vertex positions by ``factor``.&quot;&quot;&quot;<br>
        self.vertices *= factor<br>
<br>
    def get_vertex_count(self) -&gt; int:<br>
        return self.vertices.shape[0]<br>
<br>
    def get_face_count(self) -&gt; int:<br>
        return self.triangles.shape[0]<br>
<br>
    def compute_faces_normals(self):<br>
        &quot;&quot;&quot;Compute per-face normals ``n = (v1-v0) × (v2-v0) / ||...||``.&quot;&quot;&quot;<br>
        v0 = self.vertices[self.triangles[:, 0], :]<br>
        v1 = self.vertices[self.triangles[:, 1], :]<br>
        v2 = self.vertices[self.triangles[:, 2], :]<br>
        normals = np.cross(v1 - v0, v2 - v0)<br>
        norms = np.linalg.norm(normals, axis=1, keepdims=True)<br>
        norms[norms == 0] = 1  # Prevent division by zero<br>
        self.face_normals = normals / norms<br>
        return self.face_normals<br>
<br>
    def compute_vertex_normals(self):<br>
        &quot;&quot;&quot;Compute area-weighted vertex normals: ``n_v = sum_{t∈F(v)} ( (v1-v0) × (v2-v0) ).``&quot;&quot;&quot;<br>
        normals = np.zeros_like(self.vertices, dtype=np.float64)<br>
        v0 = self.vertices[self.triangles[:, 0], :]<br>
        v1 = self.vertices[self.triangles[:, 1], :]<br>
        v2 = self.vertices[self.triangles[:, 2], :]<br>
        face_normals = np.cross(v1 - v0, v2 - v0)<br>
        for face, normal in zip(self.triangles, face_normals):<br>
            normals[face] += normal<br>
        norms = np.linalg.norm(normals, axis=1)<br>
        norms[norms == 0] = 1.0<br>
        self.vertex_normals = (normals.T / norms).T.astype(np.float32)<br>
        return self.vertex_normals<br>
<br>
    @staticmethod<br>
    def from_convex_hull(hull) -&gt; &quot;Mesh3&quot;:<br>
        &quot;&quot;&quot;Create a Mesh from a scipy.spatial.ConvexHull object.&quot;&quot;&quot;<br>
        vertices = hull.points<br>
        triangles = hull.simplices<br>
<br>
        center = np.mean(vertices, axis=0)<br>
<br>
        for i in range(triangles.shape[0]):<br>
            v0 = vertices[triangles[i, 0]]<br>
            v1 = vertices[triangles[i, 1]]<br>
            v2 = vertices[triangles[i, 2]]<br>
            normal = np.cross(v1 - v0, v2 - v0)<br>
            to_center = center - v0<br>
            if np.dot(normal, to_center) &gt; 0:<br>
                triangles[i, [1, 2]] = triangles[i, [2, 1]]<br>
<br>
        return Mesh3(vertices=vertices, triangles=triangles)<br>
<br>
class CubeMesh(Mesh3):<br>
    def __init__(self, size: float = 1.0, y: float = None, z: float = None):<br>
        x = size<br>
        if y is None:<br>
            y = x<br>
        if z is None:<br>
            z = x<br>
        s_x = x * 0.5<br>
        s_y = y * 0.5<br>
        s_z = z * 0.5<br>
        vertices = np.array(<br>
            [<br>
                [-s_x, -s_y, -s_z],<br>
                [s_x, -s_y, -s_z],<br>
                [s_x, s_y, -s_z],<br>
                [-s_x, s_y, -s_z],<br>
                [-s_x, -s_y, s_z],<br>
                [s_x, -s_y, s_z],<br>
                [s_x, s_y, s_z],<br>
                [-s_x, s_y, s_z],<br>
            ],<br>
            dtype=float,<br>
        )<br>
        triangles = np.array(<br>
            [<br>
                [1, 0, 2],<br>
                [2, 0, 3],<br>
                [4, 5, 7],<br>
                [5, 6, 7],<br>
                [0, 1, 4],<br>
                [1, 5, 4],<br>
                [2, 3, 6],<br>
                [3, 7, 6],<br>
                [3, 0, 4],<br>
                [7, 3, 4],<br>
                [1, 2, 5],<br>
                [2, 6, 5],<br>
            ],<br>
            dtype=int,<br>
        )<br>
        uvs = np.array([<br>
            [0.0, 0.0],<br>
            [1.0, 0.0],<br>
            [1.0, 1.0],<br>
            [0.0, 1.0],<br>
            [0.0, 0.0],<br>
            [1.0, 0.0],<br>
            [1.0, 1.0],<br>
            [0.0, 1.0],<br>
        ], dtype=float)<br>
        super().__init__(vertices=vertices, triangles=triangles, uvs=uvs)<br>
<br>
<br>
class TexturedCubeMesh(Mesh3):<br>
    def __init__(self, size: float = 1.0, y: float = None, z: float = None):<br>
        x = size<br>
        if y is None:<br>
            y = x<br>
        if z is None:<br>
            z = x<br>
        s_x = x * 0.5<br>
        s_y = y * 0.5<br>
        s_z = z * 0.5<br>
        vertices = np.array([<br>
        [-0.5, -0.5, -0.5],  #0.0f, 0.0f,<br>
        [0.5, -0.5, -0.5],  #1.0f, 0.0f,<br>
        [0.5,  0.5, -0.5],  #1.0f, 1.0f,<br>
        [ 0.5,  0.5, -0.5],  #1.0f, 1.0f,<br>
        [-0.5,  0.5, -0.5],  #0.0f, 1.0f,<br>
        [-0.5, -0.5, -0.5],  #0.0f, 0.0f,<br>
<br>
        [-0.5, -0.5,  0.5],  #0.0f, 0.0f,<br>
         [0.5, -0.5,  0.5],  #1.0f, 0.0f,<br>
         [0.5,  0.5,  0.5],  #1.0f, 1.0f,<br>
         [0.5,  0.5,  0.5],  #1.0f, 1.0f,<br>
        [-0.5,  0.5,  0.5],  #0.0f, 1.0f,<br>
        [-0.5, -0.5,  0.5],  #0.0f, 0.0f,<br>
<br>
        [-0.5,  0.5,  0.5],  #1.0f, 0.0f,<br>
        [-0.5,  0.5, -0.5],  #1.0f, 1.0f,<br>
        [-0.5, -0.5, -0.5],  #0.0f, 1.0f,<br>
        [-0.5, -0.5, -0.5],  #0.0f, 1.0f,<br>
        [-0.5, -0.5,  0.5],  #0.0f, 0.0f,<br>
        [-0.5,  0.5,  0.5],  #1.0f, 0.0f,<br>
<br>
         [0.5,  0.5,  0.5],  #1.0f, 0.0f,<br>
         [0.5,  0.5, -0.5],  #1.0f, 1.0f,<br>
         [0.5, -0.5, -0.5],  #0.0f, 1.0f,<br>
         [0.5, -0.5, -0.5],  #0.0f, 1.0f,<br>
         [0.5, -0.5,  0.5],  #0.0f, 0.0f,<br>
         [0.5,  0.5,  0.5],  #1.0f, 0.0f,<br>
<br>
        [-0.5, -0.5, -0.5],  #0.0f, 1.0f,<br>
         [0.5, -0.5, -0.5],  #1.0f, 1.0f,<br>
         [0.5, -0.5,  0.5],  #1.0f, 0.0f,<br>
         [0.5, -0.5,  0.5],  #1.0f, 0.0f,<br>
        [-0.5, -0.5,  0.5],  #0.0f, 0.0f,<br>
        [-0.5, -0.5, -0.5],  #0.0f, 1.0f,<br>
<br>
        [-0.5,  0.5, -0.5],  #0.0f, 1.0f,<br>
         [0.5,  0.5, -0.5],  #1.0f, 1.0f,<br>
         [0.5,  0.5,  0.5],  #1.0f, 0.0f,<br>
         [0.5,  0.5,  0.5],  #1.0f, 0.0f,<br>
        [-0.5,  0.5,  0.5],  #0.0f, 0.0f,<br>
        [-0.5,  0.5, -0.5],  #0.0f, 1.0f<br>
            ])<br>
<br>
        uvs = np.array([<br>
        [0.0, 0.0],<br>
        [1.0, 0.0],<br>
        [1.0, 1.0],<br>
        [1.0, 1.0],<br>
        [0.0, 1.0],<br>
        [0.0, 0.0],<br>
        <br>
        [0.0, 0.0],<br>
        [1.0, 0.0],<br>
        [1.0, 1.0],<br>
        [1.0, 1.0],<br>
        [0.0, 1.0],<br>
        [0.0, 0.0],<br>
<br>
        [0.0, 0.0],<br>
        [1.0, 0.0],<br>
        [1.0, 1.0],<br>
        [1.0, 1.0],<br>
        [0.0, 1.0],<br>
        [0.0, 0.0],<br>
<br>
        [0.0, 0.0],<br>
        [1.0, 0.0],<br>
        [1.0, 1.0],<br>
        [1.0, 1.0],<br>
        [0.0, 1.0],<br>
        [0.0, 0.0],<br>
<br>
        [0.0, 0.0],<br>
        [1.0, 0.0],<br>
        [1.0, 1.0],<br>
        [1.0, 1.0],<br>
        [0.0, 1.0],<br>
        [0.0, 0.0],<br>
<br>
        [0.0, 0.0],<br>
        [1.0, 0.0],<br>
        [1.0, 1.0],<br>
        [1.0, 1.0],<br>
        [0.0, 1.0],<br>
        [0.0, 0.0],<br>
            ])<br>
<br>
        triangles = np.array([<br>
        [1, 0, 2],<br>
        [4, 3, 5],<br>
        [6, 7, 8],<br>
        [9, 10,11],<br>
        [12,13,14],<br>
        [15,16,17],<br>
        [19,18,20],<br>
        [22,21,23],<br>
        [24,25,26],<br>
        [27,28,29],<br>
        [31,30,32],<br>
        [34,33,35],<br>
            ])<br>
        super().__init__(vertices=vertices, triangles=triangles, uvs=uvs)<br>
<br>
<br>
class UVSphereMesh(Mesh3):<br>
    def __init__(self, radius: float = 1.0, n_meridians: int = 16, n_parallels: int = 16):<br>
        rings = n_parallels<br>
        segments = n_meridians<br>
        <br>
        vertices = []<br>
        triangles = []<br>
        for r in range(rings + 1):<br>
            theta = r * np.pi / rings<br>
            sin_theta = np.sin(theta)<br>
            cos_theta = np.cos(theta)<br>
            for s in range(segments):<br>
                phi = s * 2 * np.pi / segments<br>
                x = radius * sin_theta * np.cos(phi)<br>
                y = radius * sin_theta * np.sin(phi)<br>
                z = radius * cos_theta<br>
                vertices.append([x, y, z])<br>
        for r in range(rings):<br>
            for s in range(segments):<br>
                next_r = r + 1<br>
                next_s = (s + 1) % segments<br>
                triangles.append([r * segments + s, next_r * segments + s, next_r * segments + next_s])<br>
                triangles.append([r * segments + s, next_r * segments + next_s, r * segments + next_s])<br>
        super().__init__(vertices=np.array(vertices, dtype=float), triangles=np.array(triangles, dtype=int))<br>
<br>
class IcoSphereMesh(Mesh3):<br>
    def __init__(self, radius: float = 1.0, subdivisions: int = 2):<br>
        t = (1.0 + np.sqrt(5.0)) / 2.0<br>
        vertices = np.array(<br>
            [<br>
                [-1, t, 0],<br>
                [1, t, 0],<br>
                [-1, -t, 0],<br>
                [1, -t, 0],<br>
                [0, -1, t],<br>
                [0, 1, t],<br>
                [0, -1, -t],<br>
                [0, 1, -t],<br>
                [t, 0, -1],<br>
                [t, 0, 1],<br>
                [-t, 0, -1],<br>
                [-t, 0, 1],<br>
            ],<br>
            dtype=float,<br>
        )<br>
        vertices /= np.linalg.norm(vertices[0])<br>
        vertices *= radius<br>
        triangles = np.array(<br>
            [<br>
                [0, 11, 5],<br>
                [0, 5, 1],<br>
                [0, 1, 7],<br>
                [0, 7, 10],<br>
                [0, 10, 11],<br>
                [1, 5, 9],<br>
                [5, 11, 4],<br>
                [11, 10, 2],<br>
                [10, 7, 6],<br>
                [7, 1, 8],<br>
                [3, 9, 4],<br>
                [3, 4, 2],<br>
                [3, 2, 6],<br>
                [3, 6, 8],<br>
                [3, 8, 9],<br>
                [4, 9, 5],<br>
                [2, 4, 11],<br>
                [6, 2, 10],<br>
                [8, 6, 7],<br>
                [9, 8, 1],<br>
            ],<br>
            dtype=int,<br>
        )<br>
        super().__init__(vertices=vertices, triangles=triangles)<br>
        for _ in range(subdivisions):<br>
            self._subdivide()<br>
<br>
    def _subdivide(self):<br>
        midpoint_cache = {}<br>
<br>
        def get_midpoint(v1_idx, v2_idx):<br>
            key = tuple(sorted((v1_idx, v2_idx)))<br>
            if key in midpoint_cache:<br>
                return midpoint_cache[key]<br>
            v1 = self.vertices[v1_idx]<br>
            v2 = self.vertices[v2_idx]<br>
            midpoint = (v1 + v2) / 2.0<br>
            midpoint /= np.linalg.norm(midpoint)<br>
            midpoint *= np.linalg.norm(v1)<br>
            self.vertices = np.vstack((self.vertices, midpoint))<br>
            mid_idx = self.vertices.shape[0] - 1<br>
            midpoint_cache[key] = mid_idx<br>
            return mid_idx<br>
<br>
        new_triangles = []<br>
        for tri in self.triangles:<br>
            v0, v1, v2 = tri<br>
            a = get_midpoint(v0, v1)<br>
            b = get_midpoint(v1, v2)<br>
            c = get_midpoint(v2, v0)<br>
            new_triangles.append([v0, a, c])<br>
            new_triangles.append([v1, b, a])<br>
            new_triangles.append([v2, c, b])<br>
            new_triangles.append([a, b, c])<br>
        self.triangles = np.array(new_triangles, dtype=int)<br>
<br>
class PlaneMesh(Mesh3):<br>
    def __init__(self, width: float = 1.0, depth: float = 1.0, segments_w: int = 1, segments_d: int = 1):<br>
        vertices = []<br>
        triangles = []<br>
        for d in range(segments_d + 1):<br>
            z = (d / segments_d - 0.5) * depth<br>
            for w in range(segments_w + 1):<br>
                x = (w / segments_w - 0.5) * width<br>
                vertices.append([x, 0.0, z])<br>
        for d in range(segments_d):<br>
            for w in range(segments_w):<br>
                v0 = d * (segments_w + 1) + w<br>
                v1 = v0 + 1<br>
                v2 = v0 + (segments_w + 1)<br>
                v3 = v2 + 1<br>
                triangles.append([v0, v2, v1])<br>
                triangles.append([v1, v2, v3])<br>
        super().__init__(vertices=np.array(vertices, dtype=float), triangles=np.array(triangles, dtype=int))<br>
<br>
class CylinderMesh(Mesh3):<br>
    def __init__(self, radius: float = 1.0, height: float = 1.0, segments: int = 16):<br>
        vertices = []<br>
        triangles = []<br>
        half_height = height * 0.5<br>
        for y in [-half_height, half_height]:<br>
            for s in range(segments):<br>
                theta = s * 2 * np.pi / segments<br>
                x = radius * np.cos(theta)<br>
                z = radius * np.sin(theta)<br>
                vertices.append([x, y, z])<br>
        for s in range(segments):<br>
            next_s = (s + 1) % segments<br>
            bottom0 = s<br>
            bottom1 = next_s<br>
            top0 = s + segments<br>
            top1 = next_s + segments<br>
            triangles.append([bottom0, top0, bottom1])<br>
            triangles.append([bottom1, top0, top1])<br>
<br>
        # Add center vertices for bottom and top caps<br>
        bottom_center_idx = len(vertices)<br>
        vertices.append([0.0, -half_height, 0.0])<br>
        top_center_idx = len(vertices)<br>
        vertices.append([0.0, half_height, 0.0])<br>
        for s in range(segments):<br>
            next_s = (s + 1) % segments<br>
            bottom0 = s<br>
            bottom1 = next_s<br>
            top0 = s + segments<br>
            top1 = next_s + segments<br>
            triangles.append([bottom1, bottom_center_idx, bottom0])<br>
            triangles.append([top0, top_center_idx, top1])<br>
<br>
        super().__init__(vertices=np.array(vertices, dtype=float), triangles=np.array(triangles, dtype=int))<br>
<br>
class ConeMesh(Mesh3):<br>
    def __init__(self, radius: float = 1.0, height: float = 1.0, segments: int = 16):<br>
        vertices = []<br>
        triangles = []<br>
        half_height = height * 0.5<br>
        apex = [0.0, half_height, 0.0]<br>
        base_center = [0.0, -half_height, 0.0]<br>
        vertices.append(apex)<br>
        for s in range(segments):<br>
            theta = s * 2 * np.pi / segments<br>
            x = radius * np.cos(theta)<br>
            z = radius * np.sin(theta)<br>
            vertices.append([x, -half_height, z])<br>
        for s in range(segments):<br>
            next_s = (s + 1) % segments<br>
            base0 = s + 1<br>
            base1 = next_s + 1<br>
            triangles.append([0, base0, base1])<br>
            triangles.append([base0, base1, len(vertices)])<br>
        vertices.append(base_center)<br>
        super().__init__(vertices=np.array(vertices, dtype=float), triangles=np.array(triangles, dtype=int))<br>
<br>
class RingMesh(Mesh3):<br>
    &quot;&quot;&quot;<br>
    Плоское кольцо (annulus) в XZ-плоскости.<br>
    Нормаль смотрит вдоль +Y.<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(<br>
        self,<br>
        radius: float = 1.0,<br>
        thickness: float = 0.05,<br>
        segments: int = 32,<br>
    ):<br>
        if segments &lt; 3:<br>
            raise ValueError(&quot;RingMesh: segments must be &gt;= 3&quot;)<br>
<br>
        # внутренняя/внешняя окружности<br>
        inner_radius = max(radius - thickness * 0.5, 1e-4)<br>
        outer_radius = radius + thickness * 0.5<br>
<br>
        vertices: list[list[float]] = []<br>
        triangles: list[list[int]] = []<br>
<br>
        # вершины: [inner_i, outer_i] для каждого сегмента<br>
        for i in range(segments):<br>
            angle = 2.0 * np.pi * i / segments<br>
            c = np.cos(angle)<br>
            s = np.sin(angle)<br>
<br>
            x_inner = inner_radius * c<br>
            z_inner = inner_radius * s<br>
            x_outer = outer_radius * c<br>
            z_outer = outer_radius * s<br>
<br>
            vertices.append([x_inner, 0.0, z_inner])  # inner<br>
            vertices.append([x_outer, 0.0, z_outer])  # outer<br>
<br>
        # индексы: два треугольника на &quot;квадратик&quot; между сегментами<br>
        for i in range(segments):<br>
            i_inner = 2 * i<br>
            i_outer = 2 * i + 1<br>
            next_i = (i + 1) % segments<br>
            n_inner = 2 * next_i<br>
            n_outer = 2 * next_i + 1<br>
<br>
            # следим за порядком обхода, чтобы нормали смотрели в +Y<br>
            triangles.append([i_inner, n_inner, i_outer])<br>
            triangles.append([i_outer, n_inner, n_outer])<br>
<br>
        vertices_np = np.asarray(vertices, dtype=float)<br>
        triangles_np = np.asarray(triangles, dtype=int)<br>
<br>
        super().__init__(vertices=vertices_np, triangles=triangles_np, uvs=None)<br>
<br>
        # для более внятного освещения, если оно у тебя есть<br>
        self.compute_vertex_normals()<br>
<!-- END SCAT CODE -->
</body>
</html>
