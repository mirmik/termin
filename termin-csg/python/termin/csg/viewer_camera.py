"""Small orbit camera used by standalone CSG tools."""

from __future__ import annotations

import math

import numpy as np

from termin.geombase import OrbitCamera as _NativeOrbitCamera


def normalize(v):
    n = float(np.linalg.norm(v))
    if n <= 1.0e-8:
        return v
    return v / n


def look_at(eye, target, up):
    f = normalize(target - eye)
    r = normalize(np.cross(f, up))
    u = np.cross(r, f)
    m = np.identity(4, dtype=np.float32)
    m[0, 0:3] = r
    m[1, 0:3] = u
    m[2, 0:3] = -f
    m[0, 3] = -float(np.dot(r, eye))
    m[1, 3] = -float(np.dot(u, eye))
    m[2, 3] = float(np.dot(f, eye))
    return m


def perspective(fovy, aspect, near, far):
    f = 1.0 / math.tan(fovy * 0.5)
    fn = far - near
    m = np.zeros((4, 4), dtype=np.float32)
    m[0, 0] = f / aspect
    m[1, 1] = -f
    m[2, 2] = -far / fn
    m[2, 3] = -(far * near) / fn
    m[3, 2] = -1.0
    return m


class OrbitCamera:
    def __init__(self) -> None:
        self._camera = _NativeOrbitCamera()
        self._camera.distance = 8.0
        self.yaw = math.radians(45.0)
        self.pitch = math.radians(28.0)
        self._camera.fov_y = math.radians(45.0)
        self._camera.near = 0.01
        self._camera.far = 100.0

    @property
    def target(self):
        return np.asarray(self._camera.target, dtype=np.float32)

    @target.setter
    def target(self, value) -> None:
        v = np.asarray(value, dtype=np.float32).reshape(3)
        self._camera.target = (float(v[0]), float(v[1]), float(v[2]))

    @property
    def distance(self) -> float:
        return float(self._camera.distance)

    @distance.setter
    def distance(self, value: float) -> None:
        self._camera.distance = float(value)

    @property
    def yaw(self) -> float:
        return math.pi - float(self._camera.azimuth)

    @yaw.setter
    def yaw(self, value: float) -> None:
        self._camera.azimuth = math.pi - float(value)

    @property
    def pitch(self) -> float:
        return float(self._camera.elevation)

    @pitch.setter
    def pitch(self, value: float) -> None:
        self._camera.elevation = float(value)

    @property
    def fov_y(self) -> float:
        return float(self._camera.fov_y)

    @fov_y.setter
    def fov_y(self, value: float) -> None:
        self._camera.fov_y = float(value)

    @property
    def near(self) -> float:
        return float(self._camera.near)

    @near.setter
    def near(self, value: float) -> None:
        self._camera.near = float(value)

    @property
    def far(self) -> float:
        return float(self._camera.far)

    @far.setter
    def far(self, value: float) -> None:
        self._camera.far = float(value)

    def orbit(self, dx, dy) -> None:
        self._camera.orbit(-float(dx) * 0.01, float(dy) * 0.01)
        limit = math.radians(86.0)
        self.pitch = max(-limit, min(limit, self.pitch))

    def zoom(self, delta) -> None:
        factor = 1.0 - float(delta) * 0.10
        self._camera.zoom(max(0.15, factor))
        self.distance = max(0.05, self.distance)
        self.far = max(self.distance * 20.0, 100.0)
        self.near = 0.01

    def pan(self, dx, dy) -> None:
        self._camera.pan(float(dx), float(dy))

    def screen_axes(self):
        eye = self.eye()
        forward = normalize(self.target - eye)
        world_up = np.array((0.0, 0.0, 1.0), dtype=np.float32)
        right = normalize(np.cross(forward, world_up))
        up = normalize(np.cross(right, forward))
        return right, up

    def fit_bounds(self, lo, hi) -> None:
        center = (lo + hi) * 0.5
        extent = hi - lo
        radius = max(float(np.linalg.norm(extent)) * 0.65, 1.0)
        self.target = center.astype(np.float32)
        self.distance = radius * 2.6
        self._camera.fitted_radius = radius
        self.far = max(self.distance * 20.0, 100.0)
        self.near = 0.01

    def eye(self):
        return np.asarray(self._camera.eye, dtype=np.float32)

    def view_projection(self, width, height):
        aspect = max(float(width) / max(float(height), 1.0), 0.001)
        flat = np.asarray(self._camera.mvp(aspect), dtype=np.float32)
        return flat.reshape((4, 4), order="F")

    def view_matrix(self):
        flat = np.asarray(self._camera.view_matrix(), dtype=np.float64)
        return flat.reshape((4, 4), order="F")

    def projection_matrix(self, width, height):
        aspect = max(float(width) / max(float(height), 1.0), 0.001)
        flat = np.asarray(self._camera.projection_matrix(aspect), dtype=np.float64)
        return flat.reshape((4, 4), order="F")

    def screen_ray(self, screen_x, screen_y, width, height):
        near, direction = self._camera.screen_ray(
            float(screen_x), float(screen_y), float(width), float(height))
        return (
            (float(near[0]), float(near[1]), float(near[2])),
            (float(direction[0]), float(direction[1]), float(direction[2])),
        )

    def world_point_on_z_plane(self, screen_x, screen_y, width, height, z=0.0):
        point = self._camera.world_point_on_z_plane(
            float(screen_x), float(screen_y), float(width), float(height), float(z))
        if point is None:
            return None
        return (float(point[0]), float(point[1]), float(point[2]))


__all__ = [
    "OrbitCamera",
    "look_at",
    "normalize",
    "perspective",
]
