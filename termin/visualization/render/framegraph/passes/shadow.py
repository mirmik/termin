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
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend
    from termin.lighting import Light


class ShadowPass(_ShadowPassNative):
    """
    Проход рендеринга shadow maps для всех источников света с тенями.

    Uses C++ implementation for core rendering, with Python wrapper for
    integration with framegraph.

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
