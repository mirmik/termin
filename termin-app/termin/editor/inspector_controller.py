"""Inspector controller for the Qt editor.

State (which inspector kind is active, what the target is) lives in
:class:`termin.editor_core.inspector_model.InspectorModel`. This controller
owns the widgets and reacts to model changes by switching the stack and
calling the appropriate panel loader.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable, List, Optional

from PyQt6.QtWidgets import QStackedWidget, QVBoxLayout

from termin.editor_core.inspector_model import InspectorKind, InspectorModel

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget
    from termin.visualization.core.entity import Entity
    from termin.visualization.core.resources import ResourceManager
    from termin.visualization.core.display import Display
    from termin.visualization.core.viewport import Viewport
    from termin.visualization.core.scene import Scene
    from termin.visualization.platform.backends.sdl_embedded import SDLEmbeddedWindowBackend
    from termin.editor.editor_inspector import EntityInspector
    from termin.editor.material_inspector import MaterialInspector
    from termin.editor.display_inspector import DisplayInspector
    from termin.editor.viewport_inspector import ViewportInspector
    from termin.editor.pipeline_inspector import PipelineInspector
    from termin.editor.texture_inspector import TextureInspector
    from termin.editor.mesh_inspector import MeshInspector
    from termin.editor.glb_inspector import GLBInspector
    from termin.editor.render_target_inspector import RenderTargetInspector


_KIND_INDEX = {
    InspectorKind.ENTITY: 0,
    InspectorKind.MATERIAL: 1,
    InspectorKind.DISPLAY: 2,
    InspectorKind.VIEWPORT: 3,
    InspectorKind.PIPELINE: 4,
    InspectorKind.TEXTURE: 5,
    InspectorKind.MESH: 6,
    InspectorKind.GLB: 7,
    InspectorKind.RENDER_TARGET: 8,
}


class InspectorController:
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
        window_backend: Optional["SDLEmbeddedWindowBackend"] = None,
    ):
        self._resource_manager = resource_manager
        self._push_undo_command = push_undo_command
        self._on_display_changed = on_display_changed
        self._on_viewport_changed = on_viewport_changed
        self._on_pipeline_changed = on_pipeline_changed
        self._window_backend = window_backend

        self._model = InspectorModel(resource_manager)

        self._stack = QStackedWidget()

        from termin.editor.editor_inspector import EntityInspector
        self._entity_inspector = EntityInspector(resource_manager)
        self._entity_inspector.transform_changed.connect(on_transform_changed)
        self._entity_inspector.component_changed.connect(on_component_changed)
        self._entity_inspector.set_undo_command_handler(push_undo_command)
        self._stack.addWidget(self._entity_inspector)

        from termin.editor.material_inspector import MaterialInspector
        self._material_inspector = MaterialInspector()
        self._material_inspector.material_changed.connect(on_material_changed)
        self._stack.addWidget(self._material_inspector)

        from termin.editor.display_inspector import DisplayInspector
        self._display_inspector = DisplayInspector()
        if on_display_changed is not None:
            self._display_inspector.display_changed.connect(on_display_changed)
        self._stack.addWidget(self._display_inspector)

        from termin.editor.viewport_inspector import ViewportInspector
        self._viewport_inspector = ViewportInspector()
        if on_viewport_changed is not None:
            self._viewport_inspector.viewport_changed.connect(on_viewport_changed)
        self._stack.addWidget(self._viewport_inspector)

        from termin.editor.pipeline_inspector import PipelineInspector
        self._pipeline_inspector = PipelineInspector()
        if on_pipeline_changed is not None:
            self._pipeline_inspector.pipeline_changed.connect(on_pipeline_changed)
        self._stack.addWidget(self._pipeline_inspector)

        from termin.editor.texture_inspector import TextureInspector
        self._texture_inspector = TextureInspector()
        self._stack.addWidget(self._texture_inspector)

        from termin.editor.mesh_inspector import MeshInspector
        self._mesh_inspector = MeshInspector(window_backend=self._window_backend)
        self._stack.addWidget(self._mesh_inspector)

        from termin.editor.glb_inspector import GLBInspector
        self._glb_inspector = GLBInspector()
        self._stack.addWidget(self._glb_inspector)

        from termin.editor.render_target_inspector import RenderTargetInspector
        self._render_target_inspector = RenderTargetInspector()
        self._stack.addWidget(self._render_target_inspector)

        self._init_in_container(container)

        self._model.changed.connect(self._on_model_changed)

    def _init_in_container(self, container: "QWidget") -> None:
        layout = container.layout()
        if layout is None:
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            container.setLayout(layout)
        layout.addWidget(self._stack)

    # ------------------------------------------------------------------
    # Public widget accessors (unchanged for external callers)
    # ------------------------------------------------------------------

    @property
    def entity_inspector(self) -> "EntityInspector":
        return self._entity_inspector

    @property
    def material_inspector(self) -> "MaterialInspector":
        return self._material_inspector

    @property
    def display_inspector(self) -> "DisplayInspector":
        return self._display_inspector

    @property
    def viewport_inspector(self) -> "ViewportInspector":
        return self._viewport_inspector

    @property
    def pipeline_inspector(self) -> "PipelineInspector":
        return self._pipeline_inspector

    @property
    def texture_inspector(self) -> "TextureInspector":
        return self._texture_inspector

    @property
    def mesh_inspector(self) -> "MeshInspector":
        return self._mesh_inspector

    @property
    def glb_inspector(self) -> "GLBInspector":
        return self._glb_inspector

    @property
    def render_target_inspector(self) -> "RenderTargetInspector":
        return self._render_target_inspector

    @property
    def stack(self) -> QStackedWidget:
        return self._stack

    @property
    def model(self) -> InspectorModel:
        return self._model

    # ------------------------------------------------------------------
    # External API — thin wrappers around InspectorModel
    # ------------------------------------------------------------------

    def set_scene(self, scene: "Scene | None") -> None:
        self._model.set_scene(scene)
        self._entity_inspector.set_scene(scene)

    def show_entity_inspector(self, entity: "Entity | None" = None) -> None:
        self._model.show_entity(entity)

    def show_material_inspector(self, material_name: str | None = None) -> None:
        self._model.show_material(material_name)

    def show_material_inspector_for_file(self, file_path: str) -> None:
        self._model.show_material_for_file(file_path)

    def show_display_inspector(
        self,
        display: "Display | None" = None,
        name: str = "",
    ) -> None:
        self._model.show_display(display, name)

    def show_viewport_inspector(
        self,
        viewport: "Viewport | None" = None,
        displays: Optional[List["Display"]] = None,
        display_names: Optional[dict[int, str]] = None,
        scene: "Scene | None" = None,
        current_display: "Display | None" = None,
    ) -> None:
        if scene is not None and scene is not self._model.scene:
            self._model.set_scene(scene)
        self._model.show_viewport(
            viewport,
            displays=displays,
            display_names=display_names,
            current_display=current_display,
        )

    def show_render_target_inspector(
        self,
        render_target=None,
        scene: "Scene | None" = None,
    ) -> None:
        if scene is not None and scene is not self._model.scene:
            self._model.set_scene(scene)
        self._model.show_render_target(render_target)

    def show_pipeline_inspector_for_file(self, file_path: str) -> None:
        self._model.show_pipeline_for_file(file_path)

    def show_texture_inspector(self, texture_name: str | None = None) -> None:
        self._model.show_texture(texture_name)

    def show_texture_inspector_for_file(self, file_path: str) -> None:
        self._model.show_texture_for_file(file_path)

    def show_mesh_inspector(self, mesh_name: str | None = None) -> None:
        self._model.show_mesh(mesh_name)

    def show_mesh_inspector_for_file(self, file_path: str) -> None:
        self._model.show_mesh_for_file(file_path)

    def show_glb_inspector_for_file(self, file_path: str) -> None:
        self._model.show_glb_for_file(file_path)

    def set_entity_target(self, target) -> None:
        """Deprecated shortcut: show entity inspector with any object as target."""
        self._model.request(InspectorKind.ENTITY, target=target, label="")

    def clear(self) -> None:
        self._model.clear()

    def resync_from_tree_selection(self, tree_view, scene) -> None:
        """Resync inspector based on current tree selection."""
        index = tree_view.currentIndex()
        obj = None
        if index.isValid():
            node = index.internalPointer()
            obj = node.obj if node is not None else None
        self._model.resync_from_selection(obj)

    # ------------------------------------------------------------------
    # Model → view
    # ------------------------------------------------------------------

    def _on_model_changed(self, model: InspectorModel) -> None:
        kind = model.kind
        self._stack.setCurrentIndex(_KIND_INDEX[kind])

        file_path = model.extras.get("file_path")

        if kind is InspectorKind.ENTITY:
            self._entity_inspector.set_target(model.target)

        elif kind is InspectorKind.MATERIAL:
            if file_path is not None:
                self._material_inspector.load_material_file(file_path)
            elif model.target is not None:
                self._material_inspector.set_material(model.target)
                shader = self._resource_manager.get_shader(model.target.shader_name)
                if shader is not None:
                    self._material_inspector._shader_program = shader
                    self._material_inspector._rebuild_ui()

        elif kind is InspectorKind.DISPLAY:
            self._display_inspector.set_display(model.target, model.label)

        elif kind is InspectorKind.VIEWPORT:
            displays = model.extras.get("displays")
            display_names = model.extras.get("display_names")
            if displays is not None:
                self._viewport_inspector.set_displays(displays, display_names)
            if model.scene is not None:
                self._viewport_inspector.set_scene(model.scene)
            self._viewport_inspector.set_viewport(
                model.target, model.extras.get("current_display")
            )

        elif kind is InspectorKind.PIPELINE:
            if file_path is not None:
                self._pipeline_inspector.load_pipeline_file(file_path)

        elif kind is InspectorKind.TEXTURE:
            if file_path is not None:
                self._texture_inspector.set_texture_by_path(file_path)
            elif model.target is not None:
                self._texture_inspector.set_texture(model.target, model.label)

        elif kind is InspectorKind.MESH:
            if file_path is not None:
                self._mesh_inspector.set_mesh_by_path(file_path)
            elif model.target is not None:
                self._mesh_inspector.set_mesh(model.target, model.label)

        elif kind is InspectorKind.GLB:
            if file_path is not None:
                self._glb_inspector.set_glb_by_path(file_path)

        elif kind is InspectorKind.RENDER_TARGET:
            self._render_target_inspector.set_render_target(model.target, model.scene)
