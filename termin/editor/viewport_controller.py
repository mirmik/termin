from __future__ import annotations

from typing import Callable, Optional, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout

from termin.visualization.core.entity import Entity
from termin.visualization.render.framegraph import (
    ColorPass,
    IdPass,
    CanvasPass,
    PresentToScreenPass,
    GizmoPass,
)
from termin.visualization.render.postprocess import PostProcessPass
from termin.visualization.render.posteffects.highlight import HighlightEffect
from termin.visualization.platform.backends.base import Action, MouseButton

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
        return self._window._get_pick_id_for_entity(ent)


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
        return self._backend.get_pick_id_for_entity(ent)

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

    # ---------- обработка hover / выбора / гизмо ----------

    def _process_pending_hover(self, pending_hover, window) -> None:
        x, y, viewport = pending_hover
        self._pending_hover = None

        ent = self._backend.pick_entity_at(x, y, viewport)
        if ent is not None and getattr(ent, "selectable", True) is False:
            ent = None

        self._on_hover_entity(ent)

    def _process_pending_pick_release(self, pending_release, window) -> None:
        x, y, viewport = pending_release
        self._pending_pick_release = None

        ent = self._backend.pick_entity_at(x, y, viewport)
        if ent is not None and getattr(ent, "selectable", True) is False:
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

    # ---------- pipeline ----------

    def _make_pipeline(self) -> list:
        from termin.visualization.render.framegraph import (
            ColorPass,
            IdPass,
            CanvasPass,
            PresentToScreenPass,
            GizmoPass,
        )
        from termin.visualization.render.postprocess import PostProcessPass
        from termin.visualization.render.posteffects.highlight import HighlightEffect

        gizmo_entities = self._gizmo_controller.helper_geometry_entities()

        postprocess = PostProcessPass(
            effects=[],
            input_res="color",
            output_res="color_pp",
            pass_name="PostFX",
        )

        passes: list = [
            ColorPass(input_res="empty", output_res="color", pass_name="Color"),
            IdPass(input_res="empty_id", output_res="preid", pass_name="Id"),
            GizmoPass(
                input_res="preid",
                output_res="id",
                pass_name="Gizmo",
                gizmo_entities=gizmo_entities,
            ),
            postprocess,
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

        return passes
