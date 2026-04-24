"""InspectorModel — UI-agnostic state for the inspector panel.

Holds the currently active inspector kind and its target. Views subscribe
to ``changed`` and translate the model snapshot into their own widget
stack.

Resource resolution (name → material, name → mesh, etc.) lives here so
both Qt and tcgui controllers dispatch identically. File-path variants
don't pre-load: they attach ``file_path`` to ``extras`` and let the view
do the actual loading via its panel, since Qt and tcgui panels expose
different loader methods.
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from termin.editor_core.signal import Signal


class InspectorKind(Enum):
    ENTITY = "entity"
    MATERIAL = "material"
    DISPLAY = "display"
    VIEWPORT = "viewport"
    PIPELINE = "pipeline"
    TEXTURE = "texture"
    MESH = "mesh"
    GLB = "glb"
    RENDER_TARGET = "render_target"


class InspectorModel:
    kind: InspectorKind
    target: Any
    label: str
    extras: dict

    def __init__(self, resource_manager):
        self._rm = resource_manager
        self._scene = None

        self.kind = InspectorKind.ENTITY
        self.target = None
        self.label = ""
        self.extras = {}

        self.changed = Signal()
        self.scene_changed = Signal()

    @property
    def scene(self):
        return self._scene

    def set_scene(self, scene) -> None:
        self._scene = scene
        self.scene_changed.emit(scene)

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def request(
        self,
        kind: InspectorKind,
        target: Any = None,
        label: str = "",
        **extras,
    ) -> None:
        self.kind = kind
        self.target = target
        self.label = label
        self.extras = extras
        self.changed.emit(self)

    # ------------------------------------------------------------------
    # Show helpers — resolve the target and emit a matching request
    # ------------------------------------------------------------------

    def show_entity(self, entity) -> None:
        label = getattr(entity, "name", "") or "" if entity is not None else ""
        self.request(InspectorKind.ENTITY, target=entity, label=label)

    def show_material(self, name: str | None) -> None:
        if name is None:
            self.request(InspectorKind.MATERIAL, target=None, label="")
            return
        material = self._rm.get_material(name)
        self.request(InspectorKind.MATERIAL, target=material, label=name)

    def show_material_for_file(self, file_path: str) -> None:
        name = Path(file_path).stem
        material = self._rm.get_material(name)
        self.request(
            InspectorKind.MATERIAL,
            target=material,
            label=file_path,
            file_path=file_path,
        )

    def show_texture(self, name: str | None) -> None:
        if name is None:
            self.request(InspectorKind.TEXTURE, target=None, label="")
            return
        texture = self._rm.get_texture(name)
        self.request(InspectorKind.TEXTURE, target=texture, label=name)

    def show_texture_for_file(self, file_path: str) -> None:
        self.request(
            InspectorKind.TEXTURE,
            target=None,
            label=file_path,
            file_path=file_path,
        )

    def show_mesh(self, name: str | None) -> None:
        if name is None:
            self.request(InspectorKind.MESH, target=None, label="")
            return
        mesh = self._rm.get_mesh_asset(name)
        self.request(InspectorKind.MESH, target=mesh, label=name)

    def show_mesh_for_file(self, file_path: str) -> None:
        self.request(
            InspectorKind.MESH,
            target=None,
            label=file_path,
            file_path=file_path,
        )

    def show_glb_for_file(self, file_path: str) -> None:
        name = Path(file_path).stem
        glb_asset = self._rm.get_glb_asset(name)
        self.request(
            InspectorKind.GLB,
            target=glb_asset,
            label=file_path,
            file_path=file_path,
        )

    def show_pipeline_for_file(self, file_path: str) -> None:
        name = Path(file_path).stem
        asset = self._rm.get_pipeline_asset(name)
        pipeline = asset.data if asset is not None else None
        self.request(
            InspectorKind.PIPELINE,
            target=pipeline,
            label=file_path,
            file_path=file_path,
        )

    def show_display(self, display, name: str = "") -> None:
        self.request(InspectorKind.DISPLAY, target=display, label=name)

    def show_viewport(
        self,
        viewport,
        displays=None,
        display_names=None,
        current_display=None,
    ) -> None:
        self.request(
            InspectorKind.VIEWPORT,
            target=viewport,
            label="",
            displays=displays,
            display_names=display_names,
            current_display=current_display,
        )

    def show_render_target(self, render_target) -> None:
        self.request(InspectorKind.RENDER_TARGET, target=render_target, label="")

    # ------------------------------------------------------------------
    # Selection-driven dispatch
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Reset to empty entity inspector."""
        self.request(InspectorKind.ENTITY, target=None, label="")

    def resync_from_selection(self, obj) -> None:
        """Route a tree selection to the right inspector.

        Entity or None → entity inspector with that target. Any other
        object (Transform3, etc.) is still handed to the entity inspector
        since it's the generic target widget.
        """
        from termin.visualization.core.entity import Entity

        if isinstance(obj, Entity):
            self.show_entity(obj)
        else:
            self.request(InspectorKind.ENTITY, target=obj, label="")
