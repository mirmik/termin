"""Headless framegraph debugger access for editor automation."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from tcbase import log


class EditorFramegraphDebuggerService:
    """Expose FramegraphDebuggerModel state without requiring its tcgui dialog."""

    def __init__(
        self,
        *,
        get_rendering_controller: Callable[[], object | None],
        on_request_update: Callable[[], None] | None = None,
    ) -> None:
        self._get_rendering_controller = get_rendering_controller
        self._on_request_update = on_request_update
        self._model = None
        self._core = None

    @property
    def model(self):
        return self._ensure_model()

    @property
    def core(self):
        self._ensure_model()
        return self._core

    def refresh(self) -> None:
        self._ensure_model().refresh_viewports()

    def inspect(
        self,
        *,
        target_index: int | None = None,
        include_pass_json: bool = False,
        include_debugger_pass: bool = False,
    ) -> dict[str, object]:
        """Return a JSON-serializable framegraph state snapshot."""
        model = self._ensure_model()
        model.refresh_viewports()
        if target_index is not None:
            model.set_viewport_by_index(int(target_index))

        pipeline = model.get_current_pipeline()
        targets = model.targets
        current_target = model.current_viewport
        current_target_index = _index_of_target_source(targets, current_target)
        resources = list(model.get_resources())
        passes = _pass_details(
            pipeline,
            include_debugger_pass=include_debugger_pass,
            include_pass_json=include_pass_json,
        )
        schedule = _schedule_details(
            model,
            exclude_debugger=not include_debugger_pass,
        )

        return {
            "targets": [
                _target_summary(index, target)
                for index, target in enumerate(targets)
            ],
            "current_target_index": current_target_index,
            "current_target_label": (
                targets[current_target_index].label
                if current_target_index is not None else None
            ),
            "mode": model.mode,
            "selected_pass": model.selected_pass,
            "selected_symbol": model.selected_symbol,
            "debug_source_resource": model.debug_source_res,
            "resources": resources,
            "passes": passes,
            "duplicate_pass_names": _duplicate_pass_names(passes),
            "schedule": schedule,
            "fbo_keys": sorted(model.get_fbos().keys()),
            "pipeline_info_html": model.format_pipeline_info(),
            "render_stats": model.format_render_stats(),
            "capture": _capture_summary(model),
        }

    def disconnect(self) -> None:
        if self._model is not None:
            self._model.disconnect()

    def _ensure_model(self):
        if self._model is not None:
            return self._model

        rendering_controller = self._get_rendering_controller()
        if rendering_controller is None:
            raise RuntimeError("Rendering controller is not available")

        from termin._native.editor import FrameGraphDebuggerCore
        from termin.editor_core.framegraph_debugger_model import FramegraphDebuggerModel

        self._core = FrameGraphDebuggerCore()
        self._model = FramegraphDebuggerModel(
            rendering_controller=rendering_controller,
            core=self._core,
            on_request_update=self._on_request_update,
        )
        log.info("[FramegraphDebuggerService] headless debugger model created")
        return self._model


def _index_of_target_source(targets: list[object], source: object | None) -> int | None:
    if source is None:
        return None
    for index, target in enumerate(targets):
        if target.source is source:
            return index
    return None


def _target_summary(index: int, target: object) -> dict[str, object]:
    source = target.source
    return {
        "index": index,
        "label": target.label,
        "source_type": type(source).__name__,
    }


def _pass_details(
    pipeline: object | None,
    *,
    include_debugger_pass: bool,
    include_pass_json: bool,
) -> list[dict[str, object]]:
    if pipeline is None:
        return []

    result: list[dict[str, object]] = []
    for pass_index, frame_pass in enumerate(pipeline.passes):
        pass_name = frame_pass.pass_name
        if pass_name == "FrameDebugger" and not include_debugger_pass:
            continue
        symbols = list(frame_pass.get_internal_symbols())
        reads, read_error = _pass_resource_set(frame_pass, "reads")
        writes, write_error = _pass_resource_set(frame_pass, "writes")
        item: dict[str, object] = {
            "index": pass_index,
            "name": pass_name,
            "type": frame_pass.type_name,
            "reads": reads,
            "writes": writes,
            "internal_symbols": symbols,
            "has_internal_symbols": bool(symbols),
        }
        if read_error is not None:
            item["read_error"] = read_error
        if write_error is not None:
            item["write_error"] = write_error
        if include_pass_json:
            try:
                item["serialized"] = frame_pass.serialize()
            except Exception as exc:
                item["serialize_error"] = f"{type(exc).__name__}: {exc}"
        result.append(item)
    return result


def _duplicate_pass_names(passes: list[dict[str, object]]) -> list[dict[str, object]]:
    indices_by_name: dict[str, list[int]] = {}
    for item in passes:
        name = str(item["name"])
        index = int(item["index"])
        indices_by_name.setdefault(name, []).append(index)
    return [
        {"name": name, "indices": indices}
        for name, indices in sorted(indices_by_name.items())
        if len(indices) > 1
    ]


def _schedule_details(
    model: object,
    *,
    exclude_debugger: bool,
) -> list[dict[str, object]]:
    try:
        scheduled = model._build_schedule(exclude_debugger=exclude_debugger)
    except Exception as exc:
        return [{"error": f"{type(exc).__name__}: {exc}"}]

    result: list[dict[str, object]] = []
    for item in scheduled:
        result.append(
            {
                "name": item.pass_name,
                "reads": _sorted_strings(item.reads),
                "writes": _sorted_strings(item.writes),
            }
        )
    return result


def _capture_summary(model: object) -> dict[str, object]:
    capture = model.core.capture
    has_capture = bool(capture.has_capture())
    result: dict[str, object] = {
        "has_capture": has_capture,
    }
    if has_capture:
        result.update(
            {
                "width": int(capture.width),
                "height": int(capture.height),
                "is_depth": bool(capture.is_depth),
                "format": int(capture.format),
            }
        )
    return result


def _sorted_strings(values: object) -> list[str]:
    try:
        return sorted(str(value) for value in values)
    except TypeError:
        return [str(values)]


def _pass_resource_set(
    frame_pass: object,
    attr_name: str,
) -> tuple[list[str], str | None]:
    try:
        if attr_name == "reads":
            values = frame_pass.reads
        elif attr_name == "writes":
            values = frame_pass.writes
        else:
            raise ValueError(f"Unsupported pass resource set: {attr_name}")
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"
    return _sorted_strings(values), None


def pretty_json(data: object) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)
