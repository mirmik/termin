from __future__ import annotations

from typing import Callable, Optional, Tuple, TYPE_CHECKING

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QWindow
from PyQt6.QtWidgets import QWidget, QVBoxLayout

from termin.visualization.core.display import Display
from termin.visualization.core.entity import Entity
from termin.visualization.core.viewport import Viewport
from termin.visualization.platform.backends.base import Action, MouseButton
from termin.visualization.render.framegraph import RenderPipeline
from termin.visualization.render import (
    RenderEngine,
    RenderView,
    ViewportRenderState,
    WindowRenderSurface,
)
from termin.visualization.render.framegraph.resource_spec import ResourceSpec

from termin.editor.gizmo import GizmoController
from termin.editor.editor_display_input_manager import EditorDisplayInputManager

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import BackendWindow, GraphicsBackend
    from termin.visualization.platform.backends.sdl_embedded import (
        SDLEmbeddedWindowBackend,
        SDLEmbeddedWindowHandle,
    )


class ViewportController:
    """
    Управляет рендерингом в окне редактора.

    Использует SDL для рендеринга, встроенный в Qt виджет.
    Pull-model: рендеринг вызывается явно из главного цикла.

    Владеет:
    - Display (viewports + surface)
    - EditorDisplayInputManager (обработка ввода)
    - RenderEngine (выполняет рендеринг)
    - ViewportRenderState (pipeline + FBO пул)
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
        sdl_backend: "SDLEmbeddedWindowBackend",
    ) -> None:
        self._container = container
        self._world = world
        self._scene = scene
        self._camera = camera
        self._gizmo_controller = gizmo_controller
        self._on_entity_picked = on_entity_picked
        self._on_hover_entity = on_hover_entity
        self._sdl_backend = sdl_backend
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

        # Получаем graphics от world
        self._graphics: "GraphicsBackend" = self._world.graphics

        # Создаём SDL окно
        self._backend_window: "SDLEmbeddedWindowHandle" = sdl_backend.create_embedded_window(
            width=800,
            height=600,
            title="SDL Viewport",
        )

        # Встраиваем SDL окно в Qt через QWindow.fromWinId
        native_handle = self._backend_window.native_handle
        self._qwindow = QWindow.fromWinId(native_handle)
        self._gl_widget = QWidget.createWindowContainer(self._qwindow, self._container)
        self._gl_widget.setMinimumSize(50, 50)
        self._gl_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout.addWidget(self._gl_widget)

        # Создаём WindowRenderSurface
        self._render_surface = WindowRenderSurface(self._backend_window)

        # Создаём Display
        self._display = Display(self._render_surface)

        # Создаём viewport
        viewport = self._display.create_viewport(self._scene, self._camera)
        self._viewport = viewport

        # Создаём RenderEngine
        self._render_engine = RenderEngine(self._graphics)

        # Словарь ViewportRenderState для каждого viewport (по id)
        # Каждый viewport имеет свой FBO пул
        self._viewport_states: dict[int, ViewportRenderState] = {}

        # Создаём state для первого viewport
        self._viewport_states[id(viewport)] = ViewportRenderState(pipeline=self._make_pipeline())

        # Создаём EditorDisplayInputManager
        self._input_manager = EditorDisplayInputManager(
            backend_window=self._backend_window,
            display=self._display,
            graphics=self._graphics,
            get_fbo_pool=self._get_fbo_pool_for_picking,
            on_request_update=self.request_update,
            on_mouse_button_event=self._on_mouse_button_event,
            on_mouse_move_event=self._on_mouse_move,
        )
        self._input_manager.set_world_mode("editor")

    def render(self) -> None:
        """
        Выполняет рендеринг через RenderEngine.

        Вызывается явно из главного цикла редактора.
        """
        # CRITICAL: Ensure SDL GL context is current before ANY GL operations
        # Qt may have switched to its own context
        self._backend_window.make_current()

        # Проверяем resize
        self._backend_window.check_resize()

        self._graphics.ensure_ready()
        # Don't call make_current again - we already did it above
        # self._render_surface.make_current()

        # Собираем пары (RenderView, ViewportRenderState) для всех viewport'ов
        # Сортируем по depth (меньше = раньше)
        views_and_states = []
        sorted_viewports = sorted(self._display.viewports, key=lambda v: v.depth)
        for viewport in sorted_viewports:
            # Получаем или создаём state для viewport'а
            state = self._get_or_create_state(viewport)

            view = RenderView(
                scene=viewport.scene,
                camera=viewport.camera,
                rect=viewport.rect,
                canvas=viewport.canvas,
            )
            views_and_states.append((view, state))

        # Рендерим все viewport'ы
        # present=False - мы сами вызываем swap_buffers ниже
        self._render_engine.render_views(
            surface=self._render_surface,
            views=views_and_states,
            present=False,
        )

        # Swap buffers (единственный раз за кадр)
        self._backend_window.swap_buffers()

        # Обрабатываем отложенные события после рендера
        self._after_render()

    def needs_render(self) -> bool:
        """Проверяет, нужен ли рендеринг."""
        return self._backend_window.needs_render()

    def _get_or_create_state(self, viewport: Viewport) -> ViewportRenderState:
        """Получает или создаёт ViewportRenderState для viewport'а."""
        key = id(viewport)
        if key not in self._viewport_states:
            self._viewport_states[key] = ViewportRenderState(pipeline=self._make_pipeline())
        return self._viewport_states[key]

    def _get_primary_state(self) -> ViewportRenderState:
        """Возвращает state первого (основного) viewport'а."""
        return self._get_or_create_state(self._viewport)

    def _get_fbo_pool_for_picking(self) -> dict:
        """Возвращает FBO пул для picking (от основного viewport'а)."""
        return self._get_primary_state().fbos

    # ---------- свойства для EditorWindow ----------

    @property
    def display(self) -> Display:
        """Display с viewport'ами."""
        return self._display

    @property
    def window(self):
        """Для обратной совместимости. Возвращает объект с нужными атрибутами."""
        return self

    @property
    def handle(self):
        """BackendWindow для совместимости."""
        return self._backend_window

    @property
    def graphics(self):
        """GraphicsBackend."""
        return self._graphics

    @property
    def viewport(self):
        return self._viewport

    @property
    def gl_widget(self):
        return self._gl_widget

    @property
    def render_state(self) -> ViewportRenderState:
        """Доступ к состоянию рендера основного viewport'а (pipeline, fbos)."""
        return self._get_primary_state()

    @property
    def input_manager(self) -> EditorDisplayInputManager:
        """Менеджер ввода редактора."""
        return self._input_manager

    def set_camera(self, camera) -> None:
        """Устанавливает новую камеру для viewport."""
        self._camera = camera
        self._viewport.camera = camera
        # Камера должна знать свой viewport для обработки ввода
        camera.viewport = self._viewport

    def set_scene(self, scene) -> None:
        """Устанавливает новую сцену для viewport."""
        self._scene = scene
        self._viewport.scene = scene

    def set_world_mode(self, mode: str) -> None:
        """Устанавливает режим работы (editor/game)."""
        self._input_manager.set_world_mode(mode)

    def request_update(self) -> None:
        """Запрашивает перерисовку."""
        self._backend_window.request_update()

    def get_pick_id_for_entity(self, ent: Entity | None) -> int:
        if ent is None:
            return 0
        return ent.pick_id

    # ---------- picking через EditorDisplayInputManager ----------

    def pick_entity_at(self, x: float, y: float, viewport: Viewport) -> Entity | None:
        """Читает entity из id-карты через FBO пул."""
        return self._input_manager.pick_entity_at(x, y, viewport)

    def pick_color_at(self, x: float, y: float, viewport: Viewport, buffer_name: str = "id"):
        """Читает цвет пикселя из FBO пула."""
        return self._input_manager.pick_color_at(x, y, viewport, buffer_name)

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

    def _after_render(self) -> None:
        if self._pending_pick_press is not None:
            self._process_pending_pick_press(self._pending_pick_press)
        if self._pending_pick_release is not None:
            self._process_pending_pick_release(self._pending_pick_release)
        if self._pending_hover is not None:
            self._process_pending_hover(self._pending_hover)

        if self._framegraph_debugger is not None and self._framegraph_debugger.isVisible():
            self._framegraph_debugger.debugger_request_update()

    # ---------- обработка hover / выбора / гизмо ----------

    def _process_pending_hover(self, pending_hover) -> None:
        x, y, viewport = pending_hover
        self._pending_hover = None

        ent = self.pick_entity_at(x, y, viewport)
        if ent is not None and not ent.selectable:
            ent = None

        self._on_hover_entity(ent)

    def _process_pending_pick_release(self, pending_release) -> None:
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

    def _process_pending_pick_press(self, pending_press) -> None:
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
        pipeline = self._get_primary_state().pipeline
        if pipeline is not None:
            return pipeline.debug_blit_pass
        return None

    def get_available_framegraph_resources(self) -> list[str]:
        return list(self._get_primary_state().fbos.keys())

    def set_debug_paused(self, paused: bool) -> None:
        self._debug_paused = paused
        self.request_update()

    def get_debug_paused(self) -> bool:
        return self._debug_paused

    # ---------- internal debug symbols ----------

    def get_passes_info(self) -> list[tuple[str, bool]]:
        result: list[tuple[str, bool]] = []
        pipeline = self._get_primary_state().pipeline
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
        pipeline = self._get_primary_state().pipeline
        if pipeline is None:
            return []
        for p in pipeline.passes:
            if p.pass_name == pass_name:
                return p.get_internal_symbols()
        return []

    def set_pass_internal_symbol(self, pass_name: str, symbol: str | None) -> None:
        pipeline = self._get_primary_state().pipeline
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

        # Передаём lambda, чтобы gizmo entities обновлялись динамически
        # (важно после recreate_gizmo при выходе из game mode)
        def get_gizmo_entities():
            return self._gizmo_controller.helper_geometry_entities()

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
                gizmo_entities=get_gizmo_entities,
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
