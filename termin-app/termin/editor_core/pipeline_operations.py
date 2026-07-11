"""PipelineOperations — UI-agnostic mutations on a RenderPipeline.

Holds the currently-edited pipeline reference, exposes pure data methods
(add/remove/move/rename/etc.), and emits ``pipeline_changed`` so views can
re-render. Error messages go through the supplied :class:`DialogService`.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from tcbase import log

from termin.editor_core.dialog_service import DialogService
from termin.editor_core.signal import Signal

if TYPE_CHECKING:
    from termin.render_framework import RenderPipeline
    from termin.render_framework import ResourceSpec


def _set_resource_spec_resource(spec: "ResourceSpec", value: Any) -> None:
    spec.resource = value


def _set_resource_spec_samples(spec: "ResourceSpec", value: Any) -> None:
    spec.samples = value


def _set_resource_spec_format(spec: "ResourceSpec", value: Any) -> None:
    spec.format = value


def _set_resource_spec_clear_color(spec: "ResourceSpec", value: Any) -> None:
    spec.clear_color = value


def _set_resource_spec_clear_depth(spec: "ResourceSpec", value: Any) -> None:
    spec.clear_depth = value


_RESOURCE_SPEC_FIELD_SETTERS = {
    "resource": _set_resource_spec_resource,
    "samples": _set_resource_spec_samples,
    "format": _set_resource_spec_format,
    "clear_color": _set_resource_spec_clear_color,
    "clear_depth": _set_resource_spec_clear_depth,
}


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
        remaining = [candidate for index, candidate in enumerate(passes) if index != from_idx]
        before = remaining[to_idx] if to_idx < len(remaining) else None
        self._pipeline.move_pass_before(p, before)
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
        from termin.render_framework import ResourceSpec
        spec = ResourceSpec(resource=name, resource_type="fbo", format="render_target")
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

        setter = _RESOURCE_SPEC_FIELD_SETTERS.get(field)
        if setter is None:
            log.error(f"[PipelineOperations] unknown resource spec field: {field!r}")
            return False

        try:
            setter(spec, value)
        except TypeError as e:
            log.warn(f"[PipelineOperations] update_spec_field({field!r}) rejected: {e}")
            return False
        self.pipeline_changed.emit()
        return True

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    def load_from_file(self, path: str) -> "RenderPipeline | None":
        from termin.render_framework import RenderPipeline
        from termin.editor_core.resource_manager import ResourceManager
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            pipeline = RenderPipeline.deserialize(data, ResourceManager.instance())
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
