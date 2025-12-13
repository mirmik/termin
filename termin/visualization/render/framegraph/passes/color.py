from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, TYPE_CHECKING

import numpy as np

from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.visualization.render.framegraph.resource_spec import ResourceSpec
from termin.visualization.core.entity import RenderContext
from termin.visualization.render.drawable import Drawable
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend, FramebufferHandle
    from termin.visualization.render.framegraph.resource import ShadowMapArrayResource
    from termin.visualization.core.material import MaterialPhase
    from termin.visualization.core.entity import Entity


# Максимальное количество shadow maps в шейдере
MAX_SHADOW_MAPS = 4

# Начальный texture unit для shadow maps (после обычных текстур)
SHADOW_MAP_TEXTURE_UNIT_START = 8


@dataclass
class PhaseDrawCall:
    """
    Описание одного draw call для фазы.

    Атрибуты:
        entity: Сущность, которой принадлежит фаза
        drawable: Drawable компонент (MeshRenderer, LineRenderer, etc.)
        phase: Фаза материала для отрисовки
        priority: Приоритет отрисовки (меньше = раньше)
    """
    entity: "Entity"
    drawable: Drawable
    phase: "MaterialPhase"
    priority: int


class ColorPass(RenderFramePass):
    """
    Основной цветовой проход рендеринга.

    Рисует все сущности сцены с MeshRenderer, фильтруя фазы материалов
    по phase_mark и сортируя по priority.

    Поддерживает shadow mapping — читает ShadowMapArray и передаёт
    текстуры и матрицы в шейдеры.

    Атрибуты:
        input_res: Имя входного ресурса (обычно "empty" — пустой FBO).
        output_res: Имя выходного ресурса (обычно "color").
        shadow_res: Имя ресурса ShadowMapArray (опционально).
        phase_mark: Метка фазы для фильтрации ("opaque", "transparent" и т.д.).
                    Если None, рендерит все фазы (legacy режим).
    """

    _DEBUG_FIRST_FRAMES = True  # Debug: track first frames
    _debug_frame_count = 0

    inspect_fields = {
        "input_res": InspectField(path="input_res", label="Input Resource", kind="string"),
        "output_res": InspectField(path="output_res", label="Output Resource", kind="string"),
        "shadow_res": InspectField(path="shadow_res", label="Shadow Resource", kind="string"),
        "phase_mark": InspectField(path="phase_mark", label="Phase Mark", kind="string"),
        "sort_by_distance": InspectField(path="sort_by_distance", label="Sort by Distance", kind="bool"),
    }

    def __init__(
        self,
        input_res: str = "empty",
        output_res: str = "color",
        shadow_res: str | None = "shadow_maps",
        pass_name: str = "Color",
        phase_mark: str | None = None,
        sort_by_distance: bool = False,
    ):
        if phase_mark is None:
            phase_mark = "opaque"

        reads = {input_res}
        if shadow_res is not None:
            reads.add(shadow_res)

        super().__init__(
            pass_name=pass_name,
            reads=reads,
            writes={output_res},
        )
        self.input_res = input_res
        self.output_res = output_res
        self.shadow_res = shadow_res
        self.phase_mark = phase_mark
        self.sort_by_distance = sort_by_distance

        # Кэш имён сущностей с MeshRenderer
        self._entity_names: List[str] = []

    def _serialize_params(self) -> dict:
        """Сериализует параметры ColorPass."""
        return {
            "input_res": self.input_res,
            "output_res": self.output_res,
            "shadow_res": self.shadow_res,
            "phase_mark": self.phase_mark,
            "sort_by_distance": self.sort_by_distance,
        }

    @classmethod
    def _deserialize_instance(cls, data: dict, resource_manager=None) -> "ColorPass":
        """Создаёт ColorPass из сериализованных данных."""
        return cls(
            input_res=data.get("input_res", "empty"),
            output_res=data.get("output_res", "color"),
            shadow_res=data.get("shadow_res", "shadow_maps"),
            pass_name=data.get("pass_name", "Color"),
            phase_mark=data.get("phase_mark"),
            sort_by_distance=data.get("sort_by_distance", False),
        )

    _DEBUG_COLLECT = False  # DEBUG: отладка сбора draw calls

    def _collect_draw_calls(self, scene, phase_mark: str | None) -> List[PhaseDrawCall]:
        """
        Собирает все draw calls для указанной метки фазы.

        Алгоритм:
        1. Обходит все entities сцены
        2. Для каждой entity находит компоненты, реализующие Drawable
        3. Фильтрует drawable по phase_marks
        4. Получает фазы из drawable.get_phases(phase_mark)
        5. Возвращает список PhaseDrawCall отсортированный по priority

        Параметры:
            scene: Сцена с entities
            phase_mark: Метка фазы для фильтрации (None = все фазы)

        Возвращает:
            Список PhaseDrawCall отсортированный по priority
        """
        draw_calls: List[PhaseDrawCall] = []

        for entity in scene.entities:
            if not (entity.active and entity.visible):
                continue

            # Ищем все компоненты, реализующие Drawable протокол
            for component in entity.components:
                if not component.enabled:
                    continue

                if not isinstance(component, Drawable):
                    continue

                drawable = component

                # DEBUG
                if self._DEBUG_COLLECT:
                    print(f"[ColorPass] entity={entity.name!r}, phase_mark={phase_mark!r}, drawable.phase_marks={drawable.phase_marks}")

                # Фильтруем по phase_marks:
                # Если phase_mark задан, drawable должен участвовать в этой фазе
                if phase_mark is not None and phase_mark not in drawable.phase_marks:
                    if self._DEBUG_COLLECT:
                        print(f"  -> SKIP: {phase_mark!r} not in {drawable.phase_marks}")
                    continue

                # Получаем фазы из Drawable
                phases = drawable.get_phases(phase_mark)
                if self._DEBUG_COLLECT:
                    print(f"  -> get_phases({phase_mark!r}) returned {len(phases)} phases: {[p.phase_mark for p in phases]}")
                for phase in phases:
                    draw_calls.append(PhaseDrawCall(
                        entity=entity,
                        drawable=drawable,
                        phase=phase,
                        priority=phase.priority,
                    ))

        # Сортируем по priority (меньше = раньше)
        draw_calls.sort(key=lambda dc: dc.priority)
        return draw_calls

    def get_inplace_aliases(self) -> List[Tuple[str, str]]:
        """ColorPass читает input_res и пишет output_res inplace."""
        return [(self.input_res, self.output_res)]

    def get_resource_specs(self) -> List[ResourceSpec]:
        """
        Объявляет требования к входному ресурсу.

        Очищает буфер тёмно-серым цветом и depth=1.0.
        Если есть SkyBoxPass перед ColorPass, он перезапишет эти настройки.
        """
        return [
            ResourceSpec(
                resource=self.input_res,
                clear_color=(0.2, 0.2, 0.2, 1.0),
                clear_depth=1.0,
            )
        ]

    def get_internal_symbols(self) -> List[str]:
        """
        Возвращает список имён сущностей с MeshRenderer.

        Эти имена можно использовать как точки дебага — при выборе
        соответствующего символа в дебаггере будет блититься состояние
        рендера после отрисовки этого меша.
        """
        return list(self._entity_names)

    def _bind_shadow_maps(
        self,
        graphics: "GraphicsBackend",
        shadow_array: "ShadowMapArrayResource | None",
    ) -> None:
        """
        Биндит shadow map текстуры на texture units.
        
        Shadow maps биндятся начиная с SHADOW_MAP_TEXTURE_UNIT_START.
        MeshRenderer будет загружать uniform'ы при отрисовке.
        """
        if shadow_array is None or len(shadow_array) == 0:
            return
        
        for i, entry in enumerate(shadow_array):
            if i >= MAX_SHADOW_MAPS:
                break
            
            unit = SHADOW_MAP_TEXTURE_UNIT_START + i
            texture = entry.texture()
            texture.bind(unit)

    def execute(
        self,
        graphics: "GraphicsBackend",
        reads_fbos: dict[str, "FramebufferHandle | None"],
        writes_fbos: dict[str, "FramebufferHandle | None"],
        rect: tuple[int, int, int, int],
        scene,
        camera,
        context_key: int,
        lights=None,
        canvas=None,
    ):
        """
        Выполняет цветовой проход.

        Алгоритм (режим с phase_mark):
        1. Получает ShadowMapArray (если есть) и биндит текстуры
        2. Подготавливает FBO
        3. Собирает все draw calls для указанной phase_mark
        4. Сортирует draw calls по priority
        5. Для каждого draw call:
           a. Применяет материал (фазу)
           b. Загружает shadow uniforms
           c. Вызывает отрисовку меша

        Алгоритм (legacy режим, phase_mark=None):
        - Обходит все сущности и вызывает entity.draw()

        Формула преобразования координат (модель → клип):
            p_clip = P · V · M · p_local

        где:
            M — матрица модели (model_matrix сущности)
            V — матрица вида камеры (view)
            P — матрица проекции (projection)
        """
        from termin.visualization.render.lighting.upload import upload_lights_to_shader, upload_ambient_to_shader
        from termin.visualization.render.lighting.shadow_upload import upload_shadow_maps_to_shader
        from termin.visualization.render.renderpass import RenderState

        # Debug: log first frames
        ColorPass._debug_frame_count += 1
        if ColorPass._DEBUG_FIRST_FRAMES and ColorPass._debug_frame_count <= 5:
            light_count = len(lights) if lights else 0
            shadow_res_value = reads_fbos.get(self.shadow_res) if self.shadow_res else None
            shadow_count = len(shadow_res_value) if shadow_res_value else 0
            light_info = []
            if lights:
                for i, lt in enumerate(lights):
                    light_info.append(f"  Light[{i}]: dir={lt.direction}, shadows={lt.shadows.enabled}")
            print(f"\n=== ColorPass frame {ColorPass._debug_frame_count} ===")
            print(f"  lights count: {light_count}")
            print(f"  shadow_res ({self.shadow_res}): {type(shadow_res_value).__name__ if shadow_res_value else 'None'}, entries: {shadow_count}")
            print(f"  rect: {rect}")
            print(f"  camera: {camera}")
            if camera and camera.entity:
                pose = camera.entity.transform.global_pose()
                print(f"  camera position: {pose.lin}")
            for info in light_info:
                print(info)
            print(f"=== end ===\n")

        if lights is not None:
            scene.lights = lights

        px, py, pw, ph = rect
        key = context_key

        fb = writes_fbos.get(self.output_res)
        if fb is None:
            return

        # Получаем ShadowMapArrayResource
        shadow_array = None
        if self.shadow_res is not None:
            shadow_array = reads_fbos.get(self.shadow_res)
            # Проверяем тип — должен быть ShadowMapArrayResource
            from termin.visualization.render.framegraph.resource import ShadowMapArrayResource
            if not isinstance(shadow_array, ShadowMapArrayResource):
                shadow_array = None

        # Биндим shadow maps на texture units
        self._bind_shadow_maps(graphics, shadow_array)

        graphics.bind_framebuffer(fb)
        graphics.set_viewport(0, 0, pw, ph)

        # Матрицы камеры
        view = camera.get_view_matrix()
        projection = camera.get_projection_matrix()

        # Контекст рендеринга для компонентов
        # Передаём shadow_data и phase для использования в MeshRenderer
        render_context = RenderContext(
            view=view,
            projection=projection,
            camera=camera,
            scene=scene,
            context_key=key,
            graphics=graphics,
            shadow_data=shadow_array,
            phase=self.phase_mark if self.phase_mark else "main",
        )

        # Получаем конфигурацию внутренней точки дебага
        debug_symbol = self.get_debug_internal_point()
        debugger_window = self.get_debugger_window()

        # Обновляем кэш имён сущностей
        self._entity_names = []

        # Режим с phase_mark — собираем и сортируем draw calls
        if self.phase_mark is not None:
            draw_calls = self._collect_draw_calls(scene, self.phase_mark)

            # Сортировка по дальности (back-to-front для прозрачных объектов)
            if self.sort_by_distance and camera.entity is not None:
                cam_pos = camera.entity.transform.global_pose().lin

                def distance_key(dc: PhaseDrawCall) -> float:
                    entity_pos = dc.entity.transform.global_pose().lin
                    return -np.linalg.norm(entity_pos - cam_pos)  # минус для back-to-front

                draw_calls.sort(key=distance_key)

            for dc in draw_calls:
                self._entity_names.append(dc.entity.name)

                # Получаем матрицу модели
                model = dc.entity.model_matrix()
                render_context.model = model

                # Применяем render state фазы
                graphics.apply_render_state(dc.phase.render_state)

                # Применяем материал (фазу)
                dc.phase.apply(model, view, projection, graphics, context_key=key)

                # Загружаем камеру, свет и тени
                shader = dc.phase.shader_programm
                if camera.entity is not None:
                    cam_pos = camera.entity.transform.global_pose().lin
                    shader.set_uniform_vec3("u_camera_position", cam_pos)
                upload_lights_to_shader(shader, scene.lights)
                upload_ambient_to_shader(shader, scene.ambient_color, scene.ambient_intensity)
                if shadow_array is not None:
                    upload_shadow_maps_to_shader(shader, shadow_array)

                # Рисуем геометрию через Drawable
                dc.drawable.draw_geometry(render_context)

                if debugger_window is not None and dc.entity.name == debug_symbol:
                    self._blit_to_debugger(graphics, fb, debugger_window, (pw, ph))

            # Сбрасываем render state
            graphics.apply_render_state(RenderState())

        else:
            # Legacy режим — вызываем entity.draw()
            for entity in scene.entities:
                self._entity_names.append(entity.name)

                entity.draw(render_context)

                if debugger_window is not None and entity.name == debug_symbol:
                    self._blit_to_debugger(graphics, fb, debugger_window, (pw, ph))

    def _blit_to_debugger(
        self,
        gfx: "GraphicsBackend",
        src_fb,
        debugger_window,
        size: tuple[int, int],
    ) -> None:
        """
        Копирует текущее состояние color FBO в окно дебаггера (framebuffer 0).

        Также вызывает depth callback если он установлен.
        """
        from termin.visualization.render.framegraph.passes.present import (
            PresentToScreenPass,
            _get_texture_from_resource,
        )

        # Захватываем depth buffer до переключения контекста
        if self._depth_capture_callback is not None:
            depth = gfx.read_depth_buffer(src_fb)
            if depth is not None:
                self._depth_capture_callback(depth)

        # Извлекаем текстуру из ресурса
        tex = _get_texture_from_resource(src_fb)
        if tex is None:
            return

        # Переключаемся на контекст окна дебаггера
        debugger_window.make_current()

        # Получаем размер окна дебаггера
        dst_w, dst_h = debugger_window.framebuffer_size()

        # Биндим framebuffer 0 (окно)
        gfx.bind_framebuffer(None)
        gfx.set_viewport(0, 0, dst_w, dst_h)

        gfx.set_depth_test(False)
        gfx.set_depth_mask(False)

        # Рендерим fullscreen quad с текстурой
        shader = PresentToScreenPass._get_shader()
        shader.ensure_ready(gfx)
        shader.use()
        shader.set_uniform_int("u_tex", 0)
        tex.bind(0)
        gfx.draw_ui_textured_quad(0)

        gfx.set_depth_test(True)
        gfx.set_depth_mask(True)

        # Показываем результат
        debugger_window.swap_buffers()
