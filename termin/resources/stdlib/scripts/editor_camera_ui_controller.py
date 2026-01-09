"""
EditorCameraUIController - контроллер для UI редакторской камеры.

Подписывается на кнопки в editor_camera_ui.uiscript и управляет:
- Отображением коллайдеров (ColliderGizmoPass.enabled)
- Режимом wireframe (TODO)
- Ортографической камерой (TODO)

Использование:
    Контроллер должен быть на entity-потомке камеры (или на самой камере).
    Он найдёт CameraComponent и через него получит viewport.pipeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.visualization.core.python_component import PythonComponent
from termin.visualization.core.camera import CameraComponent
from termin.visualization.ui.widgets.component import UIComponent
from termin.visualization.ui.widgets.basic import IconButton
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.core.viewport import Viewport


class EditorCameraUIController(PythonComponent):
    """
    Контроллер UI редакторской камеры.

    Ищет CameraComponent на своей entity или родителях,
    через него получает viewport и доступ к pipeline.passes.
    """

    inspect_fields = {
        "colliders_enabled": InspectField(
            path="colliders_enabled",
            kind="bool",
            is_serializable=True,
            is_inspectable=True,
        ),
        "wireframe_enabled": InspectField(
            path="wireframe_enabled",
            kind="bool",
            is_serializable=True,
            is_inspectable=True,
        ),
        "ortho_enabled": InspectField(
            path="ortho_enabled",
            kind="bool",
            is_serializable=True,
            is_inspectable=True,
        ),
    }

    def __init__(self):
        super().__init__(enabled=True)
        self.active_in_editor = True  # Работает в режиме редактора
        self._ui_component: UIComponent | None = None
        self._camera_component: CameraComponent | None = None

        # Serializable state
        self.colliders_enabled: bool = False
        self.wireframe_enabled: bool = False
        self.ortho_enabled: bool = False

        # Кнопки (найдутся в start)
        self._colliders_btn: IconButton | None = None
        self._wireframe_btn: IconButton | None = None
        self._ortho_btn: IconButton | None = None

    @property
    def viewport(self) -> "Viewport | None":
        """Получает viewport через CameraComponent."""
        if self._camera_component is not None:
            return self._camera_component.viewport
        return None

    def start(self) -> None:
        """Инициализация при старте."""
        self._setup()

    def on_scene_active(self) -> None:
        """Перепривязка при активации сцены (после возврата из INACTIVE)."""
        self._setup()

    def _setup(self) -> None:
        """Инициализация: поиск компонентов и привязка обработчиков."""
        self._find_camera_component()
        self._find_ui_component()
        self._bind_buttons()

        print(f"EditorCameraUIController setup. camera={id(self._camera_component)}")
        self._sync_button_states()

    def _find_camera_component(self) -> None:
        """Ищет CameraComponent на своей entity или родителях."""
        entity = self.entity
        while entity is not None:
            for comp in entity.components:
                if isinstance(comp, CameraComponent):
                    self._camera_component = comp
                    return
            entity = entity.parent

    def _find_ui_component(self) -> None:
        """Ищет UIComponent на своей Entity."""
        if self.entity is None:
            return
        for comp in self.entity.components:
            if isinstance(comp, UIComponent):
                self._ui_component = comp
                break

    def _bind_buttons(self) -> None:
        """Привязка обработчиков к кнопкам."""
        if self._ui_component is None:
            return

        self._colliders_btn = self._ui_component.find("colliders_btn")
        if self._colliders_btn is not None:
            self._colliders_btn.on_click = self._on_colliders_click

        self._wireframe_btn = self._ui_component.find("wireframe_btn")
        if self._wireframe_btn is not None:
            self._wireframe_btn.on_click = self._on_wireframe_click

        self._ortho_btn = self._ui_component.find("ortho_btn")
        if self._ortho_btn is not None:
            self._ortho_btn.on_click = self._on_ortho_click

    def _sync_button_states(self) -> None:
        """Применяет сохранённые состояния к кнопкам и пассам."""
        # Colliders
        collider_pass = self._find_pass_by_name("ColliderGizmo")
        if collider_pass is not None:
            collider_pass.passthrough = not self.colliders_enabled
        if self._colliders_btn is not None:
            self._colliders_btn.active = self.colliders_enabled

        # Wireframe
        color_pass = self._find_pass_by_name("Color")
        transparent_pass = self._find_pass_by_name("Transparent")
        if color_pass is not None:
            color_pass.wireframe = self.wireframe_enabled
        if transparent_pass is not None:
            transparent_pass.wireframe = self.wireframe_enabled
        if self._wireframe_btn is not None:
            self._wireframe_btn.active = self.wireframe_enabled

        # Ortho
        if self._camera_component is not None:
            self._camera_component.projection_type = "orthographic" if self.ortho_enabled else "perspective"
        if self._ortho_btn is not None:
            self._ortho_btn.active = self.ortho_enabled

    def _find_pass_by_name(self, pass_name: str):
        """Ищет пасс по имени в pipeline."""
        vp = self.viewport
        if vp is None or vp.pipeline is None:
            return None
        for p in vp.pipeline.passes:
            if p.pass_name == pass_name:
                return p
        return None

    def _on_colliders_click(self) -> None:
        """Переключает отображение коллайдеров."""
        self.colliders_enabled = not self.colliders_enabled

        print(f"[EditorCameraUIController] Colliders enabled: camera={id(self._camera_component)}, viewports={self._camera_component.viewports}")

        collider_pass = self._find_pass_by_name("ColliderGizmo")
        if collider_pass is not None:
            collider_pass.passthrough = not self.colliders_enabled
        if self._colliders_btn is not None:
            self._colliders_btn.active = self.colliders_enabled

    def _on_wireframe_click(self) -> None:
        """Переключает wireframe режим."""
        self.wireframe_enabled = not self.wireframe_enabled

        color_pass = self._find_pass_by_name("Color")
        transparent_pass = self._find_pass_by_name("Transparent")

        if color_pass is not None:
            color_pass.wireframe = self.wireframe_enabled
        if transparent_pass is not None:
            transparent_pass.wireframe = self.wireframe_enabled
        if self._wireframe_btn is not None:
            self._wireframe_btn.active = self.wireframe_enabled

    def _on_ortho_click(self) -> None:
        """Переключает ортографическую камеру."""
        self.ortho_enabled = not self.ortho_enabled

        if self._camera_component is not None:
            self._camera_component.projection_type = "orthographic" if self.ortho_enabled else "perspective"
        if self._ortho_btn is not None:
            self._ortho_btn.active = self.ortho_enabled
