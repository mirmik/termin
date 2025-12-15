# ===== termin/editor/editor_inspector.py =====
from __future__ import annotations

from typing import Optional, Callable, Any
import logging

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, pyqtSignal

from termin.kinematic.transform import Transform3
from termin.visualization.core.entity import Entity, Component
from termin.visualization.core.resources import ResourceManager
from termin.editor.inspect_field_panel import InspectFieldPanel
from termin.editor.undo_stack import UndoCommand
from termin.editor.widgets.field_widgets import ButtonFieldWidget

from termin.editor.editor_commands import (
    ComponentFieldEditCommand,
    AddComponentCommand,
    RemoveComponentCommand,
)
from termin.editor.transform_inspector import TransformInspector
from termin.editor.entity_inspector import EntityInspector as EntityPropertiesInspector

logger = logging.getLogger(__name__)


class ComponentsPanel(QWidget):
    components_changed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(4)

        # Header with add button
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self._title = QLabel("Components")
        header.addWidget(self._title)
        header.addStretch()

        self._add_btn = QPushButton("+")
        self._add_btn.setFixedSize(24, 24)
        self._add_btn.setToolTip("Add Component")
        self._add_btn.clicked.connect(self._show_add_component_menu)
        header.addWidget(self._add_btn)
        layout.addLayout(header)

        self._list = QListWidget()
        layout.addWidget(self._list)

        self._entity: Optional[Entity] = None
        self._component_library: list[tuple[str, type[Component]]] = []

        self._push_undo_command: Optional[Callable[[UndoCommand, bool], None]] = None

        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)

    def set_undo_command_handler(
        self, handler: Optional[Callable[[UndoCommand, bool], None]]
    ) -> None:
        self._push_undo_command = handler

    def set_entity(self, ent: Optional[Entity]) -> None:
        self._entity = ent
        self._list.clear()
        if ent is None:
            return
        for comp in ent.components:
            name = comp.__class__.__name__
            item = QListWidgetItem(name)
            self._list.addItem(item)

    def set_component_library(self, library: list[tuple[str, type[Component]]]) -> None:
        self._component_library = list(library)

    def current_component(self) -> Optional[Component]:
        if self._entity is None:
            return None
        row = self._list.currentRow()
        if row < 0 or row >= len(self._entity.components):
            return None
        return self._entity.components[row]

    def _get_component_library(self) -> list[tuple[str, type[Component]]]:
        if self._component_library:
            return self._component_library
        manager = ResourceManager.instance()
        return sorted(manager.components.items())

    def _show_add_component_menu(self) -> None:
        if self._entity is None:
            return

        menu = QMenu(self)
        component_library = self._get_component_library()

        for label, cls in component_library:
            act = QAction(label, self)
            act.triggered.connect(
                lambda _checked=False, c=cls: self._add_component(c)
            )
            menu.addAction(act)

        menu.exec(self._add_btn.mapToGlobal(self._add_btn.rect().bottomLeft()))

    def _on_context_menu(self, pos) -> None:
        if self._entity is None:
            return

        global_pos = self._list.mapToGlobal(pos)
        menu = QMenu(self)
        comp = self.current_component()
        remove_action = QAction("Удалить компонент", self)
        remove_action.setEnabled(comp is not None)
        remove_action.triggered.connect(self._remove_current_component)
        menu.addAction(remove_action)

        component_library = self._get_component_library()

        if component_library:
            add_menu = menu.addMenu("Добавить компонент")
            for label, cls in component_library:
                act = QAction(label, self)
                act.triggered.connect(
                    lambda _checked=False, c=cls: self._add_component(c)
                )
                add_menu.addAction(act)

        menu.exec(global_pos)

    def _remove_current_component(self) -> None:
        if self._entity is None:
            return
        comp = self.current_component()
        if comp is None:
            return

        if self._push_undo_command is not None:
            cmd = RemoveComponentCommand(self._entity, comp)
            self._push_undo_command(cmd, False)
        else:
            self._entity.remove_component(comp)

        self.set_entity(self._entity)
        self.components_changed.emit()

    def _add_component(self, comp_cls: type[Component]) -> None:
        if self._entity is None:
            return
        try:
            comp = comp_cls()
        except TypeError:
            logger.exception("Failed to create component %s", comp_cls)
            return

        if self._push_undo_command is not None:
            cmd = AddComponentCommand(self._entity, comp)
            self._push_undo_command(cmd, False)
        else:
            self._entity.add_component(comp)

        self.set_entity(self._entity)

        row = len(self._entity.components) - 1
        if row >= 0:
            self._list.setCurrentRow(row)

        self.components_changed.emit()


class ComponentInspectorPanel(QWidget):
    """
    Panel for editing component fields with undo/redo support.

    Uses InspectFieldPanel internally but wraps field changes with undo commands.
    """

    component_changed = pyqtSignal()

    def __init__(self, resources: ResourceManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._component: Optional[Component] = None
        self._push_undo_command: Optional[Callable[[UndoCommand, bool], None]] = None
        self._resources = resources

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._panel = InspectFieldPanel(resources, self)
        layout.addWidget(self._panel)

        self._panel.field_changed.connect(self._on_field_changed)

    def set_undo_command_handler(
        self, handler: Optional[Callable[[UndoCommand, bool], None]]
    ) -> None:
        self._push_undo_command = handler

    def set_component(self, comp: Optional[Component]) -> None:
        self._component = comp
        self._panel.set_target(comp)

        # Update button targets
        if comp is not None:
            for widget in self._panel._widgets.values():
                if isinstance(widget, ButtonFieldWidget):
                    widget.set_target(comp)

    def _on_field_changed(self, key: str, old_value: Any, new_value: Any) -> None:
        if self._component is None:
            return

        field = self._panel._fields.get(key)
        if field is None:
            return

        if self._push_undo_command is not None:
            # Revert the change made by the panel
            field.set_value(self._component, old_value)
            # Create undo command
            cmd = ComponentFieldEditCommand(
                component=self._component,
                field=field,
                old_value=old_value,
                new_value=new_value,
            )
            self._push_undo_command(cmd, True)

        self.component_changed.emit()


class EntityInspector(QWidget):
    """
    Full inspector for Entity/Transform:
    - EntityPropertiesInspector (name, layer, flags)
    - TransformInspector
    - ComponentsPanel (component list)
    - ComponentInspectorPanel (selected component editor)
    """

    transform_changed = pyqtSignal()
    component_changed = pyqtSignal()

    def __init__(self, resources: ResourceManager, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._resources = resources
        self._scene = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Entity properties (name, layer, flags)
        self._entity_properties_inspector = EntityPropertiesInspector(self)
        layout.addWidget(self._entity_properties_inspector)

        self._transform_inspector = TransformInspector(self)
        layout.addWidget(self._transform_inspector)

        self._components_panel = ComponentsPanel(self)
        layout.addWidget(self._components_panel)

        self._component_inspector = ComponentInspectorPanel(resources, self)
        layout.addWidget(self._component_inspector)

        self._entity: Optional[Entity] = None

        self._entity_properties_inspector.entity_changed.connect(
            self.component_changed
        )
        self._transform_inspector.transform_changed.connect(
            self.transform_changed
        )
        self._components_panel._list.currentRowChanged.connect(
            self._on_component_selected
        )
        self._component_inspector.component_changed.connect(
            self._on_component_changed
        )
        self._components_panel.components_changed.connect(
            self._on_components_changed
        )
        self._undo_command_handler: Optional[Callable[[UndoCommand, bool], None]] = None

    def set_undo_command_handler(
        self, handler: Optional[Callable[[UndoCommand, bool], None]]
    ) -> None:
        self._undo_command_handler = handler
        self._entity_properties_inspector.set_undo_command_handler(handler)
        self._transform_inspector.set_undo_command_handler(handler)
        self._components_panel.set_undo_command_handler(handler)
        self._component_inspector.set_undo_command_handler(handler)

    def set_scene(self, scene) -> None:
        """Set the scene for layer/flag names."""
        self._scene = scene
        self._entity_properties_inspector.set_scene(scene)

    def _on_components_changed(self) -> None:
        ent = self._entity
        self._components_panel.set_entity(ent)

        if ent is not None:
            row = self._components_panel._list.currentRow()
            if 0 <= row < len(ent.components):
                self._component_inspector.set_component(ent.components[row])
            else:
                self._component_inspector.set_component(None)
        else:
            self._component_inspector.set_component(None)

        self.component_changed.emit()

    def set_component_library(self, library: list[tuple[str, type[Component]]]) -> None:
        self._components_panel.set_component_library(library)

    def _on_component_changed(self) -> None:
        self.component_changed.emit()

    def set_target(self, obj: Optional[object]) -> None:
        if isinstance(obj, Entity):
            ent = obj
            trans = obj.transform
        elif isinstance(obj, Transform3):
            trans = obj
            ent = obj.entity
        else:
            ent = None
            trans = None

        self._entity = ent

        self._entity_properties_inspector.set_entity(ent)
        self._transform_inspector.set_target(trans or ent)
        self._components_panel.set_entity(ent)
        self._component_inspector.set_component(None)

    def _on_component_selected(self, row: int) -> None:
        if self._entity is None or row < 0:
            self._component_inspector.set_component(None)
            return
        comp = self._entity.components[row]
        self._component_inspector.set_component(comp)

    def refresh_transform(self) -> None:
        """Refresh TransformInspector values from the current transform."""
        self._transform_inspector._update_from_transform()
