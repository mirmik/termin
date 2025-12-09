"""
ShadowPass — проход генерации shadow maps для источников света.

Рендерит сцену с точки зрения каждого источника света с тенями
в отдельную depth-текстуру. Результат — ShadowMapArrayResource, содержащий
текстуры и матрицы light-space для всех источников.

Поддерживаемые типы источников:
- DIRECTIONAL — ортографическая проекция вдоль направления света
"""

from __future__ import annotations

from typing import Dict, List, TYPE_CHECKING

import numpy as np

from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.visualization.render.framegraph.resource_spec import ResourceSpec
from termin.visualization.render.framegraph.resource import ShadowMapArrayResource
from termin.visualization.render.components.mesh_renderer import MeshRenderer
from termin.visualization.core.entity import RenderContext
from termin.visualization.render.renderpass import RenderState
from termin.visualization.render.materials.shadow_material import ShadowMaterial
from termin.visualization.render.shadow.shadow_camera import (
    ShadowCameraParams,
    compute_light_space_matrix,
    build_shadow_view_matrix,
    build_shadow_projection_matrix,
)
from termin.visualization.core.lighting.light import Light, LightType

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend, FramebufferHandle


class ShadowPass(RenderFramePass):
    """
    Проход рендеринга shadow maps для всех источников света с тенями.
    
    Атрибуты:
        output_res: имя выходного ресурса (ShadowMapArray)
        default_resolution: разрешение shadow map по умолчанию
        ortho_size: размер ортографического бокса для directional lights
        near: ближняя плоскость
        far: дальняя плоскость
    
    Выходные данные:
        ShadowMapArray с текстурами и матрицами для всех источников.
    """

    def __init__(
        self,
        output_res: str = "shadow_maps",
        pass_name: str = "Shadow",
        default_resolution: int = 1024,
        ortho_size: float = 20.0,
        near: float = 0.1,
        far: float = 100.0,
    ):
        super().__init__(
            pass_name=pass_name,
            reads=set(),
            writes={output_res},
        )
        self.output_res = output_res
        self.default_resolution = default_resolution
        self.ortho_size = ortho_size
        self.near = near
        self.far = far
        
        # Материал для shadow pass (общий для всех источников)
        self._material: ShadowMaterial | None = None
        
        # Пул FBO для shadow maps (переиспользуются между кадрами)
        self._fbo_pool: Dict[int, "FramebufferHandle"] = {}
        
        # Текущий ShadowMapArrayResource (обновляется в execute)
        self._shadow_map_array: ShadowMapArrayResource | None = None
        
        # Список имён сущностей для debug
        self._entity_names: List[str] = []

    def _get_material(self) -> ShadowMaterial:
        """Ленивая инициализация материала."""
        if self._material is None:
            self._material = ShadowMaterial()
        return self._material

    def _get_or_create_fbo(
        self,
        graphics: "GraphicsBackend",
        resolution: int,
        index: int,
    ) -> "FramebufferHandle":
        """
        Получает или создаёт FBO для shadow map.
        
        FBO кэшируются по индексу для переиспользования между кадрами.
        При изменении разрешения FBO пересоздаётся.
        """
        fbo = self._fbo_pool.get(index)
        
        if fbo is None:
            fbo = graphics.create_framebuffer((resolution, resolution))
            self._fbo_pool[index] = fbo
        else:
            current_size = fbo.get_size()
            if current_size != (resolution, resolution):
                fbo.resize((resolution, resolution))
        
        return fbo

    def _build_shadow_params_for_light(self, light: Light) -> ShadowCameraParams:
        """
        Строит параметры теневой камеры для источника света.
        
        Для directional light:
            - Направление камеры = направление света
            - Ортографическая проекция с заданным размером
        """
        return ShadowCameraParams(
            light_direction=light.direction.copy(),
            ortho_size=self.ortho_size,
            near=self.near,
            far=self.far,
            center=np.zeros(3, dtype=np.float32),
        )

    def get_internal_symbols(self) -> List[str]:
        """Возвращает имена отрендеренных сущностей для debug."""
        return list(self._entity_names)

    def get_resource_specs(self) -> list[ResourceSpec]:
        """
        Объявляет требования к ресурсу shadow_maps.
        
        Тип ресурса — shadow_map_array, создаётся динамически в execute().
        """
        return [
            ResourceSpec(
                resource=self.output_res,
                resource_type="shadow_map_array",
            )
        ]

    def get_shadow_map_array(self) -> ShadowMapArrayResource | None:
        """Возвращает текущий ShadowMapArrayResource (после execute)."""
        return self._shadow_map_array

    def execute(
        self,
        graphics: "GraphicsBackend",
        reads_fbos: dict,
        writes_fbos: dict,
        rect: tuple,
        scene,
        camera,
        context_key: int,
        lights: List[Light] | None = None,
        canvas=None,
    ) -> None:
        """
        Выполняет shadow pass для всех источников света с тенями.
        
        Алгоритм:
        1. Находит все источники света с включёнными тенями
        2. Для каждого источника:
           a. Создаёт/получает FBO
           b. Вычисляет light-space матрицу
           c. Рендерит сцену в shadow map
        3. Собирает результат в ShadowMapArray
        4. Кладёт ShadowMapArray в writes_fbos
        """
        if lights is None:
            lights = []
        
        # Находим источники с тенями (пока только directional)
        shadow_lights: List[tuple[int, Light]] = []
        for i, light in enumerate(lights):
            if light.type == LightType.DIRECTIONAL and light.shadows.enabled:
                shadow_lights.append((i, light))
        
        # Создаём ShadowMapArrayResource
        shadow_array = ShadowMapArrayResource(resolution=self.default_resolution)
        self._shadow_map_array = shadow_array
        
        if not shadow_lights:
            # Нет источников с тенями — возвращаем пустой массив
            writes_fbos[self.output_res] = shadow_array
            return
        
        shadow_material = self._get_material()
        self._entity_names = []
        
        # Рендерим shadow map для каждого источника
        for array_index, (light_index, light) in enumerate(shadow_lights):
            resolution = light.shadows.map_resolution
            
            # Получаем FBO
            fbo = self._get_or_create_fbo(graphics, resolution, array_index)
            
            # Вычисляем параметры теневой камеры
            shadow_params = self._build_shadow_params_for_light(light)
            light_space_matrix = compute_light_space_matrix(shadow_params)
            
            # Матрицы view и projection для материала
            view_matrix = build_shadow_view_matrix(shadow_params)
            proj_matrix = build_shadow_projection_matrix(shadow_params)
            
            # Очищаем и настраиваем FBO
            graphics.bind_framebuffer(fbo)
            graphics.set_viewport(0, 0, resolution, resolution)
            graphics.clear_color_depth((1.0, 1.0, 1.0, 1.0))
            
            # Состояние рендера: depth test/write, без blending
            graphics.apply_render_state(
                RenderState(
                    depth_test=True,
                    depth_write=True,
                    blend=False,
                    cull=True,
                )
            )
            
            # Контекст рендеринга с матрицами теневой камеры
            render_ctx = RenderContext(
                view=view_matrix,
                projection=proj_matrix,
                graphics=graphics,
                context_key=context_key,
                scene=scene,
                camera=None,
                phase="shadow",
            )
            
            # Рендерим все видимые объекты с мешами
            for entity in scene.entities:
                mr = entity.get_component(MeshRenderer)
                if mr is None or mr.mesh is None:
                    continue

                if not entity.visible:
                    continue

                # Пропускаем объекты, не отбрасывающие тень
                if not entity.cast_shadow:
                    continue
                
                # Добавляем в debug-список только для первого источника
                if array_index == 0:
                    self._entity_names.append(entity.name)
                
                model = entity.model_matrix()
                shadow_material.apply(
                    model,
                    view_matrix,
                    proj_matrix,
                    graphics=graphics,
                    context_key=context_key,
                )
                
                mr.mesh.draw(render_ctx)
            
            # Добавляем в массив
            shadow_array.add_entry(
                fbo=fbo,
                light_space_matrix=light_space_matrix,
                light_index=light_index,
            )
        
        # Сбрасываем состояние
        graphics.apply_render_state(RenderState())
        
        # Кладём результат в writes
        writes_fbos[self.output_res] = shadow_array
