from __future__ import annotations

from typing import Callable, Optional, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout

from termin.visualization.core.entity import Entity
from termin.visualization.platform.backends.base import Action, MouseButton
from termin.visualization.render.framegraph import RenderPipeline, ClearSpec

from termin.editor.gizmo import GizmoController


class ViewportBackend:
    """
    Тонкая обёртка над окном визуализации, чтобы не дергать приватные методы напрямую.
    """

    def __init__(self, window, viewport) -> None:
        self._window = window
        self._viewport = viewport

    @property
    def window(self):
        return self._window

    @property
    def viewport(self):
        return self._viewport

    def request_update(self) -> None:
        self._window._request_update()

    def pick_entity_at(self, x: float, y: float, viewport) -> Entity | None:
        return self._window.pick_entity_at(x, y, viewport)

    def pick_color_at(self, x: float, y: float, viewport, buffer_name: str = "id"):
        return self._window.pick_color_at(x, y, viewport, buffer_name)

    def get_pick_id_for_entity(self, ent: Entity | None) -> int:
        if ent is None:
            return 0
        return ent.pick_id


class ViewportController:
    """
    Управляет окном рендера:
    - создаёт окно и вьюпорт;
    - настраивает framegraph и подсветку;
    - обрабатывает события мыши и пика;
    - прокидывает выбор и hover через колбэки в EditorWindow.
    """

    def __init__(
        self,
        container: QWidget,
        world,
        scene,
        camera,
        gizmo_controller: GizmoController,
        on_entity_picked: Callable[[Entity | None], None],
        on_hover_entity: Callable[[Entity | None], None],
    ) -> None:
        self._container = container
        self._world = world
        self._scene = scene
        self._camera = camera
        self._gizmo_controller = gizmo_controller
        self._on_entity_picked = on_entity_picked
        self._on_hover_entity = on_hover_entity
        self._framegraph_debugger = None
        self._debug_source_res: str = "color_pp"
        self._debug_paused: bool = False

        self.selected_entity_id: int = 0
        self.hover_entity_id: int = 0

        self._pending_pick_press: Optional[Tuple[float, float, object]] = None
        self._pending_pick_release: Optional[Tuple[float, float, object]] = None
        self._pending_hover: Optional[Tuple[float, float, object]] = None

        layout = self._container.layout()
        if layout is None:
            layout = QVBoxLayout(self._container)
            self._container.setLayout(layout)

        window = self._world.create_window(
            width=900,
            height=800,
            title="viewport",
            parent=self._container,
        )
        viewport = window.add_viewport(self._scene, self._camera)
        window.set_world_mode("editor")

        self._backend = ViewportBackend(window, viewport)

        viewport.set_render_pipeline(self._make_pipeline())

        window.on_mouse_button_event = self._on_mouse_button_event
        window.after_render_handler = self._after_render
        window.on_mouse_move_event = self._on_mouse_move

        gl_widget = window.handle.widget
        gl_widget.setFocusPolicy(Qt.StrongFocus)
        gl_widget.setMinimumSize(50, 50)
        layout.addWidget(gl_widget)

        self._gl_widget = gl_widget

    # ---------- свойства для EditorWindow ----------

    @property
    def window(self):
        return self._backend.window

    @property
    def gl_widget(self):
        return self._gl_widget

    def request_update(self) -> None:
        self._backend.request_update()

    def get_pick_id_for_entity(self, ent: Entity | None) -> int:
        if ent is None:
            return 0
        return ent.pick_id

    # ---------- внутренние обработчики событий ----------

    def _on_mouse_button_event(self, button_type, action, x, y, viewport) -> None:
        if button_type == MouseButton.LEFT and action == Action.RELEASE:
            self._pending_pick_release = (x, y, viewport)
        if button_type == MouseButton.LEFT and action == Action.PRESS:
            self._pending_pick_press = (x, y, viewport)

    def _on_mouse_move(self, x: float, y: float, viewport) -> None:
        """
        При каждом движении мыши запоминаем, что нужно сделать hover-pick после рендера.
        """
        if viewport is None:
            self._pending_hover = None
            return
        self._pending_hover = (x, y, viewport)

    def _after_render(self, window) -> None:
        if self._pending_pick_press is not None:
            self._process_pending_pick_press(self._pending_pick_press, window)
        if self._pending_pick_release is not None:
            self._process_pending_pick_release(self._pending_pick_release, window)
        if self._pending_hover is not None:
            self._process_pending_hover(self._pending_hover, window)

        # обновляем окно дебагера уже после того, как все FBO обновлены
        if self._framegraph_debugger is not None and self._framegraph_debugger.isVisible():
            self._framegraph_debugger.debugger_request_update()

    # ---------- обработка hover / выбора / гизмо ----------

    def _process_pending_hover(self, pending_hover, window) -> None:
        x, y, viewport = pending_hover
        self._pending_hover = None

        ent = self._backend.pick_entity_at(x, y, viewport)
        if ent is not None and not ent.selectable:
            ent = None

        self._on_hover_entity(ent)

    def _process_pending_pick_release(self, pending_release, window) -> None:
        x, y, viewport = pending_release
        self._pending_pick_release = None

        ent = self._backend.pick_entity_at(x, y, viewport)
        if ent is not None and not ent.selectable:
            ent = None

        self._on_entity_picked(ent)

    def _process_pending_pick_press(self, pending_press, window) -> None:
        x, y, viewport = pending_press
        self._pending_pick_press = None

        picked_color = self._backend.pick_color_at(x, y, viewport, buffer_name="id")
        handled = self._gizmo_controller.handle_pick_press_with_color(
            x, y, viewport, picked_color
        )
        if handled:
            return

    # ---------- debug helpers ----------

    def set_framegraph_debugger(self, debugger) -> None:
        """
        Регистрирует окно дебагера framegraph, которому нужно сообщать
        об окончании рендера и передавать настройки источника/паузы.
        """
        self._framegraph_debugger = debugger

    def set_debug_source_resource(self, name: str) -> None:
        """
        Устанавливает имя ресурса framegraph, из которого BlitPass будет копировать текстуру.
        """
        self._debug_source_res = name
        self.request_update()

    def get_debug_source_resource(self) -> str:
        """
        Возвращает текущее имя ресурса framegraph, используемое BlitPass как источник.
        """
        return self._debug_source_res

    def get_debug_blit_pass(self):
        """
        Возвращает BlitPass из пайплайна для управления дебаггером.
        """
        viewport = self._backend.viewport
        if viewport.pipeline is not None:
            return viewport.pipeline.debug_blit_pass
        return None

    def get_available_framegraph_resources(self) -> list[str]:
        """
        Возвращает список имён ресурсов framegraph, доступных у текущего viewport.
        """
        viewport = self._backend.viewport
        return list(viewport.fbos.keys())

    def set_debug_paused(self, paused: bool) -> None:
        """
        Включает или выключает паузу BlitPass: при паузе новые кадры не копируются.
        """
        self._debug_paused = paused
        self.request_update()

    def get_debug_paused(self) -> bool:
        """
        Текущее состояние паузы для BlitPass.
        """
        return self._debug_paused

    # ---------- internal debug symbols ----------

    def get_passes_info(self) -> list[tuple[str, bool]]:
        """
        Возвращает список пассов с информацией о наличии внутренних символов.

        Возвращает:
            Список кортежей (pass_name, has_internal_symbols).
        """
        viewport = self._backend.viewport
        result: list[tuple[str, bool]] = []
        if viewport.pipeline is None:
            return result
        for p in viewport.pipeline.passes:
            symbols = p.get_internal_symbols()
            has_symbols = len(symbols) > 0
            result.append((p.pass_name, has_symbols))
        return result

    def get_pass_internal_symbols(self, pass_name: str) -> list[str]:
        """
        Возвращает список внутренних символов для указанного пасса.

        Параметры:
            pass_name: Имя пасса.

        Возвращает:
            Список символов или пустой список.
        """
        viewport = self._backend.viewport
        if viewport.pipeline is None:
            return []
        for p in viewport.pipeline.passes:
            if p.pass_name == pass_name:
                return p.get_internal_symbols()
        return []

    def set_pass_internal_symbol(self, pass_name: str, symbol: str | None) -> None:
        """
        Устанавливает внутреннюю точку дебага для указанного пасса.
        Параметры:
            pass_name: Имя пасса.
            symbol: Имя символа или None для сброса.
        """
        viewport = self._backend.viewport
        if viewport.pipeline is None:
            return
        blit_pass = viewport.pipeline.debug_blit_pass
        for p in viewport.pipeline.passes:
            if p.pass_name == pass_name:
                if symbol is None or symbol == "":
                    p.set_debug_internal_point(None, None)
                    # Включаем BlitPass обратно
                    if blit_pass is not None:
                        blit_pass.enabled = True
                else:
                    p.set_debug_internal_point(symbol, "debug")
                    # Отключаем BlitPass
                    if blit_pass is not None:
                        blit_pass.enabled = False
                self.request_update()
                return

    # ---------- pipeline ----------

    def _make_pipeline(self) -> RenderPipeline:
        from termin.visualization.render.framegraph import (
            ColorPass,
            IdPass,
            CanvasPass,
            PresentToScreenPass,
            GizmoPass,
        )
        from termin.visualization.render.postprocess import PostProcessPass
        from termin.visualization.render.posteffects.fog import FogEffect
        from termin.visualization.render.posteffects.highlight import HighlightEffect
        from termin.visualization.render.framegraph.passes.present import BlitPass
        from termin.visualization.render.framegraph.passes.depth import DepthPass

        gizmo_entities = self._gizmo_controller.helper_geometry_entities()

        postprocess = PostProcessPass(
            effects=[],
            input_res="color",
            output_res="color_pp",
            pass_name="PostFX",
        )

        # BlitPass копирует выбранный ресурс в отдельный debug-ресурс.
        # Источник и режим паузы задаются через колбэк, читающий состояние контроллера.
        # При выборе внутренней точки пасса BlitPass отключается через enabled=False.
        def _get_debug_source():
            if self._debug_paused:
                return None
            return self._debug_source_res

        blit_pass = BlitPass(
            get_source_res=_get_debug_source,
            output_res="debug",
            pass_name="DebugBlit",
        )

        depth_pass = DepthPass(input_res="empty_depth", output_res="depth", pass_name="Depth")
        color_pass = ColorPass(input_res="empty", output_res="color", pass_name="Color")

        passes: list = [
            color_pass,
            depth_pass,
            IdPass(input_res="empty_id", output_res="preid", pass_name="Id"),
            GizmoPass(
                input_res="preid",
                output_res="id",
                pass_name="Gizmo",
                gizmo_entities=gizmo_entities,
            ),
            postprocess,
            blit_pass,
            CanvasPass(
                src="color_pp",
                dst="color+ui",
                pass_name="Canvas",
            ),
            PresentToScreenPass(
                input_res="color+ui",
                pass_name="Present",
            ),
        ]

        postprocess.add_effect(
            HighlightEffect(
                lambda: self.hover_entity_id,
                color=(0.3, 0.8, 1.0, 1.0),
            )
        )
        postprocess.add_effect(
            HighlightEffect(
                lambda: self.selected_entity_id,
                color=(1.0, 0.9, 0.1, 1.0),
            )
        )

        postprocess.add_effect(
            FogEffect(
                fog_color=(0.5, 0.6, 0.7),
                fog_start=0.3,
                fog_end=1.0,
            )
        )

        # Спецификации очистки ресурсов перед рендерингом
        clear_specs = [
            ClearSpec(resource="empty", color=(0.2, 0.2, 0.2, 1.0), depth=1.0),
            ClearSpec(resource="empty_id", color=(0.0, 0.0, 0.0, 1.0), depth=1.0),
        ]

        return RenderPipeline(
            passes=passes, 
            clear_specs=clear_specs, 
            debug_blit_pass=blit_pass,
        )
