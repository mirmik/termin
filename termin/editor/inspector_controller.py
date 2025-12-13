"""
Controller for managing inspector panels in the editor.

Handles switching between EntityInspector, MaterialInspector,
DisplayInspector, and ViewportInspector.
Synchronizes inspector state with selection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, List, Optional

from PyQt6.QtWidgets import QStackedWidget, QVBoxLayout

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget
    from termin.visualization.core.entity import Entity
    from termin.visualization.core.resources import ResourceManager
    from termin.visualization.core.display import Display
    from termin.visualization.core.viewport import Viewport
    from termin.visualization.core.scene import Scene
    from termin.editor.editor_inspector import EntityInspector
    from termin.editor.material_inspector import MaterialInspector
    from termin.editor.display_inspector import DisplayInspector
    from termin.editor.viewport_inspector import ViewportInspector
    from termin.editor.pipeline_inspector import PipelineInspector
    from termin.editor.texture_inspector import TextureInspector
    from termin.editor.mesh_inspector import MeshInspector


class InspectorController:
    """
    Manages inspector panels and their switching.

    Handles:
    - Switching between EntityInspector, MaterialInspector,
      DisplayInspector, and ViewportInspector
    - Loading entities/materials/displays/viewports into inspectors
    - Syncing inspector with selection state
    """

    ENTITY_INSPECTOR_INDEX = 0
    MATERIAL_INSPECTOR_INDEX = 1
    DISPLAY_INSPECTOR_INDEX = 2
    VIEWPORT_INSPECTOR_INDEX = 3
    PIPELINE_INSPECTOR_INDEX = 4
    TEXTURE_INSPECTOR_INDEX = 5
    MESH_INSPECTOR_INDEX = 6

    def __init__(
        self,
        container: "QWidget",
        resource_manager: "ResourceManager",
        push_undo_command: Callable,
        on_transform_changed: Callable,
        on_component_changed: Callable,
        on_material_changed: Callable,
        on_display_changed: Optional[Callable] = None,
        on_viewport_changed: Optional[Callable] = None,
        on_pipeline_changed: Optional[Callable] = None,
    ):
        self._resource_manager = resource_manager
        self._push_undo_command = push_undo_command
        self._on_display_changed = on_display_changed
        self._on_viewport_changed = on_viewport_changed
        self._on_pipeline_changed = on_pipeline_changed

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

        # Create DisplayInspector
        from termin.editor.display_inspector import DisplayInspector

        self._display_inspector = DisplayInspector()
        if on_display_changed is not None:
            self._display_inspector.display_changed.connect(on_display_changed)
        self._stack.addWidget(self._display_inspector)

        # Create ViewportInspector
        from termin.editor.viewport_inspector import ViewportInspector

        self._viewport_inspector = ViewportInspector()
        if on_viewport_changed is not None:
            self._viewport_inspector.viewport_changed.connect(on_viewport_changed)
        self._stack.addWidget(self._viewport_inspector)

        # Create PipelineInspector
        from termin.editor.pipeline_inspector import PipelineInspector

        self._pipeline_inspector = PipelineInspector()
        if on_pipeline_changed is not None:
            self._pipeline_inspector.pipeline_changed.connect(on_pipeline_changed)
        self._stack.addWidget(self._pipeline_inspector)

        # Create TextureInspector
        from termin.editor.texture_inspector import TextureInspector

        self._texture_inspector = TextureInspector()
        self._stack.addWidget(self._texture_inspector)

        # Create MeshInspector
        from termin.editor.mesh_inspector import MeshInspector

        self._mesh_inspector = MeshInspector()
        self._stack.addWidget(self._mesh_inspector)

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
    def display_inspector(self) -> "DisplayInspector":
        """Access to DisplayInspector widget."""
        return self._display_inspector

    @property
    def viewport_inspector(self) -> "ViewportInspector":
        """Access to ViewportInspector widget."""
        return self._viewport_inspector

    @property
    def pipeline_inspector(self) -> "PipelineInspector":
        """Access to PipelineInspector widget."""
        return self._pipeline_inspector

    @property
    def texture_inspector(self) -> "TextureInspector":
        """Access to TextureInspector widget."""
        return self._texture_inspector

    @property
    def mesh_inspector(self) -> "MeshInspector":
        """Access to MeshInspector widget."""
        return self._mesh_inspector

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

    def show_display_inspector(
        self,
        display: "Display | None" = None,
        name: str = ""
    ) -> None:
        """Show DisplayInspector and set target display."""
        self._stack.setCurrentIndex(self.DISPLAY_INSPECTOR_INDEX)
        self._display_inspector.set_display(display, name)

    def show_viewport_inspector(
        self,
        viewport: "Viewport | None" = None,
        displays: Optional[List["Display"]] = None,
        display_names: Optional[dict[int, str]] = None,
        scene: "Scene | None" = None,
    ) -> None:
        """
        Show ViewportInspector and set target viewport.

        Args:
            viewport: Viewport to inspect.
            displays: Available displays for selection.
            display_names: Optional display names mapping.
            scene: Scene to find cameras from.
        """
        self._stack.setCurrentIndex(self.VIEWPORT_INSPECTOR_INDEX)
        if displays is not None:
            self._viewport_inspector.set_displays(displays, display_names)
        if scene is not None:
            self._viewport_inspector.set_scene(scene)
        self._viewport_inspector.set_viewport(viewport)

    def show_pipeline_inspector_for_file(self, file_path: str) -> None:
        """Show PipelineInspector and load pipeline from file."""
        self._stack.setCurrentIndex(self.PIPELINE_INSPECTOR_INDEX)
        self._pipeline_inspector.load_pipeline_file(file_path)

    def show_texture_inspector(self, texture_name: str | None = None) -> None:
        """Show TextureInspector and load texture by name."""
        self._stack.setCurrentIndex(self.TEXTURE_INSPECTOR_INDEX)
        if texture_name is not None:
            texture = self._resource_manager.get_texture(texture_name)
            if texture is not None:
                self._texture_inspector.set_texture(texture, texture_name)

    def show_texture_inspector_for_file(self, file_path: str) -> None:
        """Show TextureInspector and load texture from file."""
        self._stack.setCurrentIndex(self.TEXTURE_INSPECTOR_INDEX)
        self._texture_inspector.set_texture_by_path(file_path)

    def show_mesh_inspector(self, mesh_name: str | None = None) -> None:
        """Show MeshInspector and load mesh by name."""
        self._stack.setCurrentIndex(self.MESH_INSPECTOR_INDEX)
        if mesh_name is not None:
            mesh = self._resource_manager.get_mesh(mesh_name)
            if mesh is not None:
                self._mesh_inspector.set_mesh(mesh, mesh_name)

    def show_mesh_inspector_for_file(self, file_path: str) -> None:
        """Show MeshInspector and load mesh from file."""
        self._stack.setCurrentIndex(self.MESH_INSPECTOR_INDEX)
        self._mesh_inspector.set_mesh_by_path(file_path)

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
