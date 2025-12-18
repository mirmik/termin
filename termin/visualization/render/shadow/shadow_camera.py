"""
Вычисление view/projection матриц для shadow mapping.

Для directional light используется ортографическая проекция,
охватывающая view frustum основной камеры (frustum fitting).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from termin.visualization.core.camera import Camera


@dataclass
class ShadowCameraParams:
    """
    Параметры теневой камеры для directional light.

    Атрибуты:
        light_direction: нормализованное направление света (из источника в сцену)
        ortho_bounds: (left, right, bottom, top) — границы ортографической проекции
                      Если None, используется симметричный ortho_size
        ortho_size: половина размера симметричного ортографического бокса (fallback)
        near: ближняя плоскость отсечения
        far: дальняя плоскость отсечения
        center: центр теневого бокса в мировых координатах
    """
    light_direction: np.ndarray
    ortho_bounds: tuple[float, float, float, float] | None = None  # (left, right, bottom, top)
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
    
    # Размещаем камеру так, чтобы центр сцены был примерно посередине между near и far
    camera_distance = (params.near + params.far) / 2.0
    eye = center - direction * camera_distance
    
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

    Если ortho_bounds задан — использует асимметричные границы.
    Иначе использует симметричный ortho_size.

    Формула ортографической проекции:
        [2/(r-l),    0,       0,    -(r+l)/(r-l)]
        [   0,    2/(t-b),    0,    -(t+b)/(t-b)]
        [   0,       0,   -2/(f-n), -(f+n)/(f-n)]
        [   0,       0,       0,          1     ]

    Возвращает:
        4x4 projection matrix (float32)
    """
    near = params.near
    far = params.far

    if params.ortho_bounds is not None:
        left, right, bottom, top = params.ortho_bounds
    else:
        size = params.ortho_size
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


# ============================================================
# Frustum Fitting
# ============================================================


def compute_frustum_corners(
    view_matrix: np.ndarray,
    projection_matrix: np.ndarray,
) -> np.ndarray:
    """
    Вычисляет 8 углов view frustum в world space.

    Frustum в clip space — это куб [-1,1]^3. Инвертируем VP матрицу
    и трансформируем 8 углов куба обратно в world space.

    Параметры:
        view_matrix: 4x4 view matrix камеры
        projection_matrix: 4x4 projection matrix камеры

    Возвращает:
        (8, 3) array — 8 точек в world space
    """
    # Clip space corners (NDC cube)
    ndc_corners = np.array([
        [-1, -1, -1],  # near bottom left
        [ 1, -1, -1],  # near bottom right
        [ 1,  1, -1],  # near top right
        [-1,  1, -1],  # near top left
        [-1, -1,  1],  # far bottom left
        [ 1, -1,  1],  # far bottom right
        [ 1,  1,  1],  # far top right
        [-1,  1,  1],  # far top left
    ], dtype=np.float32)

    # Inverse view-projection matrix
    vp = projection_matrix @ view_matrix
    inv_vp = np.linalg.inv(vp)

    # Transform corners to world space
    world_corners = np.zeros((8, 3), dtype=np.float32)

    for i, ndc in enumerate(ndc_corners):
        # Homogeneous coordinates
        clip = np.array([ndc[0], ndc[1], ndc[2], 1.0], dtype=np.float32)
        world_h = inv_vp @ clip
        # Perspective divide
        world_corners[i] = world_h[:3] / world_h[3]

    return world_corners


def _build_light_view_matrix(light_direction: np.ndarray) -> np.ndarray:
    """
    Строит view matrix для света (без позиции, только ориентация).

    Используется для трансформации frustum corners в light space
    перед вычислением AABB.
    """
    direction = light_direction / np.linalg.norm(light_direction)

    # Up vector
    world_up = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    if abs(np.dot(direction, world_up)) > 0.99:
        world_up = np.array([0.0, 0.0, 1.0], dtype=np.float32)

    right = np.cross(direction, world_up)
    right = right / np.linalg.norm(right)

    up = np.cross(right, direction)
    up = up / np.linalg.norm(up)

    # View matrix (rotation only, no translation yet)
    view = np.eye(4, dtype=np.float32)
    view[0, 0:3] = right
    view[1, 0:3] = up
    view[2, 0:3] = -direction

    return view


def fit_shadow_frustum_to_camera(
    camera: "Camera",
    light_direction: np.ndarray,
    padding: float = 1.0,
) -> ShadowCameraParams:
    """
    Вычисляет параметры shadow camera, покрывающие view frustum основной камеры.

    Алгоритм:
    1. Вычислить 8 углов view frustum камеры в world space
    2. Трансформировать их в light space (ориентация света)
    3. Найти AABB в light space
    4. Использовать AABB как границы ортографической проекции

    Параметры:
        camera: Основная камера сцены
        light_direction: Направление directional light
        padding: Дополнительный отступ для shadow casters за камерой

    Возвращает:
        ShadowCameraParams с fitted frustum
    """
    light_direction = np.asarray(light_direction, dtype=np.float32)
    light_direction = light_direction / np.linalg.norm(light_direction)

    # 1. Get camera frustum corners in world space
    view = camera.get_view_matrix()
    proj = camera.get_projection_matrix()
    frustum_corners = compute_frustum_corners(view, proj)

    # 2. Build light-space rotation matrix
    light_view = _build_light_view_matrix(light_direction)

    # 3. Transform frustum corners to light space
    light_space_corners = np.zeros((8, 3), dtype=np.float32)
    for i, corner in enumerate(frustum_corners):
        h = np.array([corner[0], corner[1], corner[2], 1.0], dtype=np.float32)
        transformed = light_view @ h
        light_space_corners[i] = transformed[:3]

    # 4. Compute AABB in light space
    min_bounds = light_space_corners.min(axis=0)
    max_bounds = light_space_corners.max(axis=0)

    # X, Y — ortho bounds; Z — near/far
    left = min_bounds[0] - padding
    right = max_bounds[0] + padding
    bottom = min_bounds[1] - padding
    top = max_bounds[1] + padding

    # Z в light space: min — ближе к свету, max — дальше
    # Добавляем padding назад для shadow casters за камерой
    z_near = min_bounds[2] - padding * 10.0  # больше padding для casters
    z_far = max_bounds[2] + padding

    # near/far должны быть положительными для ортографической проекции
    # В нашей системе камера смотрит вдоль -Z, поэтому инвертируем
    near = -z_far
    far = -z_near

    # Защита от вырожденных случаев
    if near < 0.1:
        near = 0.1
    if far <= near:
        far = near + 100.0

    # 5. Центр frustum в world space (для позиционирования shadow camera)
    center = frustum_corners.mean(axis=0)

    return ShadowCameraParams(
        light_direction=light_direction,
        ortho_bounds=(left, right, bottom, top),
        near=near,
        far=far,
        center=center,
    )
