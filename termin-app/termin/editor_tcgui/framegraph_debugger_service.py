"""Headless framegraph debugger access for editor automation."""

from __future__ import annotations

import base64
import json
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
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
            "selected_pass_index": model.selected_pass_index,
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

    def prepare_resource_capture(
        self,
        *,
        target_index: int | None = None,
        resource_name: str | None = None,
        channel_mode: int = 0,
        highlight_hdr: bool = False,
    ) -> dict[str, object]:
        """Connect the debugger pass so a following render frame captures a resource."""
        model = self._ensure_model()
        model.refresh_viewports()
        if target_index is not None:
            model.set_viewport_by_index(int(target_index))

        resources = list(model.get_resources())
        if not resources:
            raise RuntimeError("Current framegraph target has no capturable resources")
        selected_resource = resource_name or resources[0]
        if selected_resource not in resources:
            raise ValueError(
                f"Framegraph resource '{selected_resource}' is not available"
            )

        model.core.capture.reset_capture()
        model.core.depth_capture.reset_capture()
        model.set_channel_mode(int(channel_mode))
        model.set_highlight_hdr(bool(highlight_hdr))
        model.set_mode("between")
        model.set_source_resource(selected_resource)
        if self._on_request_update is not None:
            self._on_request_update()

        return {
            "target_index": _index_of_target_source(model.targets, model.current_viewport),
            "target_label": _current_target_label(model),
            "resource": selected_resource,
            "resources": resources,
            "capture": _capture_summary(model),
        }

    def prepare_pass_symbol_capture(
        self,
        *,
        target_index: int | None = None,
        pass_index: int | None = None,
        pass_name: str | None = None,
        symbol: str | None = None,
        symbol_index: int | None = None,
    ) -> dict[str, object]:
        """Connect an inside-pass debug capture to a pass internal symbol."""
        model = self._ensure_model()
        model.refresh_viewports()
        if target_index is not None:
            model.set_viewport_by_index(int(target_index))

        pipeline = model.get_current_pipeline()
        if pipeline is None:
            raise RuntimeError("Current framegraph target has no pipeline")

        frame_pass, resolved_pass_index = _resolve_pass(
            pipeline,
            pass_index=pass_index,
            pass_name=pass_name,
        )
        symbols = list(frame_pass.get_internal_symbols())
        if not symbols:
            raise ValueError(
                f"Framegraph pass '{frame_pass.pass_name}' has no internal symbols"
            )
        resolved_symbol, resolved_symbol_index = _resolve_symbol(
            symbols,
            symbol=symbol,
            symbol_index=symbol_index,
        )

        model.core.capture.reset_capture()
        model.core.depth_capture.reset_capture()
        model.set_mode("inside")
        model.set_selected_pass_by_index(resolved_pass_index)
        model.set_selected_symbol(resolved_symbol)
        if self._on_request_update is not None:
            self._on_request_update()

        return {
            "target_index": _index_of_target_source(model.targets, model.current_viewport),
            "target_label": _current_target_label(model),
            "pass_index": resolved_pass_index,
            "pass_name": frame_pass.pass_name,
            "pass_type": frame_pass.type_name,
            "symbol": resolved_symbol,
            "symbol_index": resolved_symbol_index,
            "symbols": symbols,
            "capture": _capture_summary(model),
        }

    def export_capture(
        self,
        *,
        output_path: str | None = None,
        include_image: bool = False,
        capture_kind: str = "main",
    ) -> dict[str, object]:
        """Write the current framegraph capture to PNG if a capture is ready."""
        model = self._ensure_model()
        capture = _select_capture(model, capture_kind)
        if not capture.has_capture():
            return {
                "ready": False,
                "capture_kind": capture_kind,
                "capture": _capture_summary_for(capture),
            }

        from termin.visualization.render.manager import RenderingManager

        render_engine = RenderingManager.instance().render_engine
        if render_engine is None:
            raise RuntimeError("No render engine is available")
        render_engine.ensure_tgfx2()
        device = render_engine.tgfx2_device
        if device is None:
            raise RuntimeError("No tgfx2 device is available")

        path = _resolve_capture_path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        width = int(capture.width)
        height = int(capture.height)
        if width <= 0 or height <= 0:
            raise RuntimeError(f"Invalid framegraph capture size {width}x{height}")

        if bool(capture.is_depth):
            result = model.core.presenter.read_depth_normalized(
                device,
                capture.capture_tex,
            )
            if result is None:
                raise RuntimeError("Failed to read framegraph depth capture")
            data, width, height = result
            image_array = np.frombuffer(data, dtype=np.uint8).reshape(
                (int(height), int(width))
            )
            Image.fromarray(image_array, mode="L").save(path)
        else:
            pixels = np.empty(width * height * 4, dtype=np.float32)
            if not device.read_texture_rgba_float(capture.capture_tex, pixels):
                raise RuntimeError("Failed to read framegraph color capture")
            # tgfx2 readback returns rows in top-left CPU order for all backends.
            rgba = pixels.reshape((height, width, 4))
            rgba = _apply_preview_params(
                rgba,
                channel_mode=model.channel_mode,
                highlight_hdr=model.highlight_hdr,
            )
            rgba8 = np.clip(rgba * 255.0, 0.0, 255.0).astype(np.uint8)
            Image.fromarray(rgba8, mode="RGBA").save(path)

        log.info(f"[FramegraphDebuggerService] exported framegraph capture: {path}")
        payload: dict[str, object] = {
            "ready": True,
            "path": str(path),
            "width": int(width),
            "height": int(height),
            "mime_type": "image/png",
            "capture_kind": capture_kind,
            "capture": _capture_summary_for(capture),
            "resource": model.debug_source_res,
            "target_index": _index_of_target_source(model.targets, model.current_viewport),
            "target_label": _current_target_label(model),
        }
        if include_image:
            payload["base64"] = base64.b64encode(path.read_bytes()).decode("ascii")
        return payload

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


def _resolve_pass(
    pipeline: object,
    *,
    pass_index: int | None,
    pass_name: str | None,
) -> tuple[object, int]:
    passes = list(pipeline.passes)
    if not passes:
        raise RuntimeError("Current framegraph pipeline has no passes")
    if pass_index is not None:
        resolved_index = int(pass_index)
        if resolved_index < 0 or resolved_index >= len(passes):
            raise ValueError(
                f"Framegraph pass index {resolved_index} is outside 0..{len(passes) - 1}"
            )
        frame_pass = passes[resolved_index]
        if pass_name is not None and frame_pass.pass_name != pass_name:
            raise ValueError(
                "Framegraph pass selector mismatch: "
                f"index {resolved_index} is '{frame_pass.pass_name}', not '{pass_name}'"
            )
        return frame_pass, resolved_index

    if pass_name is None:
        raise ValueError("Either pass_index or pass_name is required")

    matches = [
        (index, frame_pass)
        for index, frame_pass in enumerate(passes)
        if frame_pass.pass_name == pass_name
    ]
    if not matches:
        raise ValueError(f"Framegraph pass '{pass_name}' is not available")
    if len(matches) > 1:
        indices = [index for index, _frame_pass in matches]
        raise ValueError(
            f"Framegraph pass name '{pass_name}' is ambiguous; use pass_index "
            f"(matches: {indices})"
        )
    resolved_index, frame_pass = matches[0]
    return frame_pass, resolved_index


def _resolve_symbol(
    symbols: list[str],
    *,
    symbol: str | None,
    symbol_index: int | None,
) -> tuple[str, int]:
    if symbol_index is not None:
        resolved_index = int(symbol_index)
        if resolved_index < 0 or resolved_index >= len(symbols):
            raise ValueError(
                f"Framegraph symbol index {resolved_index} is outside 0..{len(symbols) - 1}"
            )
        resolved_symbol = symbols[resolved_index]
        if symbol is not None and resolved_symbol != symbol:
            raise ValueError(
                "Framegraph symbol selector mismatch: "
                f"index {resolved_index} is '{resolved_symbol}', not '{symbol}'"
            )
        return resolved_symbol, resolved_index

    if symbol is None:
        return symbols[-1], len(symbols) - 1

    matches = [index for index, candidate in enumerate(symbols) if candidate == symbol]
    if not matches:
        raise ValueError(f"Framegraph symbol '{symbol}' is not available")
    if len(matches) > 1:
        raise ValueError(
            f"Framegraph symbol '{symbol}' is ambiguous; use symbol_index "
            f"(matches: {matches})"
        )
    resolved_index = matches[0]
    return symbols[resolved_index], resolved_index


def _current_target_label(model: object) -> str | None:
    targets = model.targets
    index = _index_of_target_source(targets, model.current_viewport)
    if index is None:
        return None
    return targets[index].label


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
    return _capture_summary_for(model.core.capture)


def _capture_summary_for(capture: object) -> dict[str, object]:
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


def _select_capture(model: object, capture_kind: str) -> object:
    normalized = capture_kind.strip().lower()
    if normalized in ("", "main", "color", "capture"):
        return model.core.capture
    if normalized in ("depth", "depth_capture"):
        return model.core.depth_capture
    raise ValueError("capture_kind must be 'main' or 'depth'")


def _apply_preview_params(
    rgba: np.ndarray,
    *,
    channel_mode: int,
    highlight_hdr: bool,
) -> np.ndarray:
    if channel_mode == 1:
        result_rgb = np.repeat(rgba[:, :, 0:1], 3, axis=2)
    elif channel_mode == 2:
        result_rgb = np.repeat(rgba[:, :, 1:2], 3, axis=2)
    elif channel_mode == 3:
        result_rgb = np.repeat(rgba[:, :, 2:3], 3, axis=2)
    elif channel_mode == 4:
        result_rgb = np.repeat(rgba[:, :, 3:4], 3, axis=2)
    else:
        result_rgb = rgba[:, :, :3].copy()

    if highlight_hdr:
        max_value = np.max(rgba[:, :, :3], axis=2)
        hdr_mask = max_value > 1.0
        if np.any(hdr_mask):
            intensity = np.clip((max_value - 1.0) / 2.0, 0.0, 1.0)
            mix = 0.5 + intensity * 0.5
            magenta = np.array([1.0, 0.0, 1.0], dtype=np.float32)
            result_rgb[hdr_mask] = (
                result_rgb[hdr_mask] * (1.0 - mix[hdr_mask, None])
                + magenta * mix[hdr_mask, None]
            )

    alpha = np.ones((*result_rgb.shape[:2], 1), dtype=result_rgb.dtype)
    return np.concatenate((result_rgb, alpha), axis=2)


def _resolve_capture_path(output_path: str | None) -> Path:
    if output_path:
        path = Path(output_path).expanduser()
        if path.suffix.lower() != ".png":
            if path.exists() and path.is_dir():
                return path / _default_capture_name()
            return path.with_suffix(".png")
        return path
    return Path(tempfile.gettempdir()) / "termin-framegraph-captures" / _default_capture_name()


def _default_capture_name() -> str:
    return f"termin-framegraph-{time.strftime('%Y%m%d-%H%M%S')}.png"


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
