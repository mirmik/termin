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
&#9;FLOAT32 = &quot;float32&quot;<br>
&#9;INT32 = &quot;int32&quot;<br>
&#9;UINT32 = &quot;uint32&quot;<br>
<br>
class VertexAttribute:<br>
&#9;def __init__(self, name, size, vtype: VertexAttribType, offset):<br>
&#9;&#9;self.name = name<br>
&#9;&#9;self.size = size<br>
&#9;&#9;self.vtype = vtype<br>
&#9;&#9;self.offset = offset<br>
<br>
<br>
<br>
class VertexLayout:<br>
&#9;def __init__(self, stride, attributes):<br>
&#9;&#9;self.stride = stride    # размер одной вершины в байтах<br>
&#9;&#9;self.attributes = attributes  # список VertexAttribute<br>
<br>
<br>
class Mesh:<br>
&#9;def __init__(self, vertices: np.ndarray, indices: np.ndarray):<br>
&#9;&#9;self.vertices = np.asarray(vertices, dtype=np.float32)<br>
&#9;&#9;self.indices  = np.asarray(indices,  dtype=np.uint32)<br>
&#9;&#9;self.type = &quot;triangles&quot; if indices.shape[1] == 3 else &quot;lines&quot;<br>
&#9;&#9;self._inter = None<br>
<br>
&#9;def get_vertex_layout(self) -&gt; VertexLayout:<br>
&#9;&#9;raise NotImplementedError(&quot;get_vertex_layout must be implemented in subclasses.&quot;)<br>
<br>
<br>
<br>
class Mesh2(Mesh):<br>
&#9;&quot;&quot;&quot;Simple triangle mesh storing vertex positions and triangle indices.&quot;&quot;&quot;<br>
<br>
&#9;@staticmethod<br>
&#9;def from_lists(vertices: list[tuple[float, float]], indices: list[tuple[int, int]]) -&gt; &quot;Mesh2&quot;:<br>
&#9;&#9;verts = np.asarray(vertices, dtype=float)<br>
&#9;&#9;idx = np.asarray(indices, dtype=int)<br>
&#9;&#9;return Mesh2(verts, idx)<br>
<br>
&#9;def __init__(self, vertices: np.ndarray, indices: np.ndarray):<br>
&#9;&#9;super().__init__(vertices, indices)<br>
&#9;&#9;self._validate_mesh()<br>
<br>
&#9;def _validate_mesh(self):<br>
&#9;&#9;&quot;&quot;&quot;Ensure that the vertex/index arrays have correct shapes and bounds.&quot;&quot;&quot;<br>
&#9;&#9;if self.vertices.ndim != 2 or self.vertices.shape[1] != 3:<br>
&#9;&#9;&#9;raise ValueError(&quot;Vertices must be a Nx3 array.&quot;)<br>
&#9;&#9;if self.indices.ndim != 2 or self.indices.shape[1] != 2:<br>
&#9;&#9;&#9;raise ValueError(&quot;Indices must be a Mx2 array.&quot;)<br>
<br>
&#9;def interleaved_buffer(self):<br>
&#9;&#9;return self.vertices.astype(np.float32)<br>
<br>
&#9;def get_vertex_layout(self):<br>
&#9;&#9;return VertexLayout(<br>
&#9;&#9;&#9;stride=3*4,<br>
&#9;&#9;&#9;attributes=[<br>
&#9;&#9;&#9;&#9;VertexAttribute(&quot;position&quot;, 3, VertexAttribType.FLOAT32, 0)<br>
&#9;&#9;&#9;]<br>
&#9;&#9;)<br>
<br>
<br>
class Mesh3(Mesh):<br>
&#9;&quot;&quot;&quot;Simple triangle mesh storing vertex positions and triangle indices.&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, vertices: np.ndarray, triangles: np.ndarray, uvs: np.ndarray | None = None):<br>
&#9;&#9;super().__init__(vertices, triangles)<br>
<br>
&#9;&#9;self.uv = np.asarray(uvs, dtype=float) if uvs is not None else None<br>
&#9;&#9;self._validate_mesh()<br>
&#9;&#9;self.vertex_normals = None<br>
&#9;&#9;self.face_normals = None<br>
<br>
&#9;def build_interleaved_buffer(self):<br>
&#9;&#9;# позиции — всегда есть<br>
&#9;&#9;pos = self.vertices.astype(np.float32)<br>
<br>
&#9;&#9;# нормали — если нет, генерим нули<br>
&#9;&#9;if self.vertex_normals is None:<br>
&#9;&#9;&#9;normals = np.zeros_like(self.vertices, dtype=np.float32)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;normals = self.vertex_normals.astype(np.float32)<br>
<br>
&#9;&#9;# uv — если нет, ставим (0,0)<br>
&#9;&#9;if self.uv is None:<br>
&#9;&#9;&#9;uvs = np.zeros((self.vertices.shape[0], 2), dtype=np.float32)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;uvs = self.uv.astype(np.float32)<br>
<br>
&#9;&#9;return np.hstack([pos, normals, uvs])<br>
<br>
&#9;def interleaved_buffer(self):<br>
&#9;&#9;if self._inter == None:<br>
&#9;&#9;&#9;self._inter = self.build_interleaved_buffer()<br>
&#9;&#9;return self._inter<br>
<br>
&#9;@property<br>
&#9;def triangles(self):<br>
&#9;&#9;return self.indices<br>
&#9;<br>
&#9;@triangles.setter<br>
&#9;def triangles(self, value):<br>
&#9;&#9;self.indices = value<br>
<br>
&#9;def get_vertex_layout(self) -&gt; VertexLayout:<br>
&#9;&#9;return VertexLayout(<br>
&#9;&#9;&#9;stride=8 * 4,  # всегда: pos(3) + normal(3) + uv(2)<br>
&#9;&#9;&#9;attributes=[<br>
&#9;&#9;&#9;&#9;VertexAttribute(&quot;position&quot;, 3, VertexAttribType.FLOAT32, 0),<br>
&#9;&#9;&#9;&#9;VertexAttribute(&quot;normal&quot;,   3, VertexAttribType.FLOAT32, 12),<br>
&#9;&#9;&#9;&#9;VertexAttribute(&quot;uv&quot;,       2, VertexAttribType.FLOAT32, 24),<br>
&#9;&#9;&#9;]<br>
&#9;&#9;)<br>
<br>
&#9;def _validate_mesh(self):<br>
&#9;&#9;&quot;&quot;&quot;Ensure that the vertex/index arrays have correct shapes and bounds.&quot;&quot;&quot;<br>
&#9;&#9;if self.vertices.ndim != 2 or self.vertices.shape[1] != 3:<br>
&#9;&#9;&#9;raise ValueError(&quot;Vertices must be a Nx3 array.&quot;)<br>
&#9;&#9;if self.triangles.ndim != 2 or self.triangles.shape[1] != 3:<br>
&#9;&#9;&#9;raise ValueError(&quot;Triangles must be a Mx3 array.&quot;)<br>
&#9;&#9;if np.any(self.triangles &lt; 0) or np.any(self.triangles &gt;= self.vertices.shape[0]):<br>
&#9;&#9;&#9;raise ValueError(&quot;Triangle indices must be valid vertex indices.&quot;)<br>
<br>
&#9;def translate(self, offset: np.ndarray):<br>
&#9;&#9;&quot;&quot;&quot;Apply translation by vector ``offset`` to all vertices.&quot;&quot;&quot;<br>
&#9;&#9;offset = np.asarray(offset, dtype=float)<br>
&#9;&#9;if offset.shape != (3,):<br>
&#9;&#9;&#9;raise ValueError(&quot;Offset must be a 3-dimensional vector.&quot;)<br>
&#9;&#9;self.vertices += offset<br>
<br>
&#9;def show(self):<br>
&#9;&#9;&quot;&quot;&quot;Show the mesh in a simple viewer application.&quot;&quot;&quot;<br>
&#9;&#9;from .mesh_viewer_miniapp import show_mesh_app<br>
&#9;&#9;show_mesh_app(self)<br>
<br>
&#9;@staticmethod<br>
&#9;def from_assimp_mesh(assimp_mesh) -&gt; &quot;Mesh&quot;:<br>
&#9;&#9;&#9;verts = np.asarray(assimp_mesh.vertices, dtype=float)<br>
&#9;&#9;&#9;idx = np.asarray(assimp_mesh.indices, dtype=int).reshape(-1, 3)<br>
<br>
&#9;&#9;&#9;if assimp_mesh.uvs is not None:<br>
&#9;&#9;&#9;&#9;uvs = np.asarray(assimp_mesh.uvs, dtype=float)<br>
&#9;&#9;&#9;else:<br>
&#9;&#9;&#9;&#9;uvs = None<br>
<br>
&#9;&#9;&#9;mesh = Mesh3(vertices=verts, triangles=idx, uvs=uvs)<br>
<br>
&#9;&#9;&#9;# если нормали есть – присвоим<br>
&#9;&#9;&#9;if assimp_mesh.normals is not None:<br>
&#9;&#9;&#9;&#9;mesh.vertex_normals = np.asarray(assimp_mesh.normals, dtype=float)<br>
&#9;&#9;&#9;else:<br>
&#9;&#9;&#9;&#9;mesh.compute_vertex_normals()<br>
<br>
&#9;&#9;&#9;return mesh<br>
<br>
<br>
&#9;def scale(self, factor: float):<br>
&#9;&#9;&quot;&quot;&quot;Uniformly scale vertex positions by ``factor``.&quot;&quot;&quot;<br>
&#9;&#9;self.vertices *= factor<br>
<br>
&#9;def get_vertex_count(self) -&gt; int:<br>
&#9;&#9;return self.vertices.shape[0]<br>
<br>
&#9;def get_face_count(self) -&gt; int:<br>
&#9;&#9;return self.triangles.shape[0]<br>
<br>
&#9;def compute_faces_normals(self):<br>
&#9;&#9;&quot;&quot;&quot;Compute per-face normals ``n = (v1-v0) × (v2-v0) / ||...||``.&quot;&quot;&quot;<br>
&#9;&#9;v0 = self.vertices[self.triangles[:, 0], :]<br>
&#9;&#9;v1 = self.vertices[self.triangles[:, 1], :]<br>
&#9;&#9;v2 = self.vertices[self.triangles[:, 2], :]<br>
&#9;&#9;normals = np.cross(v1 - v0, v2 - v0)<br>
&#9;&#9;norms = np.linalg.norm(normals, axis=1, keepdims=True)<br>
&#9;&#9;norms[norms == 0] = 1  # Prevent division by zero<br>
&#9;&#9;self.face_normals = normals / norms<br>
&#9;&#9;return self.face_normals<br>
<br>
&#9;def compute_vertex_normals(self):<br>
&#9;&#9;&quot;&quot;&quot;Compute area-weighted vertex normals: ``n_v = sum_{t∈F(v)} ( (v1-v0) × (v2-v0) ).``&quot;&quot;&quot;<br>
&#9;&#9;normals = np.zeros_like(self.vertices, dtype=np.float64)<br>
&#9;&#9;v0 = self.vertices[self.triangles[:, 0], :]<br>
&#9;&#9;v1 = self.vertices[self.triangles[:, 1], :]<br>
&#9;&#9;v2 = self.vertices[self.triangles[:, 2], :]<br>
&#9;&#9;face_normals = np.cross(v1 - v0, v2 - v0)<br>
&#9;&#9;for face, normal in zip(self.triangles, face_normals):<br>
&#9;&#9;&#9;normals[face] += normal<br>
&#9;&#9;norms = np.linalg.norm(normals, axis=1)<br>
&#9;&#9;norms[norms == 0] = 1.0<br>
&#9;&#9;self.vertex_normals = (normals.T / norms).T.astype(np.float32)<br>
&#9;&#9;return self.vertex_normals<br>
<br>
&#9;@staticmethod<br>
&#9;def from_convex_hull(hull) -&gt; &quot;Mesh3&quot;:<br>
&#9;&#9;&quot;&quot;&quot;Create a Mesh from a scipy.spatial.ConvexHull object.&quot;&quot;&quot;<br>
&#9;&#9;vertices = hull.points<br>
&#9;&#9;triangles = hull.simplices<br>
<br>
&#9;&#9;center = np.mean(vertices, axis=0)<br>
<br>
&#9;&#9;for i in range(triangles.shape[0]):<br>
&#9;&#9;&#9;v0 = vertices[triangles[i, 0]]<br>
&#9;&#9;&#9;v1 = vertices[triangles[i, 1]]<br>
&#9;&#9;&#9;v2 = vertices[triangles[i, 2]]<br>
&#9;&#9;&#9;normal = np.cross(v1 - v0, v2 - v0)<br>
&#9;&#9;&#9;to_center = center - v0<br>
&#9;&#9;&#9;if np.dot(normal, to_center) &gt; 0:<br>
&#9;&#9;&#9;&#9;triangles[i, [1, 2]] = triangles[i, [2, 1]]<br>
<br>
&#9;&#9;return Mesh3(vertices=vertices, triangles=triangles)<br>
<br>
class CubeMesh(Mesh3):<br>
&#9;def __init__(self, size: float = 1.0, y: float = None, z: float = None):<br>
&#9;&#9;x = size<br>
&#9;&#9;if y is None:<br>
&#9;&#9;&#9;y = x<br>
&#9;&#9;if z is None:<br>
&#9;&#9;&#9;z = x<br>
&#9;&#9;s_x = x * 0.5<br>
&#9;&#9;s_y = y * 0.5<br>
&#9;&#9;s_z = z * 0.5<br>
&#9;&#9;vertices = np.array(<br>
&#9;&#9;&#9;[<br>
&#9;&#9;&#9;&#9;[-s_x, -s_y, -s_z],<br>
&#9;&#9;&#9;&#9;[s_x, -s_y, -s_z],<br>
&#9;&#9;&#9;&#9;[s_x, s_y, -s_z],<br>
&#9;&#9;&#9;&#9;[-s_x, s_y, -s_z],<br>
&#9;&#9;&#9;&#9;[-s_x, -s_y, s_z],<br>
&#9;&#9;&#9;&#9;[s_x, -s_y, s_z],<br>
&#9;&#9;&#9;&#9;[s_x, s_y, s_z],<br>
&#9;&#9;&#9;&#9;[-s_x, s_y, s_z],<br>
&#9;&#9;&#9;],<br>
&#9;&#9;&#9;dtype=float,<br>
&#9;&#9;)<br>
&#9;&#9;triangles = np.array(<br>
&#9;&#9;&#9;[<br>
&#9;&#9;&#9;&#9;[1, 0, 2],<br>
&#9;&#9;&#9;&#9;[2, 0, 3],<br>
&#9;&#9;&#9;&#9;[4, 5, 7],<br>
&#9;&#9;&#9;&#9;[5, 6, 7],<br>
&#9;&#9;&#9;&#9;[0, 1, 4],<br>
&#9;&#9;&#9;&#9;[1, 5, 4],<br>
&#9;&#9;&#9;&#9;[2, 3, 6],<br>
&#9;&#9;&#9;&#9;[3, 7, 6],<br>
&#9;&#9;&#9;&#9;[3, 0, 4],<br>
&#9;&#9;&#9;&#9;[7, 3, 4],<br>
&#9;&#9;&#9;&#9;[1, 2, 5],<br>
&#9;&#9;&#9;&#9;[2, 6, 5],<br>
&#9;&#9;&#9;],<br>
&#9;&#9;&#9;dtype=int,<br>
&#9;&#9;)<br>
&#9;&#9;uvs = np.array([<br>
&#9;&#9;&#9;[0.0, 0.0],<br>
&#9;&#9;&#9;[1.0, 0.0],<br>
&#9;&#9;&#9;[1.0, 1.0],<br>
&#9;&#9;&#9;[0.0, 1.0],<br>
&#9;&#9;&#9;[0.0, 0.0],<br>
&#9;&#9;&#9;[1.0, 0.0],<br>
&#9;&#9;&#9;[1.0, 1.0],<br>
&#9;&#9;&#9;[0.0, 1.0],<br>
&#9;&#9;], dtype=float)<br>
&#9;&#9;super().__init__(vertices=vertices, triangles=triangles, uvs=uvs)<br>
<br>
<br>
class TexturedCubeMesh(Mesh3):<br>
&#9;def __init__(self, size: float = 1.0, y: float = None, z: float = None):<br>
&#9;&#9;x = size<br>
&#9;&#9;if y is None:<br>
&#9;&#9;&#9;y = x<br>
&#9;&#9;if z is None:<br>
&#9;&#9;&#9;z = x<br>
&#9;&#9;s_x = x * 0.5<br>
&#9;&#9;s_y = y * 0.5<br>
&#9;&#9;s_z = z * 0.5<br>
&#9;&#9;vertices = np.array([<br>
&#9;&#9;[-0.5, -0.5, -0.5],  #0.0f, 0.0f,<br>
&#9;&#9;[0.5, -0.5, -0.5],  #1.0f, 0.0f,<br>
&#9;&#9;[0.5,  0.5, -0.5],  #1.0f, 1.0f,<br>
&#9;&#9;[ 0.5,  0.5, -0.5],  #1.0f, 1.0f,<br>
&#9;&#9;[-0.5,  0.5, -0.5],  #0.0f, 1.0f,<br>
&#9;&#9;[-0.5, -0.5, -0.5],  #0.0f, 0.0f,<br>
<br>
&#9;&#9;[-0.5, -0.5,  0.5],  #0.0f, 0.0f,<br>
&#9;&#9;[0.5, -0.5,  0.5],  #1.0f, 0.0f,<br>
&#9;&#9;[0.5,  0.5,  0.5],  #1.0f, 1.0f,<br>
&#9;&#9;[0.5,  0.5,  0.5],  #1.0f, 1.0f,<br>
&#9;&#9;[-0.5,  0.5,  0.5],  #0.0f, 1.0f,<br>
&#9;&#9;[-0.5, -0.5,  0.5],  #0.0f, 0.0f,<br>
<br>
&#9;&#9;[-0.5,  0.5,  0.5],  #1.0f, 0.0f,<br>
&#9;&#9;[-0.5,  0.5, -0.5],  #1.0f, 1.0f,<br>
&#9;&#9;[-0.5, -0.5, -0.5],  #0.0f, 1.0f,<br>
&#9;&#9;[-0.5, -0.5, -0.5],  #0.0f, 1.0f,<br>
&#9;&#9;[-0.5, -0.5,  0.5],  #0.0f, 0.0f,<br>
&#9;&#9;[-0.5,  0.5,  0.5],  #1.0f, 0.0f,<br>
<br>
&#9;&#9;[0.5,  0.5,  0.5],  #1.0f, 0.0f,<br>
&#9;&#9;[0.5,  0.5, -0.5],  #1.0f, 1.0f,<br>
&#9;&#9;[0.5, -0.5, -0.5],  #0.0f, 1.0f,<br>
&#9;&#9;[0.5, -0.5, -0.5],  #0.0f, 1.0f,<br>
&#9;&#9;[0.5, -0.5,  0.5],  #0.0f, 0.0f,<br>
&#9;&#9;[0.5,  0.5,  0.5],  #1.0f, 0.0f,<br>
<br>
&#9;&#9;[-0.5, -0.5, -0.5],  #0.0f, 1.0f,<br>
&#9;&#9;[0.5, -0.5, -0.5],  #1.0f, 1.0f,<br>
&#9;&#9;[0.5, -0.5,  0.5],  #1.0f, 0.0f,<br>
&#9;&#9;[0.5, -0.5,  0.5],  #1.0f, 0.0f,<br>
&#9;&#9;[-0.5, -0.5,  0.5],  #0.0f, 0.0f,<br>
&#9;&#9;[-0.5, -0.5, -0.5],  #0.0f, 1.0f,<br>
<br>
&#9;&#9;[-0.5,  0.5, -0.5],  #0.0f, 1.0f,<br>
&#9;&#9;[0.5,  0.5, -0.5],  #1.0f, 1.0f,<br>
&#9;&#9;[0.5,  0.5,  0.5],  #1.0f, 0.0f,<br>
&#9;&#9;[0.5,  0.5,  0.5],  #1.0f, 0.0f,<br>
&#9;&#9;[-0.5,  0.5,  0.5],  #0.0f, 0.0f,<br>
&#9;&#9;[-0.5,  0.5, -0.5],  #0.0f, 1.0f<br>
&#9;&#9;&#9;])<br>
<br>
&#9;&#9;uvs = np.array([<br>
&#9;&#9;[0.0, 0.0],<br>
&#9;&#9;[1.0, 0.0],<br>
&#9;&#9;[1.0, 1.0],<br>
&#9;&#9;[1.0, 1.0],<br>
&#9;&#9;[0.0, 1.0],<br>
&#9;&#9;[0.0, 0.0],<br>
&#9;&#9;<br>
&#9;&#9;[0.0, 0.0],<br>
&#9;&#9;[1.0, 0.0],<br>
&#9;&#9;[1.0, 1.0],<br>
&#9;&#9;[1.0, 1.0],<br>
&#9;&#9;[0.0, 1.0],<br>
&#9;&#9;[0.0, 0.0],<br>
<br>
&#9;&#9;[0.0, 0.0],<br>
&#9;&#9;[1.0, 0.0],<br>
&#9;&#9;[1.0, 1.0],<br>
&#9;&#9;[1.0, 1.0],<br>
&#9;&#9;[0.0, 1.0],<br>
&#9;&#9;[0.0, 0.0],<br>
<br>
&#9;&#9;[0.0, 0.0],<br>
&#9;&#9;[1.0, 0.0],<br>
&#9;&#9;[1.0, 1.0],<br>
&#9;&#9;[1.0, 1.0],<br>
&#9;&#9;[0.0, 1.0],<br>
&#9;&#9;[0.0, 0.0],<br>
<br>
&#9;&#9;[0.0, 0.0],<br>
&#9;&#9;[1.0, 0.0],<br>
&#9;&#9;[1.0, 1.0],<br>
&#9;&#9;[1.0, 1.0],<br>
&#9;&#9;[0.0, 1.0],<br>
&#9;&#9;[0.0, 0.0],<br>
<br>
&#9;&#9;[0.0, 0.0],<br>
&#9;&#9;[1.0, 0.0],<br>
&#9;&#9;[1.0, 1.0],<br>
&#9;&#9;[1.0, 1.0],<br>
&#9;&#9;[0.0, 1.0],<br>
&#9;&#9;[0.0, 0.0],<br>
&#9;&#9;&#9;])<br>
<br>
&#9;&#9;triangles = np.array([<br>
&#9;&#9;[1, 0, 2],<br>
&#9;&#9;[4, 3, 5],<br>
&#9;&#9;[6, 7, 8],<br>
&#9;&#9;[9, 10,11],<br>
&#9;&#9;[12,13,14],<br>
&#9;&#9;[15,16,17],<br>
&#9;&#9;[19,18,20],<br>
&#9;&#9;[22,21,23],<br>
&#9;&#9;[24,25,26],<br>
&#9;&#9;[27,28,29],<br>
&#9;&#9;[31,30,32],<br>
&#9;&#9;[34,33,35],<br>
&#9;&#9;&#9;])<br>
&#9;&#9;super().__init__(vertices=vertices, triangles=triangles, uvs=uvs)<br>
<br>
<br>
class UVSphereMesh(Mesh3):<br>
&#9;def __init__(self, radius: float = 1.0, n_meridians: int = 16, n_parallels: int = 16):<br>
&#9;&#9;rings = n_parallels<br>
&#9;&#9;segments = n_meridians<br>
&#9;&#9;<br>
&#9;&#9;vertices = []<br>
&#9;&#9;triangles = []<br>
&#9;&#9;for r in range(rings + 1):<br>
&#9;&#9;&#9;theta = r * np.pi / rings<br>
&#9;&#9;&#9;sin_theta = np.sin(theta)<br>
&#9;&#9;&#9;cos_theta = np.cos(theta)<br>
&#9;&#9;&#9;for s in range(segments):<br>
&#9;&#9;&#9;&#9;phi = s * 2 * np.pi / segments<br>
&#9;&#9;&#9;&#9;x = radius * sin_theta * np.cos(phi)<br>
&#9;&#9;&#9;&#9;y = radius * sin_theta * np.sin(phi)<br>
&#9;&#9;&#9;&#9;z = radius * cos_theta<br>
&#9;&#9;&#9;&#9;vertices.append([x, y, z])<br>
&#9;&#9;for r in range(rings):<br>
&#9;&#9;&#9;for s in range(segments):<br>
&#9;&#9;&#9;&#9;next_r = r + 1<br>
&#9;&#9;&#9;&#9;next_s = (s + 1) % segments<br>
&#9;&#9;&#9;&#9;triangles.append([r * segments + s, next_r * segments + s, next_r * segments + next_s])<br>
&#9;&#9;&#9;&#9;triangles.append([r * segments + s, next_r * segments + next_s, r * segments + next_s])<br>
&#9;&#9;super().__init__(vertices=np.array(vertices, dtype=float), triangles=np.array(triangles, dtype=int))<br>
<br>
class IcoSphereMesh(Mesh3):<br>
&#9;def __init__(self, radius: float = 1.0, subdivisions: int = 2):<br>
&#9;&#9;t = (1.0 + np.sqrt(5.0)) / 2.0<br>
&#9;&#9;vertices = np.array(<br>
&#9;&#9;&#9;[<br>
&#9;&#9;&#9;&#9;[-1, t, 0],<br>
&#9;&#9;&#9;&#9;[1, t, 0],<br>
&#9;&#9;&#9;&#9;[-1, -t, 0],<br>
&#9;&#9;&#9;&#9;[1, -t, 0],<br>
&#9;&#9;&#9;&#9;[0, -1, t],<br>
&#9;&#9;&#9;&#9;[0, 1, t],<br>
&#9;&#9;&#9;&#9;[0, -1, -t],<br>
&#9;&#9;&#9;&#9;[0, 1, -t],<br>
&#9;&#9;&#9;&#9;[t, 0, -1],<br>
&#9;&#9;&#9;&#9;[t, 0, 1],<br>
&#9;&#9;&#9;&#9;[-t, 0, -1],<br>
&#9;&#9;&#9;&#9;[-t, 0, 1],<br>
&#9;&#9;&#9;],<br>
&#9;&#9;&#9;dtype=float,<br>
&#9;&#9;)<br>
&#9;&#9;vertices /= np.linalg.norm(vertices[0])<br>
&#9;&#9;vertices *= radius<br>
&#9;&#9;triangles = np.array(<br>
&#9;&#9;&#9;[<br>
&#9;&#9;&#9;&#9;[0, 11, 5],<br>
&#9;&#9;&#9;&#9;[0, 5, 1],<br>
&#9;&#9;&#9;&#9;[0, 1, 7],<br>
&#9;&#9;&#9;&#9;[0, 7, 10],<br>
&#9;&#9;&#9;&#9;[0, 10, 11],<br>
&#9;&#9;&#9;&#9;[1, 5, 9],<br>
&#9;&#9;&#9;&#9;[5, 11, 4],<br>
&#9;&#9;&#9;&#9;[11, 10, 2],<br>
&#9;&#9;&#9;&#9;[10, 7, 6],<br>
&#9;&#9;&#9;&#9;[7, 1, 8],<br>
&#9;&#9;&#9;&#9;[3, 9, 4],<br>
&#9;&#9;&#9;&#9;[3, 4, 2],<br>
&#9;&#9;&#9;&#9;[3, 2, 6],<br>
&#9;&#9;&#9;&#9;[3, 6, 8],<br>
&#9;&#9;&#9;&#9;[3, 8, 9],<br>
&#9;&#9;&#9;&#9;[4, 9, 5],<br>
&#9;&#9;&#9;&#9;[2, 4, 11],<br>
&#9;&#9;&#9;&#9;[6, 2, 10],<br>
&#9;&#9;&#9;&#9;[8, 6, 7],<br>
&#9;&#9;&#9;&#9;[9, 8, 1],<br>
&#9;&#9;&#9;],<br>
&#9;&#9;&#9;dtype=int,<br>
&#9;&#9;)<br>
&#9;&#9;super().__init__(vertices=vertices, triangles=triangles)<br>
&#9;&#9;for _ in range(subdivisions):<br>
&#9;&#9;&#9;self._subdivide()<br>
<br>
&#9;def _subdivide(self):<br>
&#9;&#9;midpoint_cache = {}<br>
<br>
&#9;&#9;def get_midpoint(v1_idx, v2_idx):<br>
&#9;&#9;&#9;key = tuple(sorted((v1_idx, v2_idx)))<br>
&#9;&#9;&#9;if key in midpoint_cache:<br>
&#9;&#9;&#9;&#9;return midpoint_cache[key]<br>
&#9;&#9;&#9;v1 = self.vertices[v1_idx]<br>
&#9;&#9;&#9;v2 = self.vertices[v2_idx]<br>
&#9;&#9;&#9;midpoint = (v1 + v2) / 2.0<br>
&#9;&#9;&#9;midpoint /= np.linalg.norm(midpoint)<br>
&#9;&#9;&#9;midpoint *= np.linalg.norm(v1)<br>
&#9;&#9;&#9;self.vertices = np.vstack((self.vertices, midpoint))<br>
&#9;&#9;&#9;mid_idx = self.vertices.shape[0] - 1<br>
&#9;&#9;&#9;midpoint_cache[key] = mid_idx<br>
&#9;&#9;&#9;return mid_idx<br>
<br>
&#9;&#9;new_triangles = []<br>
&#9;&#9;for tri in self.triangles:<br>
&#9;&#9;&#9;v0, v1, v2 = tri<br>
&#9;&#9;&#9;a = get_midpoint(v0, v1)<br>
&#9;&#9;&#9;b = get_midpoint(v1, v2)<br>
&#9;&#9;&#9;c = get_midpoint(v2, v0)<br>
&#9;&#9;&#9;new_triangles.append([v0, a, c])<br>
&#9;&#9;&#9;new_triangles.append([v1, b, a])<br>
&#9;&#9;&#9;new_triangles.append([v2, c, b])<br>
&#9;&#9;&#9;new_triangles.append([a, b, c])<br>
&#9;&#9;self.triangles = np.array(new_triangles, dtype=int)<br>
<br>
class PlaneMesh(Mesh3):<br>
&#9;def __init__(self, width: float = 1.0, depth: float = 1.0, segments_w: int = 1, segments_d: int = 1):<br>
&#9;&#9;vertices = []<br>
&#9;&#9;triangles = []<br>
&#9;&#9;for d in range(segments_d + 1):<br>
&#9;&#9;&#9;z = (d / segments_d - 0.5) * depth<br>
&#9;&#9;&#9;for w in range(segments_w + 1):<br>
&#9;&#9;&#9;&#9;x = (w / segments_w - 0.5) * width<br>
&#9;&#9;&#9;&#9;vertices.append([x, 0.0, z])<br>
&#9;&#9;for d in range(segments_d):<br>
&#9;&#9;&#9;for w in range(segments_w):<br>
&#9;&#9;&#9;&#9;v0 = d * (segments_w + 1) + w<br>
&#9;&#9;&#9;&#9;v1 = v0 + 1<br>
&#9;&#9;&#9;&#9;v2 = v0 + (segments_w + 1)<br>
&#9;&#9;&#9;&#9;v3 = v2 + 1<br>
&#9;&#9;&#9;&#9;triangles.append([v0, v2, v1])<br>
&#9;&#9;&#9;&#9;triangles.append([v1, v2, v3])<br>
&#9;&#9;super().__init__(vertices=np.array(vertices, dtype=float), triangles=np.array(triangles, dtype=int))<br>
<br>
class CylinderMesh(Mesh3):<br>
&#9;def __init__(self, radius: float = 1.0, height: float = 1.0, segments: int = 16):<br>
&#9;&#9;vertices = []<br>
&#9;&#9;triangles = []<br>
&#9;&#9;half_height = height * 0.5<br>
&#9;&#9;for y in [-half_height, half_height]:<br>
&#9;&#9;&#9;for s in range(segments):<br>
&#9;&#9;&#9;&#9;theta = s * 2 * np.pi / segments<br>
&#9;&#9;&#9;&#9;x = radius * np.cos(theta)<br>
&#9;&#9;&#9;&#9;z = radius * np.sin(theta)<br>
&#9;&#9;&#9;&#9;vertices.append([x, y, z])<br>
&#9;&#9;for s in range(segments):<br>
&#9;&#9;&#9;next_s = (s + 1) % segments<br>
&#9;&#9;&#9;bottom0 = s<br>
&#9;&#9;&#9;bottom1 = next_s<br>
&#9;&#9;&#9;top0 = s + segments<br>
&#9;&#9;&#9;top1 = next_s + segments<br>
&#9;&#9;&#9;triangles.append([bottom0, top0, bottom1])<br>
&#9;&#9;&#9;triangles.append([bottom1, top0, top1])<br>
<br>
&#9;&#9;# Add center vertices for bottom and top caps<br>
&#9;&#9;bottom_center_idx = len(vertices)<br>
&#9;&#9;vertices.append([0.0, -half_height, 0.0])<br>
&#9;&#9;top_center_idx = len(vertices)<br>
&#9;&#9;vertices.append([0.0, half_height, 0.0])<br>
&#9;&#9;for s in range(segments):<br>
&#9;&#9;&#9;next_s = (s + 1) % segments<br>
&#9;&#9;&#9;bottom0 = s<br>
&#9;&#9;&#9;bottom1 = next_s<br>
&#9;&#9;&#9;top0 = s + segments<br>
&#9;&#9;&#9;top1 = next_s + segments<br>
&#9;&#9;&#9;triangles.append([bottom1, bottom_center_idx, bottom0])<br>
&#9;&#9;&#9;triangles.append([top0, top_center_idx, top1])<br>
<br>
&#9;&#9;super().__init__(vertices=np.array(vertices, dtype=float), triangles=np.array(triangles, dtype=int))<br>
<br>
class ConeMesh(Mesh3):<br>
&#9;def __init__(self, radius: float = 1.0, height: float = 1.0, segments: int = 16):<br>
&#9;&#9;vertices = []<br>
&#9;&#9;triangles = []<br>
&#9;&#9;half_height = height * 0.5<br>
&#9;&#9;apex = [0.0, half_height, 0.0]<br>
&#9;&#9;base_center = [0.0, -half_height, 0.0]<br>
&#9;&#9;vertices.append(apex)<br>
&#9;&#9;for s in range(segments):<br>
&#9;&#9;&#9;theta = s * 2 * np.pi / segments<br>
&#9;&#9;&#9;x = radius * np.cos(theta)<br>
&#9;&#9;&#9;z = radius * np.sin(theta)<br>
&#9;&#9;&#9;vertices.append([x, -half_height, z])<br>
&#9;&#9;for s in range(segments):<br>
&#9;&#9;&#9;next_s = (s + 1) % segments<br>
&#9;&#9;&#9;base0 = s + 1<br>
&#9;&#9;&#9;base1 = next_s + 1<br>
&#9;&#9;&#9;triangles.append([0, base0, base1])<br>
&#9;&#9;&#9;triangles.append([base0, base1, len(vertices)])<br>
&#9;&#9;vertices.append(base_center)<br>
&#9;&#9;super().__init__(vertices=np.array(vertices, dtype=float), triangles=np.array(triangles, dtype=int))<br>
<br>
class RingMesh(Mesh3):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Плоское кольцо (annulus) в XZ-плоскости.<br>
&#9;Нормаль смотрит вдоль +Y.<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(<br>
&#9;&#9;self,<br>
&#9;&#9;radius: float = 1.0,<br>
&#9;&#9;thickness: float = 0.05,<br>
&#9;&#9;segments: int = 32,<br>
&#9;):<br>
&#9;&#9;if segments &lt; 3:<br>
&#9;&#9;&#9;raise ValueError(&quot;RingMesh: segments must be &gt;= 3&quot;)<br>
<br>
&#9;&#9;# внутренняя/внешняя окружности<br>
&#9;&#9;inner_radius = max(radius - thickness * 0.5, 1e-4)<br>
&#9;&#9;outer_radius = radius + thickness * 0.5<br>
<br>
&#9;&#9;vertices: list[list[float]] = []<br>
&#9;&#9;triangles: list[list[int]] = []<br>
<br>
&#9;&#9;# вершины: [inner_i, outer_i] для каждого сегмента<br>
&#9;&#9;for i in range(segments):<br>
&#9;&#9;&#9;angle = 2.0 * np.pi * i / segments<br>
&#9;&#9;&#9;c = np.cos(angle)<br>
&#9;&#9;&#9;s = np.sin(angle)<br>
<br>
&#9;&#9;&#9;x_inner = inner_radius * c<br>
&#9;&#9;&#9;z_inner = inner_radius * s<br>
&#9;&#9;&#9;x_outer = outer_radius * c<br>
&#9;&#9;&#9;z_outer = outer_radius * s<br>
<br>
&#9;&#9;&#9;vertices.append([x_inner, 0.0, z_inner])  # inner<br>
&#9;&#9;&#9;vertices.append([x_outer, 0.0, z_outer])  # outer<br>
<br>
&#9;&#9;# индексы: два треугольника на &quot;квадратик&quot; между сегментами<br>
&#9;&#9;for i in range(segments):<br>
&#9;&#9;&#9;i_inner = 2 * i<br>
&#9;&#9;&#9;i_outer = 2 * i + 1<br>
&#9;&#9;&#9;next_i = (i + 1) % segments<br>
&#9;&#9;&#9;n_inner = 2 * next_i<br>
&#9;&#9;&#9;n_outer = 2 * next_i + 1<br>
<br>
&#9;&#9;&#9;# следим за порядком обхода, чтобы нормали смотрели в +Y<br>
&#9;&#9;&#9;triangles.append([i_inner, n_inner, i_outer])<br>
&#9;&#9;&#9;triangles.append([i_outer, n_inner, n_outer])<br>
<br>
&#9;&#9;vertices_np = np.asarray(vertices, dtype=float)<br>
&#9;&#9;triangles_np = np.asarray(triangles, dtype=int)<br>
<br>
&#9;&#9;super().__init__(vertices=vertices_np, triangles=triangles_np, uvs=None)<br>
<br>
&#9;&#9;# для более внятного освещения, если оно у тебя есть<br>
&#9;&#9;self.compute_vertex_normals()<br>
<!-- END SCAT CODE -->
</body>
</html>
