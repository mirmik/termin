"""
ShadowPass — проход генерации shadow map для directional light.

Рендерит сцену с точки зрения источника света в depth-текстуру.
Матрицы view/projection строятся из параметров света, а не из CameraComponent.
"""

from __future__ import annotations

from typing import List, TYPE_CHECKING

import numpy as np

from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.visualization.render.components.mesh_renderer import MeshRenderer
from termin.visualization.core.entity import RenderContext
from termin.visualization.render.renderpass import RenderState
from termin.visualization.render.materials.shadow_material import ShadowMaterial
from termin.visualization.render.shadow.shadow_camera import (
    ShadowCameraParams,
    build_shadow_view_matrix,
    build_shadow_projection_matrix,
    compute_light_space_matrix,
)

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend


class ShadowPass(RenderFramePass):
    """
    Проход рендеринга shadow map для directional light.
    
    Атрибуты:
        output_res: имя выходного ресурса (FBO с depth attachment)
        shadow_params: параметры теневой камеры (направление света, размеры и т.д.)
        resolution: разрешение shadow map (по умолчанию 1024)
    
    Выходные данные:
        - Depth-текстура с картой теней
        - light_space_matrix — матрица для трансформации в shader
    """

    def __init__(
        self,
        output_res: str = "shadow_map",
        pass_name: str = "ShadowPass",
        shadow_params: ShadowCameraParams = None,
        resolution: int = 1024,
    ):
        # ShadowPass не читает никаких ресурсов, только пишет shadow_map
        super().__init__(
            pass_name=pass_name,
            reads=set(),
            writes={output_res},
            inplace=False,
        )
        self.output_res = output_res
        self.resolution = resolution
        
        # Параметры по умолчанию: свет сверху-спереди
        if shadow_params is None:
            shadow_params = ShadowCameraParams(
                light_direction=np.array([0.5, -1.0, 0.5], dtype=np.float32),
                ortho_size=20.0,
                near=0.1,
                far=100.0,
            )
        self.shadow_params = shadow_params
        
        # Кэшированные матрицы (обновляются в execute)
        self._view_matrix: np.ndarray = np.eye(4, dtype=np.float32)
        self._projection_matrix: np.ndarray = np.eye(4, dtype=np.float32)
        self._light_space_matrix: np.ndarray = np.eye(4, dtype=np.float32)
        
        # Материал для shadow pass
        self._material: ShadowMaterial = None
        
        # Список отрендеренных сущностей (для debug)
        self._entity_names: List[str] = []

    def _get_material(self) -> ShadowMaterial:
        """Ленивая инициализация материала."""
        if self._material is None:
            self._material = ShadowMaterial()
        return self._material

    def get_light_space_matrix(self) -> np.ndarray:
        """
        Возвращает матрицу light-space для использования в основном шейдере.
        
        Вызывать после execute(), иначе вернётся единичная матрица.
        """
        return self._light_space_matrix.copy()

    def update_shadow_params(self, params: ShadowCameraParams) -> None:
        """Обновляет параметры теневой камеры."""
        self.shadow_params = params

    def update_from_light_direction(self, direction: np.ndarray) -> None:
        """
        Обновляет направление света, сохраняя остальные параметры.
        
        Параметр direction — вектор направления света (из источника в сцену).
        """
        self.shadow_params.light_direction = np.asarray(direction, dtype=np.float32)
        norm = np.linalg.norm(self.shadow_params.light_direction)
        if norm > 1e-6:
            self.shadow_params.light_direction /= norm

    def update_center(self, center: np.ndarray) -> None:
        """Обновляет центр теневого бокса (обычно — позиция игрока или камеры)."""
        self.shadow_params.center = np.asarray(center, dtype=np.float32)

    def get_internal_symbols(self) -> List[str]:
        """Возвращает имена отрендеренных сущностей для debug."""
        return list(self._entity_names)

    def execute(
        self,
        graphics: "GraphicsBackend",
        reads_fbos: dict,
        writes_fbos: dict,
        rect: tuple,
        scene,
        camera,
        context_key: int,
        lights=None,
        canvas=None,
    ) -> None:
        """
        Выполняет shadow pass.
        
        Алгоритм:
        1. Вычисляет view/projection матрицы из shadow_params
        2. Биндит FBO для shadow map
        3. Очищает depth buffer
        4. Обходит сущности с MeshRenderer и рендерит их с ShadowMaterial
        5. Сохраняет light_space_matrix для использования в ColorPass
        """
        px, py, pw, ph = rect
        
        fb = writes_fbos.get(self.output_res)
        if fb is None:
            return
        
        # Вычисляем матрицы теневой камеры
        self._view_matrix = build_shadow_view_matrix(self.shadow_params)
        self._projection_matrix = build_shadow_projection_matrix(self.shadow_params)
        self._light_space_matrix = compute_light_space_matrix(self.shadow_params)
        
        # Используем разрешение shadow map, а не viewport основной камеры
        shadow_size = self.resolution
        
        graphics.bind_framebuffer(fb)
        graphics.set_viewport(0, 0, shadow_size, shadow_size)
        
        # Очистка — белый цвет (для debug) и максимальная глубина
        graphics.clear_color_depth((1.0, 1.0, 1.0, 1.0))
        
        # Состояние рендера: depth test/write включены, без blending
        graphics.apply_render_state(
            RenderState(
                depth_test=True,
                depth_write=True,
                blend=False,
                cull=True,
            )
        )
        
        shadow_material = self._get_material()
        
        # Контекст рендеринга с матрицами теневой камеры
        render_ctx = RenderContext(
            view=self._view_matrix,
            projection=self._projection_matrix,
            graphics=graphics,
            context_key=context_key,
            scene=scene,
            camera=None,  # теневой pass не использует camera component
            phase="shadow",
        )
        
        self._entity_names = []
        
        # Обход сущностей и рендеринг
        for entity in scene.entities:
            mr = entity.get_component(MeshRenderer)
            if mr is None:
                continue
            
            if mr.mesh is None:
                continue
            
            # Пропускаем невидимые объекты
            if not entity.visible:
                continue
            
            self._entity_names.append(entity.name)
            
            model = entity.model_matrix()
            shadow_material.apply(
                model,
                self._view_matrix,
                self._projection_matrix,
                graphics=graphics,
                context_key=context_key,
            )
            
            mr.mesh.draw(render_ctx)
        
        # Сбрасываем состояние
        graphics.apply_render_state(RenderState())
