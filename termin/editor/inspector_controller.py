"""
Controller for managing inspector panels in the editor.

Handles switching between EntityInspector and MaterialInspector,
and synchronizes inspector state with selection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from PyQt6.QtWidgets import QStackedWidget, QVBoxLayout

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget
    from termin.visualization.core.entity import Entity
    from termin.visualization.core.resources import ResourceManager
    from termin.editor.editor_inspector import EntityInspector
    from termin.editor.material_inspector import MaterialInspector


class InspectorController:
    """
    Manages inspector panels and their switching.

    Handles:
    - Switching between EntityInspector and MaterialInspector
    - Loading entities/materials into inspectors
    - Syncing inspector with selection state
    """

    ENTITY_INSPECTOR_INDEX = 0
    MATERIAL_INSPECTOR_INDEX = 1

    def __init__(
        self,
        container: "QWidget",
        resource_manager: "ResourceManager",
        push_undo_command: Callable,
        on_transform_changed: Callable,
        on_component_changed: Callable,
        on_material_changed: Callable,
    ):
        self._resource_manager = resource_manager
        self._push_undo_command = push_undo_command

        # Create stack widget
        self._stack = QStackedWidget()

        # Create EntityInspector
        from termin.editor.editor_inspector import EntityInspector

        self._entity_inspector = EntityInspector(resource_manager)
        self._entity_inspector.transform_changed.connect(on_transform_changed)
        self._entity_inspector.component_changed.connect(on_component_changed)
        self._entity_inspector.set_undo_command_handler(push_undo_command)
        self._stack.addWidget(self._entity_inspector)

        # Create MaterialInspector
        from termin.editor.material_inspector import MaterialInspector

        self._material_inspector = MaterialInspector()
        self._material_inspector.material_changed.connect(on_material_changed)
        self._stack.addWidget(self._material_inspector)

        # Add to container
        self._init_in_container(container)

    def _init_in_container(self, container: "QWidget") -> None:
        """Initialize inspector stack in the container widget."""
        layout = container.layout()
        if layout is None:
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            container.setLayout(layout)
        layout.addWidget(self._stack)

    @property
    def entity_inspector(self) -> "EntityInspector":
        """Access to EntityInspector widget."""
        return self._entity_inspector

    @property
    def material_inspector(self) -> "MaterialInspector":
        """Access to MaterialInspector widget."""
        return self._material_inspector

    @property
    def stack(self) -> QStackedWidget:
        """Access to the stack widget."""
        return self._stack

    def show_entity_inspector(self, entity: "Entity | None" = None) -> None:
        """Show EntityInspector and optionally set target entity."""
        self._stack.setCurrentIndex(self.ENTITY_INSPECTOR_INDEX)
        if entity is not None:
            self._entity_inspector.set_target(entity)

    def show_material_inspector(self, material_name: str | None = None) -> None:
        """Show MaterialInspector and load material by name."""
        self._stack.setCurrentIndex(self.MATERIAL_INSPECTOR_INDEX)
        if material_name is not None:
            mat = self._resource_manager.get_material(material_name)
            if mat is not None:
                self._material_inspector.set_material(mat)
                shader = self._resource_manager.get_shader(mat.shader_name)
                if shader is not None:
                    self._material_inspector._shader_program = shader
                    self._material_inspector._rebuild_ui()

    def show_material_inspector_for_file(self, file_path: str) -> None:
        """Show MaterialInspector and load material from file."""
        self._stack.setCurrentIndex(self.MATERIAL_INSPECTOR_INDEX)
        self._material_inspector.load_material_file(file_path)

    def set_entity_target(self, target) -> None:
        """Set target for EntityInspector (can be Entity or other object)."""
        self._entity_inspector.set_target(target)

    def clear(self) -> None:
        """Clear inspector state."""
        self._entity_inspector.set_target(None)
        self._stack.setCurrentIndex(self.ENTITY_INSPECTOR_INDEX)

    def resync_from_tree_selection(self, tree_view, scene) -> None:
        """
        Resync inspector based on current tree selection.

        Args:
            tree_view: QTreeView with scene tree
            scene: Current scene
        """
        from termin.visualization.core.entity import Entity

        index = tree_view.currentIndex()
        if not index.isValid():
            self.show_entity_inspector(None)
            return

        node = index.internalPointer()
        obj = node.obj if node is not None else None

        if isinstance(obj, Entity):
            self.show_entity_inspector(obj)
        else:
            self._entity_inspector.set_target(obj)
            self._stack.setCurrentIndex(self.ENTITY_INSPECTOR_INDEX)
