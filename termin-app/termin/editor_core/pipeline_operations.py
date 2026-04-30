"""PipelineOperations — UI-agnostic mutations on a RenderPipeline.

Shared by both Qt and tcgui pipeline inspectors. Holds the currently-edited
pipeline reference, exposes pure data methods (add/remove/move/rename/etc.),
and emits ``pipeline_changed`` so views can re-render. Error messages go
through the supplied :class:`DialogService`.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tcbase import log

from termin.editor_core.dialog_service import DialogService
from termin.editor_core.signal import Signal

if TYPE_CHECKING:
    from termin.visualization.render.framegraph.pipeline import RenderPipeline
    from termin.visualization.render.framegraph.passes.base import RenderFramePass
    from termin.visualization.render.framegraph.resource_spec import ResourceSpec


class PipelineOperations:
    def __init__(self, dialog_service: DialogService):
        self._dialog = dialog_service
        self._pipeline: "RenderPipeline | None" = None

        self.pipeline_changed = Signal()

    @property
    def pipeline(self) -> "RenderPipeline | None":
        return self._pipeline

    def set_pipeline(self, pipeline: "RenderPipeline | None") -> None:
        self._pipeline = pipeline

    # ------------------------------------------------------------------
    # Pass operations
    # ------------------------------------------------------------------

    def add_pass(self, pass_obj, index: int = -1) -> None:
        if self._pipeline is None:
            return
        if index < 0 or index >= len(self._pipeline.passes):
            self._pipeline.add_pass(pass_obj)
        else:
            self._pipeline.insert_pass_before(pass_obj, self._pipeline.passes[index])
        self.pipeline_changed.emit()

    def remove_pass(self, pass_obj) -> None:
        if self._pipeline is None:
            return
        try:
            self._pipeline.remove_pass(pass_obj)
        except Exception as e:
            log.error(f"[PipelineOperations] remove_pass failed: {e}")
            self._dialog.show_error("Remove Pass Failed", str(e))
            return
        self.pipeline_changed.emit()

    def move_pass(self, from_idx: int, to_idx: int) -> None:
        if self._pipeline is None:
            return
        passes = self._pipeline.passes
        if not (0 <= from_idx < len(passes)) or not (0 <= to_idx < len(passes)):
            return
        if from_idx == to_idx:
            return
        p = passes[from_idx]
        self._pipeline.remove_pass(p)
        updated_passes = self._pipeline.passes
        if to_idx >= len(updated_passes):
            self._pipeline.add_pass(p)
        else:
            self._pipeline.insert_pass_before(p, updated_passes[to_idx])
        self.pipeline_changed.emit()

    def set_pass_enabled(self, pass_obj, enabled: bool) -> None:
        pass_obj.enabled = bool(enabled)
        self.pipeline_changed.emit()

    def rename_pass(self, pass_obj, new_name: str) -> bool:
        new_name = new_name.strip() if new_name else ""
        if not new_name:
            return False
        pass_obj.pass_name = new_name
        self.pipeline_changed.emit()
        return True

    # ------------------------------------------------------------------
    # PostEffect operations (on a PostProcessPass)
    # ------------------------------------------------------------------

    def add_effect(self, postprocess_pass, effect_obj) -> None:
        postprocess_pass.effects.append(effect_obj)
        self.pipeline_changed.emit()

    def remove_effect(self, postprocess_pass, effect_idx: int) -> None:
        effects = postprocess_pass.effects
        if not (0 <= effect_idx < len(effects)):
            return
        del effects[effect_idx]
        self.pipeline_changed.emit()

    def move_effect(self, postprocess_pass, from_idx: int, to_idx: int) -> None:
        effects = postprocess_pass.effects
        if not (0 <= from_idx < len(effects)) or not (0 <= to_idx < len(effects)):
            return
        if from_idx == to_idx:
            return
        eff = effects.pop(from_idx)
        effects.insert(to_idx, eff)
        self.pipeline_changed.emit()

    def rename_effect(self, effect_obj, new_name: str) -> bool:
        new_name = new_name.strip() if new_name else ""
        if not new_name:
            return False
        effect_obj.name = new_name
        self.pipeline_changed.emit()
        return True

    # ------------------------------------------------------------------
    # ResourceSpec operations
    # ------------------------------------------------------------------

    def is_resource_name_unique(self, name: str, exclude_idx: int = -1) -> bool:
        if self._pipeline is None:
            return True
        for i, spec in enumerate(self._pipeline.pipeline_specs):
            if i == exclude_idx:
                continue
            if spec.resource == name:
                return False
        return True

    def add_resource_spec(self, name: str) -> "ResourceSpec | None":
        if self._pipeline is None:
            return None
        if not self.is_resource_name_unique(name):
            self._dialog.show_error(
                "Duplicate Resource",
                f"Resource '{name}' already exists in the pipeline.",
            )
            return None
        from termin.visualization.render.framegraph.resource_spec import ResourceSpec
        spec = ResourceSpec(resource=name, resource_type="fbo")
        self._pipeline.pipeline_specs.append(spec)
        self.pipeline_changed.emit()
        return spec

    def remove_resource_spec(self, spec_idx: int) -> None:
        if self._pipeline is None:
            return
        specs = self._pipeline.pipeline_specs
        if not (0 <= spec_idx < len(specs)):
            return
        del specs[spec_idx]
        self.pipeline_changed.emit()

    def update_spec_field(self, spec, field: str, value) -> bool:
        """Update a single field on a resource spec. Returns True on success.

        Validates uniqueness for ``resource`` (name) field. Safely handles
        None for ``clear_color`` / ``clear_depth`` where C++ bindings
        don't accept None and would raise TypeError.
        """
        if field == "resource":
            idx = -1
            if self._pipeline is not None:
                for i, s in enumerate(self._pipeline.pipeline_specs):
                    if s is spec:
                        idx = i
                        break
            if not self.is_resource_name_unique(value, exclude_idx=idx):
                self._dialog.show_error(
                    "Duplicate Resource",
                    f"Resource '{value}' already exists in the pipeline.",
                )
                return False

        try:
            setattr(spec, field, value)
        except TypeError as e:
            log.warn(f"[PipelineOperations] update_spec_field({field!r}) rejected: {e}")
            return False
        self.pipeline_changed.emit()
        return True

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    def load_from_file(self, path: str) -> "RenderPipeline | None":
        from termin.visualization.render.framegraph.pipeline import RenderPipeline
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            pipeline = RenderPipeline.deserialize(data)
        except Exception as e:
            log.error(f"[PipelineOperations] load_from_file failed: {e}")
            self._dialog.show_error("Load Pipeline Failed", str(e))
            return None
        return pipeline

    def save_to_file(self, path: str) -> bool:
        if self._pipeline is None:
            self._dialog.show_error("Save Pipeline Failed", "No pipeline loaded.")
            return False
        try:
            data = self._pipeline.serialize()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"[PipelineOperations] save_to_file failed: {e}")
            self._dialog.show_error("Save Pipeline Failed", str(e))
            return False
        return True
