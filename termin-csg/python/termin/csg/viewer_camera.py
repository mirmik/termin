"""Small orbit camera used by standalone CSG tools."""

from __future__ import annotations

import math

import numpy as np


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
        self.target = np.array((0.0, 0.0, 0.0), dtype=np.float32)
        self.distance = 8.0
        self.yaw = math.radians(45.0)
        self.pitch = math.radians(28.0)
        self.fov_y = math.radians(45.0)
        self.near = 0.01
        self.far = 100.0

    def orbit(self, dx, dy) -> None:
        self.yaw += float(dx) * 0.01
        self.pitch += float(dy) * 0.01
        limit = math.radians(86.0)
        self.pitch = max(-limit, min(limit, self.pitch))

    def zoom(self, delta) -> None:
        factor = 1.0 - float(delta) * 0.10
        self.distance = max(0.05, self.distance * max(0.15, factor))

    def fit_bounds(self, lo, hi) -> None:
        center = (lo + hi) * 0.5
        extent = hi - lo
        radius = max(float(np.linalg.norm(extent)) * 0.65, 1.0)
        self.target = center.astype(np.float32)
        self.distance = radius * 2.6
        self.far = max(self.distance * 20.0, 100.0)

    def eye(self):
        cp = math.cos(self.pitch)
        return self.target + np.array(
            (
                math.sin(self.yaw) * cp,
                math.cos(self.yaw) * cp,
                math.sin(self.pitch),
            ),
            dtype=np.float32,
        ) * self.distance

    def view_projection(self, width, height):
        view = look_at(self.eye(), self.target, np.array((0.0, 0.0, 1.0), dtype=np.float32))
        aspect = max(float(width) / max(float(height), 1.0), 0.001)
        proj = perspective(self.fov_y, aspect, self.near, self.far)
        return proj @ view

    def world_point_on_z_plane(self, screen_x, screen_y, width, height, z=0.0):
        vp = self.view_projection(width, height)
        inv_vp = np.linalg.inv(vp)
        ndc_x = float(screen_x) / max(float(width), 1.0) * 2.0 - 1.0
        ndc_y = float(screen_y) / max(float(height), 1.0) * 2.0 - 1.0
        near = inv_vp @ np.array((ndc_x, ndc_y, 0.0, 1.0), dtype=np.float32)
        far = inv_vp @ np.array((ndc_x, ndc_y, 1.0, 1.0), dtype=np.float32)
        near = near[:3] / near[3]
        far = far[:3] / far[3]
        direction = far - near
        if abs(float(direction[2])) < 1.0e-8:
            return None
        t = (float(z) - float(near[2])) / float(direction[2])
        if t < 0.0:
            return None
        point = near + direction * t
        return (float(point[0]), float(point[1]), float(point[2]))


__all__ = [
    "OrbitCamera",
    "look_at",
    "normalize",
    "perspective",
]
