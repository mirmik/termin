from __future__ import annotations

from typing import Callable, Optional, Tuple

import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout

from termin.visualization.core.entity import Entity
from termin.visualization.core.viewport import Viewport
from termin.visualization.platform.backends.base import Action, MouseButton
from termin.visualization.render.framegraph import RenderPipeline
from termin.visualization.render import (
    RenderEngine,
    RenderView,
    ViewportRenderState,
)
from termin.visualization.render.framegraph.resource_spec import ResourceSpec

from termin.editor.gizmo import GizmoController


class ViewportController:
    """
    Управляет рендерингом в окне редактора.
    
    Владеет:
    - RenderEngine (выполняет рендеринг)
    - ViewportRenderState (pipeline + FBO пул)
    - WindowRenderSurface (куда рендерим)
    
    Ссылается на:
    - Window (события мыши/клавиатуры)
    - Viewport (scene + camera + rect)
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

        # Для определения клика vs drag: запоминаем позицию press
        self._press_position: Optional[Tuple[float, float]] = None
        self._gizmo_handled_press: bool = False
        # Порог в пикселях для определения клика (если мышь сдвинулась меньше — это клик)
        self._click_threshold: float = 5.0

        layout = self._container.layout()
        if layout is None:
            layout = QVBoxLayout(self._container)
            self._container.setLayout(layout)

        # Создаём окно через world
        window = self._world.create_window(
            width=900,
            height=800,
            title="viewport",
            parent=self._container,
        )
        
        # Создаём viewport (теперь без pipeline и fbos)
        viewport = window.add_viewport(self._scene, self._camera)
        window.set_world_mode("editor")

        self._window = window
        self._viewport = viewport

        # Создаём новую архитектуру рендеринга
        self._render_engine = RenderEngine(window.graphics)
        self._render_surface = window.render_surface  # Берём surface из окна
        self._render_state = ViewportRenderState(pipeline=self._make_pipeline())

        # Подписываемся на события
        window.on_mouse_button_event = self._on_mouse_button_event
        window.after_render_handler = self._after_render
        window.on_mouse_move_event = self._on_mouse_move

        gl_widget = window.handle.widget
        gl_widget.setFocusPolicy(Qt.StrongFocus)
        gl_widget.setMinimumSize(50, 50)
        layout.addWidget(gl_widget)

        self._gl_widget = gl_widget

        # Подключаем рендер к Qt виджету
        self._setup_qt_render()

    def _setup_qt_render(self) -> None:
        """
        Настраивает рендеринг для Qt виджета.
        
        Qt OpenGL виджет вызывает paintGL при необходимости перерисовки.
        Нам нужно перехватить это и вызвать наш RenderEngine.
        """
        # Qt backend сам вызывает render, нужно подменить метод
        original_paint = self._gl_widget.paintGL
        
        def custom_paint():
            self._do_render()
        
        self._gl_widget.paintGL = custom_paint

    def _do_render(self) -> None:
        """
        Выполняет рендеринг через RenderEngine.
        """
        if self._window.handle is None:
            return

        self._window.graphics.ensure_ready()
        self._render_surface.make_current()

        # Создаём RenderView из Viewport
        view = RenderView(
            scene=self._viewport.scene,
            camera=self._viewport.camera,
            rect=self._viewport.rect,
            canvas=self._viewport.canvas,
        )

        # Рендерим
        self._render_engine.render_single_view(
            surface=self._render_surface,
            view=view,
            state=self._render_state,
            present=False,  # Qt сам делает swap buffers
        )

        # Вызываем after_render_handler
        if self._window.after_render_handler is not None:
            self._window.after_render_handler(self._window)

    # ---------- свойства для EditorWindow ----------

    @property
    def window(self):
        return self._window

    @property
    def viewport(self):
        return self._viewport

    @property
    def gl_widget(self):
        return self._gl_widget

    @property
    def render_state(self) -> ViewportRenderState:
        """Доступ к состоянию рендера (pipeline, fbos)."""
        return self._render_state

    def set_camera(self, camera) -> None:
        """Устанавливает новую камеру для viewport."""
        self._camera = camera
        self._viewport.camera = camera
        # Камера должна знать свой viewport для обработки ввода
        camera.viewport = self._viewport

    def request_update(self) -> None:
        self._window._request_update()

    def get_pick_id_for_entity(self, ent: Entity | None) -> int:
        if ent is None:
            return 0
        return ent.pick_id

    # ---------- picking через новый API ----------

    def pick_entity_at(self, x: float, y: float, viewport: Viewport) -> Entity | None:
        """Читает entity из id-карты через FBO пул."""
        return self._window.pick_entity_at(x, y, self._render_state.fbos, viewport)

    def pick_color_at(self, x: float, y: float, viewport: Viewport, buffer_name: str = "id"):
        """Читает цвет пикселя из FBO пула."""
        return self._window.pick_color_at(x, y, self._render_state.fbos, viewport, buffer_name)

    # ---------- внутренние обработчики событий ----------

    def _on_mouse_button_event(self, button_type, action, x, y, viewport) -> None:
        if button_type == MouseButton.LEFT and action == Action.RELEASE:
            self._pending_pick_release = (x, y, viewport)
        if button_type == MouseButton.LEFT and action == Action.PRESS:
            self._pending_pick_press = (x, y, viewport)

    def _on_mouse_move(self, x: float, y: float, viewport) -> None:
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

        if self._framegraph_debugger is not None and self._framegraph_debugger.isVisible():
            self._framegraph_debugger.debugger_request_update()

    # ---------- обработка hover / выбора / гизмо ----------

    def _process_pending_hover(self, pending_hover, window) -> None:
        x, y, viewport = pending_hover
        self._pending_hover = None

        ent = self.pick_entity_at(x, y, viewport)
        if ent is not None and not ent.selectable:
            ent = None

        self._on_hover_entity(ent)

    def _process_pending_pick_release(self, pending_release, window) -> None:
        """
        Обрабатывает отпускание левой кнопки мыши.
        
        Выбор объекта (select) происходит только если:
        1. Гизмо не обрабатывал нажатие (не было начато перемещение/вращение)
        2. Мышь не сдвинулась значительно от точки нажатия (это клик, а не drag)
        """
        x, y, viewport = pending_release
        self._pending_pick_release = None

        # Если гизмо обработал press (начал drag), не делаем select
        if self._gizmo_handled_press:
            self._gizmo_handled_press = False
            self._press_position = None
            return

        # Проверяем, был ли это клик (мышь не сдвинулась значительно)
        if self._press_position is not None:
            press_x, press_y = self._press_position
            dx = x - press_x
            dy = y - press_y
            distance_sq = dx * dx + dy * dy
            threshold_sq = self._click_threshold * self._click_threshold
            if distance_sq > threshold_sq:
                # Это был drag, не делаем select
                self._press_position = None
                return
            self._press_position = None
        # Если _press_position is None — press не был обработан,
        # но делаем select для обратной совместимости.

        ent = self.pick_entity_at(x, y, viewport)
        if ent is not None and not ent.selectable:
            ent = None

        self._on_entity_picked(ent)

    def _process_pending_pick_press(self, pending_press, window) -> None:
        """
        Обрабатывает нажатие левой кнопки мыши.
        
        Запоминаем позицию для последующего определения, был ли это клик или drag.
        Если клик попал по гизмо — начинаем drag гизмо и помечаем, что select не нужен.
        """
        x, y, viewport = pending_press
        self._pending_pick_press = None

        # Запоминаем позицию press для определения клика
        self._press_position = (x, y)
        self._gizmo_handled_press = False

        picked_color = self.pick_color_at(x, y, viewport, buffer_name="id")
        handled = self._gizmo_controller.handle_pick_press_with_color(
            x, y, viewport, picked_color
        )
        if handled:
            # Гизмо обработал клик — помечаем, чтобы при release не делать select
            self._gizmo_handled_press = True
            return

    # ---------- debug helpers ----------

    def set_framegraph_debugger(self, debugger) -> None:
        self._framegraph_debugger = debugger

    def set_debug_source_resource(self, name: str) -> None:
        self._debug_source_res = name
        self.request_update()

    def get_debug_source_resource(self) -> str:
        return self._debug_source_res

    def get_debug_blit_pass(self):
        pipeline = self._render_state.pipeline
        if pipeline is not None:
            return pipeline.debug_blit_pass
        return None

    def get_available_framegraph_resources(self) -> list[str]:
        return list(self._render_state.fbos.keys())

    def set_debug_paused(self, paused: bool) -> None:
        self._debug_paused = paused
        self.request_update()

    def get_debug_paused(self) -> bool:
        return self._debug_paused

    # ---------- internal debug symbols ----------

    def get_passes_info(self) -> list[tuple[str, bool]]:
        result: list[tuple[str, bool]] = []
        pipeline = self._render_state.pipeline
        if pipeline is None:
            return result
        for p in pipeline.passes:
            # Игнорируем внутренние символы для ShadowPass
            # (ShadowMapArray не поддерживает отладку внутренних символов)
            from termin.visualization.render.framegraph.passes.shadow import ShadowPass
            if isinstance(p, ShadowPass):
                has_symbols = False
            else:
                symbols = p.get_internal_symbols()
                has_symbols = len(symbols) > 0
            result.append((p.pass_name, has_symbols))
        return result

    def get_pass_internal_symbols(self, pass_name: str) -> list[str]:
        pipeline = self._render_state.pipeline
        if pipeline is None:
            return []
        for p in pipeline.passes:
            if p.pass_name == pass_name:
                return p.get_internal_symbols()
        return []

    def set_pass_internal_symbol(self, pass_name: str, symbol: str | None) -> None:
        pipeline = self._render_state.pipeline
        if pipeline is None:
            return
        blit_pass = pipeline.debug_blit_pass
        for p in pipeline.passes:
            if p.pass_name == pass_name:
                if symbol is None or symbol == "":
                    p.set_debug_internal_point(None, None)
                    if blit_pass is not None:
                        blit_pass.enabled = True
                else:
                    p.set_debug_internal_point(symbol, "debug")
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
        from termin.visualization.render.framegraph.passes.frame_debugger import FrameDebuggerPass
        from termin.visualization.render.framegraph.passes.depth import DepthPass
        from termin.visualization.render.framegraph.passes.skybox import SkyBoxPass
        from termin.visualization.render.framegraph.passes.shadow import ShadowPass

        gizmo_entities = self._gizmo_controller.helper_geometry_entities()

        postprocess = PostProcessPass(
            effects=[],
            input_res="color",
            output_res="color_pp",
            pass_name="PostFX",
        )

        def _get_debug_source():
            if self._debug_paused:
                return None
            return self._debug_source_res

        blit_pass = FrameDebuggerPass(
            get_source_res=_get_debug_source,
            output_res="debug",
            pass_name="DebugBlit",
        )

        depth_pass = DepthPass(input_res="empty_depth", output_res="depth", pass_name="Depth")
        
        # ColorPass читает shadow_maps для shadow mapping
        color_pass = ColorPass(
            input_res="skybox",
            output_res="color",
            shadow_res="shadow_maps",
            pass_name="Color",
        )

        skybox_pass = SkyBoxPass(input_res="empty", output_res="skybox", pass_name="Skybox")

        # Shadow pass — генерирует shadow maps для всех directional lights с тенями
        shadow_pass = ShadowPass(
            output_res="shadow_maps",
            pass_name="Shadow",
            default_resolution=1024,
            ortho_size=20.0,
            near=0.1,
            far=100.0,
        )

        passes: list = [
            shadow_pass,
            skybox_pass,
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

        # postprocess.add_effect(
        #     FogEffect(
        #         fog_color=(0.5, 0.6, 0.7),
        #         fog_start=0.3,
        #         fog_end=1.0,
        #     )
        # )

        # ResourceSpec'ы для очистки ресурсов теперь объявляются в самих pass'ах
        # через метод get_resource_specs()

        return RenderPipeline(
            passes=passes,
            debug_blit_pass=blit_pass,
            pipeline_specs=[],
        )
