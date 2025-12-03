"""
Вычисление view/projection матриц для shadow mapping.

Для directional light используется ортографическая проекция,
охватывающая view frustum основной камеры (frustum fitting).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np


@dataclass
class ShadowCameraParams:
    """
    Параметры теневой камеры для directional light.
    
    Атрибуты:
        light_direction: нормализованное направление света (из источника в сцену)
        ortho_size: половина размера ортографического бокса (ширина = высота = 2 * ortho_size)
        near: ближняя плоскость отсечения
        far: дальняя плоскость отсечения
        center: центр теневого бокса в мировых координатах
    """
    light_direction: np.ndarray
    ortho_size: float = 20.0
    near: float = 0.1
    far: float = 100.0
    center: np.ndarray = None

    def __post_init__(self):
        self.light_direction = np.asarray(self.light_direction, dtype=np.float32)
        norm = np.linalg.norm(self.light_direction)
        if norm > 1e-6:
            self.light_direction = self.light_direction / norm
        else:
            self.light_direction = np.array([0.0, -1.0, 0.0], dtype=np.float32)

        if self.center is None:
            self.center = np.zeros(3, dtype=np.float32)
        else:
            self.center = np.asarray(self.center, dtype=np.float32)


def build_shadow_view_matrix(params: ShadowCameraParams) -> np.ndarray:
    """
    Строит view-матрицу для теневой камеры.
    
    Камера располагается на расстоянии far от центра сцены
    в направлении, противоположном свету, и смотрит вдоль света.
    
    Формула:
        eye = center - light_direction * far
        target = center
        up = выбирается ортогонально light_direction
    
    Возвращает:
        4x4 view matrix (float32)
    """
    direction = params.light_direction
    center = params.center
    
    # Позиция камеры — отступаем от центра против направления света
    eye = center - direction * params.far
    
    # Выбираем up-вектор, ортогональный направлению
    # Если свет смотрит вдоль Y, берём Z как временный
    world_up = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    if abs(np.dot(direction, world_up)) > 0.99:
        world_up = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    
    # Правый вектор
    right = np.cross(direction, world_up)
    right = right / np.linalg.norm(right)
    
    # Истинный up
    up = np.cross(right, direction)
    up = up / np.linalg.norm(up)
    
    # Строим view-матрицу (look-at)
    # View = R * T, где R — поворот, T — трансляция
    view = np.eye(4, dtype=np.float32)
    
    # Строки 0,1,2 — оси камеры (right, up, -forward)
    view[0, 0:3] = right
    view[1, 0:3] = up
    view[2, 0:3] = -direction  # камера смотрит вдоль -Z в своём пространстве
    
    # Трансляция
    view[0, 3] = -np.dot(right, eye)
    view[1, 3] = -np.dot(up, eye)
    view[2, 3] = np.dot(direction, eye)
    
    return view


def build_shadow_projection_matrix(params: ShadowCameraParams) -> np.ndarray:
    """
    Строит ортографическую projection-матрицу для теневой камеры.
    
    Параметры:
        left = -ortho_size
        right = +ortho_size
        bottom = -ortho_size
        top = +ortho_size
        near, far — из params
    
    Формула ортографической проекции:
        [2/(r-l),    0,       0,    -(r+l)/(r-l)]
        [   0,    2/(t-b),    0,    -(t+b)/(t-b)]
        [   0,       0,   -2/(f-n), -(f+n)/(f-n)]
        [   0,       0,       0,          1     ]
    
    Возвращает:
        4x4 projection matrix (float32)
    """
    size = params.ortho_size
    near = params.near
    far = params.far
    
    left = -size
    right = size
    bottom = -size
    top = size
    
    proj = np.zeros((4, 4), dtype=np.float32)
    
    proj[0, 0] = 2.0 / (right - left)
    proj[1, 1] = 2.0 / (top - bottom)
    proj[2, 2] = -2.0 / (far - near)
    
    proj[0, 3] = -(right + left) / (right - left)
    proj[1, 3] = -(top + bottom) / (top - bottom)
    proj[2, 3] = -(far + near) / (far - near)
    proj[3, 3] = 1.0
    
    return proj


def compute_light_space_matrix(params: ShadowCameraParams) -> np.ndarray:
    """
    Вычисляет матрицу преобразования из мирового пространства
    в clip-пространство теневой камеры.
    
    light_space_matrix = projection * view
    
    Эта матрица используется в основном шейдере для трансформации
    фрагмента и сравнения с shadow map.
    
    Возвращает:
        4x4 matrix (float32)
    """
    view = build_shadow_view_matrix(params)
    proj = build_shadow_projection_matrix(params)
    return proj @ view
