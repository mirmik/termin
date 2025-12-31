"""
ShadowPass — проход генерации shadow maps для источников света.

Рендерит сцену с точки зрения каждого источника света с тенями
в отдельную depth-текстуру. Результат — ShadowMapArrayResource, содержащий
текстуры и матрицы light-space для всех источников.

Поддерживаемые типы источников:
- DIRECTIONAL — ортографическая проекция вдоль направления света
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, TYPE_CHECKING

import numpy as np

from termin._native import log
from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.visualization.render.framegraph.resource_spec import ResourceSpec
from termin.visualization.render.framegraph.resource import ShadowMapArrayResource
from termin.visualization.render.render_context import RenderContext
from termin.visualization.render.drawable import Drawable
from termin.visualization.render.renderpass import RenderState
from termin.visualization.render.system_shaders import get_system_shader
from termin.visualization.render.shadow.shadow_camera import (
    ShadowCameraParams,
    compute_light_space_matrix,
    build_shadow_view_matrix,
    build_shadow_projection_matrix,
    fit_shadow_frustum_to_camera,
)
from termin.lighting import Light, LightType
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend, FramebufferHandle
    from termin.visualization.core.entity import Entity


@dataclass
class ShadowDrawCall:
    """Pre-collected draw call for ShadowPass."""
    entity: "Entity"
    drawable: Drawable


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

    inspect_fields = {
        "output_res": InspectField(path="output_res", label="Output Resource", kind="string"),
        "default_resolution": InspectField(
            path="default_resolution", label="Resolution", kind="int",
            min=128, max=4096, step=128,
        ),
        "max_shadow_distance": InspectField(
            path="max_shadow_distance", label="Max Shadow Distance", kind="float",
            min=1.0, max=500.0, step=5.0,
        ),
        "ortho_size": InspectField(
            path="ortho_size", label="Ortho Size (fallback)", kind="float",
            min=1.0, max=200.0, step=1.0,
        ),
        "near": InspectField(path="near", label="Near (fallback)", kind="float", min=0.01, step=0.1),
        "far": InspectField(path="far", label="Far (fallback)", kind="float", min=1.0, step=1.0),
        "caster_offset": InspectField(
            path="caster_offset", label="Caster Offset", kind="float",
            min=0.0, max=200.0, step=5.0,
        ),
    }

    def __init__(
        self,
        output_res: str = "shadow_maps",
        pass_name: str = "Shadow",
        default_resolution: int = 1024,
        max_shadow_distance: float = 50.0,
        ortho_size: float = 20.0,
        near: float = 0.1,
        far: float = 100.0,
        caster_offset: float = 50.0,
    ):
        super().__init__(
            pass_name=pass_name,
            reads=set(),
            writes={output_res},
        )
        self.output_res = output_res
        self.default_resolution = default_resolution
        self.max_shadow_distance = max_shadow_distance
        self.ortho_size = ortho_size
        self.near = near
        self.far = far
        self.caster_offset = caster_offset

        # Пул FBO для shadow maps (переиспользуются между кадрами)
        self._fbo_pool: Dict[int, "FramebufferHandle"] = {}

        # Текущий ShadowMapArrayResource (обновляется в execute)
        self._shadow_map_array: ShadowMapArrayResource | None = None

        # Список имён сущностей для debug
        self._entity_names: List[str] = []

    def _serialize_params(self) -> dict:
        """Сериализует параметры ShadowPass."""
        return {
            "output_res": self.output_res,
            "default_resolution": self.default_resolution,
            "max_shadow_distance": self.max_shadow_distance,
            "ortho_size": self.ortho_size,
            "near": self.near,
            "far": self.far,
            "caster_offset": self.caster_offset,
        }

    @classmethod
    def _deserialize_instance(cls, data: dict, resource_manager=None) -> "ShadowPass":
        """Создаёт ShadowPass из сериализованных данных."""
        return cls(
            output_res=data.get("output_res", "shadow_maps"),
            pass_name=data.get("pass_name", "Shadow"),
            default_resolution=data.get("default_resolution", 1024),
            max_shadow_distance=data.get("max_shadow_distance", 50.0),
            ortho_size=data.get("ortho_size", 20.0),
            near=data.get("near", 0.1),
            far=data.get("far", 100.0),
            caster_offset=data.get("caster_offset", 50.0),
        )

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
            # Используем shadow framebuffer с depth texture и hardware PCF
            fbo = graphics.create_shadow_framebuffer((resolution, resolution))
            self._fbo_pool[index] = fbo
        else:
            current_size = fbo.get_size()
            if current_size != (resolution, resolution):
                fbo.resize((resolution, resolution))

        return fbo

    def _build_shadow_params_for_light(
        self,
        light: Light,
        camera=None,
    ) -> ShadowCameraParams:
        """
        Строит параметры теневой камеры для источника света.

        Если camera задана — использует frustum fitting для оптимального
        покрытия видимой области. Иначе — fallback на фиксированные параметры.

        Для directional light:
            - Направление камеры = направление света
            - Ортографическая проекция, покрывающая view frustum камеры
        """
        if camera is not None:
            return fit_shadow_frustum_to_camera(
                camera=camera,
                light_direction=light.direction,
                padding=1.0,
                max_shadow_distance=self.max_shadow_distance,
                shadow_map_resolution=light.shadows.map_resolution,
                stabilize=True,  # Texel snapping для устранения дрожания
                caster_offset=self.caster_offset,
            )

        # Fallback: фиксированные параметры
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

    def _collect_draw_calls(self, scene) -> List[ShadowDrawCall]:
        """
        Собирает все draw calls для shadow casters.

        Один проход по сцене, плоский список результатов.
        Фильтрует только объекты с "shadow" в phase_marks.
        """
        draw_calls: List[ShadowDrawCall] = []

        for entity in scene.entities:
            if not (entity.active and entity.visible):
                continue

            for component in entity.components:
                if not component.enabled:
                    continue

                # DEBUG: find problematic component
                print(f"DEBUG: checking component {type(component).__name__} on entity {entity.name}", flush=True)
                # Bypass isinstance to debug which attribute causes segfault
                print(f"  hasattr phase_marks...", flush=True)
                has_pm = hasattr(component, "phase_marks")
                print(f"  has_pm={has_pm}", flush=True)
                if not has_pm:
                    continue
                print(f"  hasattr draw_geometry...", flush=True)
                has_dg = hasattr(component, "draw_geometry")
                print(f"  has_dg={has_dg}", flush=True)
                if not has_dg:
                    continue
                print(f"  hasattr get_geometry_draws...", flush=True)
                has_ggd = hasattr(component, "get_geometry_draws")
                print(f"  has_ggd={has_ggd}", flush=True)
                if not has_ggd:
                    continue

                # Пропускаем объекты без метки "shadow"
                if "shadow" not in component.phase_marks:
                    continue

                draw_calls.append(ShadowDrawCall(
                    entity=entity,
                    drawable=component,
                ))

        return draw_calls

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
        1. Собирает draw calls ОДИН РАЗ
        2. Находит все источники света с включёнными тенями
        3. Для каждого источника:
           a. Создаёт/получает FBO
           b. Вычисляет light-space матрицу
           c. Рендерит draw calls в shadow map
        4. Собирает результат в ShadowMapArray
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

        # Собираем draw calls ОДИН РАЗ (не для каждого источника света!)
        draw_calls = self._collect_draw_calls(scene)

        # Обновляем debug-список имён
        self._entity_names = []
        seen_entities = set()
        for dc in draw_calls:
            if dc.entity.name not in seen_entities:
                seen_entities.add(dc.entity.name)
                self._entity_names.append(dc.entity.name)

        # Если нет shadow casters — возвращаем пустой массив
        if not draw_calls:
            writes_fbos[self.output_res] = shadow_array
            return

        # Получаем шейдер из глобального реестра
        shader = get_system_shader("shadow", graphics)

        # Состояние рендера: depth test/write, без blending
        render_state = RenderState(
            depth_test=True,
            depth_write=True,
            blend=False,
            cull=True,
        )

        # Рендерим shadow map для каждого источника
        for array_index, (light_index, light) in enumerate(shadow_lights):
            resolution = light.shadows.map_resolution

            # Получаем FBO
            fbo = self._get_or_create_fbo(graphics, resolution, array_index)

            # Вычисляем параметры теневой камеры (с frustum fitting если есть камера)
            shadow_params = self._build_shadow_params_for_light(light, camera)
            light_space_matrix = compute_light_space_matrix(shadow_params)

            # Матрицы view и projection
            view_matrix = build_shadow_view_matrix(shadow_params)
            proj_matrix = build_shadow_projection_matrix(shadow_params)

            # Очищаем и настраиваем FBO
            graphics.bind_framebuffer(fbo)
            graphics.set_viewport(0, 0, resolution, resolution)
            graphics.clear_color_depth((1.0, 1.0, 1.0, 1.0))
            graphics.apply_render_state(render_state)

            # Настраиваем шейдер для этого источника
            shader.use()
            shader.set_uniform_matrix4("u_view", view_matrix)
            shader.set_uniform_matrix4("u_projection", proj_matrix)

            # Контекст рендеринга
            render_ctx = RenderContext(
                view=view_matrix,
                projection=proj_matrix,
                graphics=graphics,
                context_key=context_key,
                scene=scene,
                camera=None,
                phase="shadow",
                current_shader=shader,
            )

            # Рендерим все draw calls (переиспользуем собранный список!)
            for dc in draw_calls:
                model = dc.entity.model_matrix()
                # Re-bind shader before setting uniforms (draw_geometry may switch shaders)
                shader.use()
                shader.set_uniform_matrix4("u_model", model)
                render_ctx.model = model
                dc.drawable.draw_geometry(render_ctx)

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
