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

from termin.visualization.core.component import Component
from termin.visualization.core.camera import CameraComponent
from termin.visualization.ui.widgets.component import UIComponent
from termin.visualization.ui.widgets.basic import IconButton

if TYPE_CHECKING:
    from termin.visualization.core.viewport import Viewport


class EditorCameraUIController(Component):
    """
    Контроллер UI редакторской камеры.

    Ищет CameraComponent на своей entity или родителях,
    через него получает viewport и доступ к pipeline.passes.
    """

    def __init__(self):
        super().__init__(enabled=True)
        self.active_in_editor = True  # Работает в режиме редактора
        self._ui_component: UIComponent | None = None
        self._camera_component: CameraComponent | None = None

        # Кнопки
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
        self._find_camera_component()
        self._find_ui_component()
        self._bind_buttons()
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
        """Синхронизирует состояние кнопок с текущими настройками."""
        collider_pass = self._find_pass_by_name("ColliderGizmo")
        if collider_pass is not None and self._colliders_btn is not None:
            self._colliders_btn.active = collider_pass.enabled

        color_pass = self._find_pass_by_name("Color")
        if color_pass is not None and self._wireframe_btn is not None:
            self._wireframe_btn.active = color_pass.wireframe

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
        collider_pass = self._find_pass_by_name("ColliderGizmo")
        if collider_pass is not None:
            collider_pass.enabled = not collider_pass.enabled
            if self._colliders_btn is not None:
                self._colliders_btn.active = collider_pass.enabled

    def _on_wireframe_click(self) -> None:
        """Переключает wireframe режим."""
        color_pass = self._find_pass_by_name("Color")
        transparent_pass = self._find_pass_by_name("Transparent")

        self._wireframe_btn.active = not self._wireframe_btn.active
        current_state = self._wireframe_btn.active

        if color_pass is not None:
            color_pass.wireframe = current_state

        if transparent_pass is not None:
            transparent_pass.wireframe = current_state

    def _on_ortho_click(self) -> None:
        """Переключает ортографическую камеру."""
        # TODO: Реализовать переключение проекции камеры
        if self._ortho_btn is not None:
            self._ortho_btn.active = not self._ortho_btn.active
