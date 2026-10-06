"""Helpers loaded with exec-file in an isolated CargoTerminal editor.

Load this file before each call; functions accept the editor's globals().
prepare(globals(), "hall", True); wait for warmup outside the editor thread;
sample(globals(), "/tmp/hall-on.json", 120).
"""

import json
import ctypes as ct
from pathlib import Path
import statistics
import sys


def _flatten_sections(nodes, parent=""):
    result = []
    for section in nodes.values():
        path = parent + "/" + section.name
        result.append({"path": path, "name": section.name,
                       "cpu_ms": section.cpu_ms, "calls": section.call_count})
        result.extend(_flatten_sections(section.children, path))
    return result


def prepare(ns, view, enabled):
    from termin.render import _render_native as render
    root = Path(ns["project_path"])
    sys.path.insert(0, str(root / "tools"))
    from cargo_terminal.editor import camera
    if not ns["game_mode_controller"].model.is_game_mode:
        raise RuntimeError("Enter Play and editor pause before preparing a sample")
    if not ns["game_mode_controller"].model.is_game_paused:
        raise RuntimeError("Pause Play to keep the A/B scene identical")
    camera(ns, view)
    render.set_render_item_culling_enabled(enabled)
    render.clear_render_item_culling_diagnostics()
    ns["profiler_capture_coordinator"].acquire("cargo-culling-ab")
    ns["profiler_capture_coordinator"].profiler.clear_history()
    ns["request_render_update"]()
    print(json.dumps({"view": view, "enabled": enabled}))


def _gpu_history(native_library):
    # Read the public tc_frame_profile ABI on the owning editor thread. Python
    # bindings currently omit GPU fields; copy values before history can change.
    class Frame(ct.Structure):
        _fields_ = [("frame", ct.c_int), ("start", ct.c_double),
                    ("interval", ct.c_double), ("active", ct.c_double),
                    ("total", ct.c_double), ("target", ct.c_double),
                    ("late", ct.c_double), ("missed", ct.c_int),
                    ("profiled", ct.c_bool), ("sections", ct.c_void_p),
                    ("count", ct.c_int), ("gpu_ms", ct.c_double),
                    ("has_gpu", ct.c_bool)]
    base = ct.CDLL(str(native_library))
    base.tc_profiler_history_count.restype = ct.c_int
    base.tc_profiler_history_at.argtypes = [ct.c_int]
    base.tc_profiler_history_at.restype = ct.POINTER(Frame)
    values = {}
    count = base.tc_profiler_history_count()
    # Timestamp results arrive asynchronously; leave eight recent frames out
    # of the GPU mean so late submissions have time to accumulate.
    for index in range(max(0, count - 8)):
        frame = base.tc_profiler_history_at(index).contents
        if frame.has_gpu:
            values[frame.frame] = frame.gpu_ms
    return values


def sample(ns, destination, frames=120, native_library=None):
    from termin.render import _render_native as render
    history = ns["profiler_capture_coordinator"].profiler.history[-frames:]
    if len(history) != frames or not all(frame.sections_profiled for frame in history):
        raise RuntimeError("Insufficient profiled frames; allow more warmup")
    rows = []
    gpu_values = _gpu_history(native_library) if native_library is not None else {}
    for frame in history:
        sections = _flatten_sections(frame.sections)
        rows.append({"frame": frame.frame_number, "active_ms": frame.active_ms,
                     "interval_ms": frame.interval_ms, "sections": sections,
                     "gpu_ms": gpu_values.get(frame.frame_number)})
    render_spans = [sum(s["cpu_ms"] for s in row["sections"] if s["name"] == "SceneManager Render")
                    for row in rows]
    if not all(render_spans):
        raise RuntimeError("SceneManager Render scope missing")
    # Encode count is a cross-check; pass diagnostics count successful submits.
    draws = [sum(s["calls"] for s in row["sections"] if s["name"] == "Encode mesh draw") for row in rows]
    if not any(draws):
        raise RuntimeError("Backend draw scope missing; check profiler scopes before claiming draws")
    diagnostics = render.get_render_item_culling_diagnostics()
    gpu_spans = [row["gpu_ms"] for row in rows if row["gpu_ms"] is not None]
    result = {"frames": frames, "method": "CPU wall spans; optional native GPU submission timestamps",
              "gpu_frames": len(gpu_spans),
              "gpu_ms": statistics.mean(gpu_spans) if gpu_spans else None,
              "enabled": render.render_item_culling_enabled(),
              "active_ms": statistics.mean(row["active_ms"] for row in rows),
              "interval_ms": statistics.mean(row["interval_ms"] for row in rows),
              "render_ms": statistics.mean(render_spans),
              "mesh_encode_calls": statistics.mean(draws),
              "mesh_draws": sum(record["mesh_draws"] for record in diagnostics),
              "max_profiler_sections": max(len(row["sections"]) for row in rows),
              "culling": diagnostics,
              "raw": rows}
    Path(destination).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key not in ("raw", "culling")}))
