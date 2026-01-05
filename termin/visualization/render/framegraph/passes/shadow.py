"""
ShadowPass — проход генерации shadow maps для источников света.

Рендерит сцену с точки зрения каждого источника света с тенями
в отдельную depth-текстуру. Результат — ShadowMapArrayResource, содержащий
текстуры и матрицы light-space для всех источников.

Uses C++ implementation for core rendering.
"""

from __future__ import annotations

from typing import List, TYPE_CHECKING

import numpy as np

from termin._native.render import ShadowPass as _ShadowPassNative
from termin.visualization.render.framegraph.resource_spec import ResourceSpec
from termin.visualization.render.framegraph.resource import ShadowMapArrayResource
from termin.visualization.render.system_shaders import get_system_shader

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend
    from termin.lighting import Light


class ShadowPass(_ShadowPassNative):
    """
    Проход рендеринга shadow maps для всех источников света с тенями.

    Uses C++ implementation for core rendering, with Python wrapper for
    integration with framegraph.

    Fields are registered via INSPECT_FIELD macros in C++ (shadow_pass.hpp).

    Атрибуты:
        output_res: имя выходного ресурса (ShadowMapArray)
        default_resolution: разрешение shadow map по умолчанию
        max_shadow_distance: максимальная дистанция теней
        ortho_size: размер ортографического бокса (fallback)
        near: ближняя плоскость (fallback)
        far: дальняя плоскость (fallback)
        caster_offset: смещение за камеру для shadow casters

    Выходные данные:
        ShadowMapArray с текстурами и матрицами для всех источников.
    """

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
            output_res=output_res,
            pass_name=pass_name,
            default_resolution=default_resolution,
            max_shadow_distance=max_shadow_distance,
            ortho_size=ortho_size,
            near=near,
            far=far,
            caster_offset=caster_offset,
        )

        # Текущий ShadowMapArrayResource (обновляется в execute)
        self._shadow_map_array: ShadowMapArrayResource | None = None

    @classmethod
    def _deserialize_instance(cls, data: dict, resource_manager=None) -> "ShadowPass":
        """Create ShadowPass with pass_name; other fields set via InspectRegistry."""
        return cls(pass_name=data.get("pass_name", "Shadow"))

    def serialize_data(self) -> dict:
        """Serialize fields via InspectRegistry (C++ INSPECT_FIELD)."""
        from termin._native.inspect import InspectRegistry
        return InspectRegistry.instance().serialize_all(self)

    def deserialize_data(self, data: dict) -> None:
        """Deserialize fields via InspectRegistry (C++ INSPECT_FIELD)."""
        if not data:
            return
        from termin._native.inspect import InspectRegistry
        InspectRegistry.instance().deserialize_all(self, data)

    def serialize(self) -> dict:
        """Serialize ShadowPass to dict."""
        return {
            "type": self.__class__.__name__,
            "pass_name": self.pass_name,
            "enabled": self.enabled,
            "data": self.serialize_data(),
        }

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
        lights: List["Light"] | None = None,
        canvas=None,
    ) -> None:
        """
        Выполняет shadow pass для всех источников света с тенями.

        Uses C++ implementation for rendering.
        """
        if lights is None:
            lights = []

        # Создаём ShadowMapArrayResource
        shadow_array = ShadowMapArrayResource(resolution=self.default_resolution)
        self._shadow_map_array = shadow_array

        if not lights:
            writes_fbos[self.output_res] = shadow_array
            return

        # Set shadow shader for C++ (enables skinning injection)
        self.shadow_shader_program = get_system_shader("shadow", graphics)

        # Get camera matrices
        camera_view = camera.get_view_matrix().astype(np.float32)
        camera_projection = camera.get_projection_matrix().astype(np.float32)

        # Call C++ execute_shadow_pass
        results = self.execute_shadow_pass(
            graphics=graphics,
            entities=list(scene.entities),
            lights=list(lights),
            camera_view=camera_view,
            camera_projection=camera_projection,
            context_key=context_key,
        )

        # Convert C++ results to ShadowMapArrayResource
        for result in results:
            shadow_array.add_entry(
                fbo=result.fbo,
                light_space_matrix=result.light_space_matrix,
                light_index=result.light_index,
            )

        # Put result in writes
        writes_fbos[self.output_res] = shadow_array
