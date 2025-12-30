"""Primitive mesh shapes: Cube, Sphere, Cylinder, Cone, Plane, Ring."""

import hashlib
import numpy as np
from .mesh import Mesh3


def _primitive_uuid(name: str, *args) -> str:
    """Compute UUID for primitive from name and parameters."""
    key = f"{name}:{':'.join(str(a) for a in args)}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


class CubeMesh(Mesh3):
    def __init__(self, size: float = 1.0, y: float = None, z: float = None):
        x = size
        if y is None:
            y = x
        if z is None:
            z = x

        uuid = _primitive_uuid("CubeMesh", x, y, z)

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
        super().__init__(vertices=vertices, triangles=triangles, uvs=uvs, name="Cube", uuid=uuid)


class TexturedCubeMesh(Mesh3):
    def __init__(self, size: float = 1.0, y: float = None, z: float = None):
        x = size
        if y is None:
            y = x
        if z is None:
            z = x
        uuid = _primitive_uuid("TexturedCubeMesh", x, y, z)
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
        super().__init__(vertices=vertices, triangles=triangles, uvs=uvs, name="TexturedCube", uuid=uuid)


class UVSphereMesh(Mesh3):
    def __init__(self, radius: float = 1.0, n_meridians: int = 16, n_parallels: int = 16):
        uuid = _primitive_uuid("UVSphereMesh", radius, n_meridians, n_parallels)
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
        super().__init__(vertices=np.array(vertices, dtype=float), triangles=np.array(triangles, dtype=int), name="UVSphere", uuid=uuid)


class IcoSphereMesh(Mesh3):
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
        super().__init__(vertices=vertices, triangles=triangles, name="IcoSphere")
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


class PlaneMesh(Mesh3):
    def __init__(self, width: float = 1.0, depth: float = 1.0, segments_w: int = 1, segments_d: int = 1):
        uuid = _primitive_uuid("PlaneMesh", width, depth, segments_w, segments_d)
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
        super().__init__(vertices=np.array(vertices, dtype=float), triangles=np.array(triangles, dtype=int), name="Plane", uuid=uuid)


class CylinderMesh(Mesh3):
    def __init__(self, radius: float = 1.0, height: float = 1.0, segments: int = 16):
        uuid = _primitive_uuid("CylinderMesh", radius, height, segments)
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

        # Add center vertices for bottom and top caps
        bottom_center_idx = len(vertices)
        vertices.append([0.0, -half_height, 0.0])
        top_center_idx = len(vertices)
        vertices.append([0.0, half_height, 0.0])
        for s in range(segments):
            next_s = (s + 1) % segments
            bottom0 = s
            bottom1 = next_s
            top0 = s + segments
            top1 = next_s + segments
            triangles.append([bottom1, bottom_center_idx, bottom0])
            triangles.append([top0, top_center_idx, top1])

        super().__init__(vertices=np.array(vertices, dtype=float), triangles=np.array(triangles, dtype=int), name="Cylinder", uuid=uuid)


class ConeMesh(Mesh3):
    def __init__(self, radius: float = 1.0, height: float = 1.0, segments: int = 16):
        uuid = _primitive_uuid("ConeMesh", radius, height, segments)
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
            # Боковые грани: нормаль наружу
            triangles.append([0, base1, base0])
            # Основание: нормаль вниз (-Y)
            triangles.append([base0, base1, len(vertices)])
        vertices.append(base_center)
        super().__init__(vertices=np.array(vertices, dtype=float), triangles=np.array(triangles, dtype=int), name="Cone", uuid=uuid)


class TorusMesh(Mesh3):
    """
    Тор (бублик) в XZ-плоскости.

    Параметры:
        major_radius: Расстояние от центра тора до центра трубки
        minor_radius: Радиус трубки
        major_segments: Количество сегментов по большому кругу
        minor_segments: Количество сегментов по трубке
    """

    def __init__(
        self,
        major_radius: float = 1.0,
        minor_radius: float = 0.25,
        major_segments: int = 32,
        minor_segments: int = 16,
    ):
        if major_segments < 3:
            raise ValueError("TorusMesh: major_segments must be >= 3")
        if minor_segments < 3:
            raise ValueError("TorusMesh: minor_segments must be >= 3")

        uuid = _primitive_uuid("TorusMesh", major_radius, minor_radius, major_segments, minor_segments)
        vertices: list[list[float]] = []
        triangles: list[list[int]] = []

        # Генерируем вершины
        for i in range(major_segments):
            u = 2.0 * np.pi * i / major_segments
            cos_u = np.cos(u)
            sin_u = np.sin(u)

            for j in range(minor_segments):
                v = 2.0 * np.pi * j / minor_segments
                cos_v = np.cos(v)
                sin_v = np.sin(v)

                # Параметрическое уравнение тора
                x = (major_radius + minor_radius * cos_v) * cos_u
                y = minor_radius * sin_v
                z = (major_radius + minor_radius * cos_v) * sin_u

                vertices.append([x, y, z])

        # Генерируем треугольники
        for i in range(major_segments):
            next_i = (i + 1) % major_segments
            for j in range(minor_segments):
                next_j = (j + 1) % minor_segments

                # Индексы четырёх вершин квада
                v0 = i * minor_segments + j
                v1 = next_i * minor_segments + j
                v2 = next_i * minor_segments + next_j
                v3 = i * minor_segments + next_j

                # Два треугольника на квад (CCW для нормалей наружу)
                triangles.append([v0, v1, v2])
                triangles.append([v0, v2, v3])

        vertices_np = np.asarray(vertices, dtype=float)
        triangles_np = np.asarray(triangles, dtype=int)

        super().__init__(vertices=vertices_np, triangles=triangles_np, name="Torus", uuid=uuid)
        self.compute_vertex_normals()


class RingMesh(Mesh3):
    """
    Плоское кольцо (annulus) в XZ-плоскости.
    Нормаль смотрит вдоль +Y.
    """

    def __init__(
        self,
        radius: float = 1.0,
        thickness: float = 0.05,
        segments: int = 32,
    ):
        if segments < 3:
            raise ValueError("RingMesh: segments must be >= 3")

        uuid = _primitive_uuid("RingMesh", radius, thickness, segments)

        # внутренняя/внешняя окружности
        inner_radius = max(radius - thickness * 0.5, 1e-4)
        outer_radius = radius + thickness * 0.5

        vertices: list[list[float]] = []
        triangles: list[list[int]] = []

        # вершины: [inner_i, outer_i] для каждого сегмента
        for i in range(segments):
            angle = 2.0 * np.pi * i / segments
            c = np.cos(angle)
            s = np.sin(angle)

            x_inner = inner_radius * c
            z_inner = inner_radius * s
            x_outer = outer_radius * c
            z_outer = outer_radius * s

            vertices.append([x_inner, 0.0, z_inner])  # inner
            vertices.append([x_outer, 0.0, z_outer])  # outer

        # индексы: два треугольника на "квадратик" между сегментами
        for i in range(segments):
            i_inner = 2 * i
            i_outer = 2 * i + 1
            next_i = (i + 1) % segments
            n_inner = 2 * next_i
            n_outer = 2 * next_i + 1

            # следим за порядком обхода, чтобы нормали смотрели в +Y
            triangles.append([i_inner, n_inner, i_outer])
            triangles.append([i_outer, n_inner, n_outer])

        vertices_np = np.asarray(vertices, dtype=float)
        triangles_np = np.asarray(triangles, dtype=int)

        super().__init__(vertices=vertices_np, triangles=triangles_np, name="Ring", uuid=uuid)

        # для более внятного освещения
        self.compute_vertex_normals()
