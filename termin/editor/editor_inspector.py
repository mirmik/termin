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
    QInputDialog,
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

        self._push_undo_command: Optional[Callable[[UndoCommand, bool], None]] = None

        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)

    def set_undo_command_handler(
        self, handler: Optional[Callable[[UndoCommand, bool], None]]
    ) -> None:
        self._push_undo_command = handler

    def set_entity(self, ent: Optional[Entity]) -> None:
        self._entity = ent
        # Block signals during list update to prevent spurious selection events
        self._list.blockSignals(True)
        self._list.clear()
        if ent is None:
            self._list.blockSignals(False)
            return
        for ref in ent.tc_components:
            name = self._get_component_display_name_ref(ref)
            item = QListWidgetItem(name)
            self._list.addItem(item)
        # Clear selection after populating
        self._list.setCurrentRow(-1)
        self._list.blockSignals(False)

    def _get_component_display_name_ref(self, ref) -> str:
        """Get display name for component: 'display_name (type_name)' or just 'type_name'."""
        type_name = ref.type_name
        display_name = ref.get_field("display_name")
        if display_name:
            return f"{display_name} ({type_name})"
        return type_name

    def current_component(self) -> Optional[Component]:
        if self._entity is None:
            return None
        row = self._list.currentRow()
        if row < 0 or row >= len(self._entity.components):
            return None
        return self._entity.components[row]

    def current_component_ref(self):
        """Get current component as TcComponentRef."""
        if self._entity is None:
            return None
        row = self._list.currentRow()
        tc_components = self._entity.tc_components
        if row < 0 or row >= len(tc_components):
            return None
        return tc_components[row]

    def _get_component_library(self) -> list[str]:
        from termin.entity import ComponentRegistry
        # Import native modules to trigger static component registration
        import termin._native.render  # noqa: F401 - registers MeshRenderer, etc.
        import termin._native.skeleton  # noqa: F401 - registers SkeletonController
        return ComponentRegistry.instance().list_all()

    def _show_add_component_menu(self) -> None:
        if self._entity is None:
            return

        menu = QMenu(self)
        component_names = self._get_component_library()

        for name in component_names:
            act = QAction(name, self)
            act.triggered.connect(
                lambda _checked=False, n=name: self._add_component(n)
            )
            menu.addAction(act)

        menu.exec(self._add_btn.mapToGlobal(self._add_btn.rect().bottomLeft()))

    def _on_context_menu(self, pos) -> None:
        if self._entity is None:
            return

        global_pos = self._list.mapToGlobal(pos)
        menu = QMenu(self)
        comp = self.current_component()

        # Rename action
        rename_action = QAction("Переименовать", self)
        rename_action.setEnabled(comp is not None)
        rename_action.triggered.connect(self._rename_current_component)
        menu.addAction(rename_action)

        # Remove action
        remove_action = QAction("Удалить компонент", self)
        remove_action.setEnabled(comp is not None)
        remove_action.triggered.connect(self._remove_current_component)
        menu.addAction(remove_action)

        menu.addSeparator()

        component_names = self._get_component_library()

        if component_names:
            add_menu = menu.addMenu("Добавить компонент")
            for name in component_names:
                act = QAction(name, self)
                act.triggered.connect(
                    lambda _checked=False, n=name: self._add_component(n)
                )
                add_menu.addAction(act)

        self._list.blockSignals(True)
        menu.exec(global_pos)
        self._list.blockSignals(False)

    def _rename_current_component(self) -> None:
        if self._entity is None:
            return
        ref = self.current_component_ref()
        if ref is None or not ref.valid:
            return

        # Get current display name
        current_name = ref.get_field("display_name") or ""

        # Show input dialog
        new_name, ok = QInputDialog.getText(
            self,
            "Переименовать компонент",
            "Имя:",
            text=current_name,
        )

        if ok:
            # Set new display name (empty string clears custom name)
            ref.set_field("display_name", new_name.strip())
            # Update list item
            row = self._list.currentRow()
            item = self._list.item(row)
            if item is not None:
                item.setText(self._get_component_display_name_ref(ref))
            self.components_changed.emit()

    def _remove_current_component(self) -> None:
        if self._entity is None:
            return
        ref = self.current_component_ref()
        if ref is None or not ref.valid:
            return

        type_name = ref.type_name

        if self._push_undo_command is not None:
            cmd = RemoveComponentCommand(self._entity, type_name)
            self._push_undo_command(cmd, False)
        else:
            self._entity.remove_component_ref(ref)

        self.set_entity(self._entity)
        self.components_changed.emit()

    def _add_component(self, name: str) -> None:
        if self._entity is None:
            return

        try:
            ref = self._entity.add_component_by_name(name)
        except Exception:
            logger.exception("Failed to create component %s", name)
            return

        # Register undo command (component already added, but undo will remove it)
        if self._push_undo_command is not None:
            cmd = AddComponentCommand(self._entity, name, ref)
            self._push_undo_command(cmd, False)

        self.set_entity(self._entity)

        # Don't auto-select - debugging crash
        self._list.blockSignals(True)
        self._list.setCurrentRow(-1)
        self._list.blockSignals(False)

        # self.components_changed.emit()


class ComponentInspectorPanel(QWidget):
    """
    Panel for editing component fields with undo/redo support.

    Uses InspectFieldPanel internally but wraps field changes with undo commands.
    Also shows MaterialPropertiesEditor for components with override_material.
    """

    component_changed = pyqtSignal()
    # Emitted when a field changes: (component, field_key, new_value)
    field_changed = pyqtSignal(object, str, object)

    def __init__(self, resources: ResourceManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._component: Optional[Component] = None
        self._push_undo_command: Optional[Callable[[UndoCommand, bool], None]] = None
        self._resources = resources

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._panel = InspectFieldPanel(resources, self)
        layout.addWidget(self._panel)

        # Material properties editor (for components with override_material)
        from termin.editor.widgets.material_properties_editor import (
            MaterialPropertiesEditor,
        )

        self._material_props_editor = MaterialPropertiesEditor(self)
        self._material_props_editor.setVisible(False)
        self._material_props_editor.property_changed.connect(
            self._on_material_property_changed
        )
        layout.addWidget(self._material_props_editor)

        self._panel.field_changed.connect(self._on_field_changed)

    def set_undo_command_handler(
        self, handler: Optional[Callable[[UndoCommand, bool], None]]
    ) -> None:
        self._push_undo_command = handler

    def set_scene_getter(self, getter) -> None:
        """Set callback for getting current scene (for layer_mask widget)."""
        self._panel.set_scene_getter(getter)

    def set_component(self, comp: Optional[Component]) -> None:
        self._component = comp
        self._panel.set_target(comp)

        # Update button targets
        if comp is not None:
            for widget in self._panel._widgets.values():
                if isinstance(widget, ButtonFieldWidget):
                    widget.set_target(comp)

        # Update material properties editor visibility
        self._update_material_props_editor()

    def _update_material_props_editor(self) -> None:
        """Update material properties editor visibility and content."""
        from termin._native.render import MeshRenderer  # SkinnedMeshRenderer inherits from this

        if isinstance(self._component, MeshRenderer) and self._component.override_material:
            mat = self._component.get_overridden_material()
            # If override enabled but material not created (e.g. after scene load), recreate it
            if mat is None:
                self._component._override_material = False
                self._component.set_override_material(True)
                mat = self._component.get_overridden_material()
            self._material_props_editor.set_material(mat)
            self._material_props_editor.setVisible(True)
        else:
            self._material_props_editor.setVisible(False)
            self._material_props_editor.set_material(None)

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

        # If override_material changed, call the setter to create/delete the override copy
        if key == "_override_material":
            from termin._native.render import MeshRenderer
            if isinstance(self._component, MeshRenderer):
                # Force setter to run by resetting field first (setter has early-return check)
                self._component._override_material = not new_value
                self._component.set_override_material(new_value)
            self._update_material_props_editor()

        self.field_changed.emit(self._component, key, new_value)
        self.component_changed.emit()

    def _on_material_property_changed(self, name: str, value: Any) -> None:
        """Handle changes from material properties editor."""
        # The material properties editor already applied the change
        # to the overridden material, just emit component_changed
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
    # Emitted when a component field changes: (component, field_key, new_value)
    component_field_changed = pyqtSignal(object, str, object)

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
        self._component_inspector.field_changed.connect(
            self.component_field_changed
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
        self._component_inspector.set_scene_getter(lambda: self._scene)

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
