"""Pipeline Editor window for tcgui based on tcnodegraph."""

from __future__ import annotations

import json
from pathlib import Path

from tcbase import log
from tcgui.widgets.button import Button
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.menu import MenuItem
from tcgui.widgets.ui import UI
from tcgui.widgets.units import pct, px
from tcgui.widgets.vstack import VStack
from tcgui.widgets.file_dialog_overlay import show_open_file_dialog, show_save_file_dialog
from tcgui.widgets.input_dialog import show_input_dialog


_TITLE_TO_PASS_CLASS = {
    "SkyboxPass": "SkyBoxPass",
    "PostProcess": "PostProcessPass",
    "Present": "PresentToScreenPass",
}
_PASS_CLASS_TO_TITLE = {v: k for k, v in _TITLE_TO_PASS_CLASS.items()}
_SOCKET_PARAM_NAMES = {
    "input_res",
    "output_res",
    "shadow_res",
    "depth_res",
    "id_res",
    "normal_res",
    "output_res_target",
}
_FBO_FORMAT_CHOICES = [
    ("render_target", "As Output RenderTarget"),
    ("rgba8", "RGBA8"),
    ("rgba16f", "RGBA16F"),
    ("rgba32f", "RGBA32F"),
    ("r16f", "R16F"),
    ("r32f", "R32F"),
]
_COLOR_TEXTURE_FORMAT_CHOICES = [
    ("rgba8", "RGBA8"),
    ("rgba16f", "RGBA16F"),
    ("rgba32f", "RGBA32F"),
    ("r16f", "R16F"),
    ("r32f", "R32F"),
]
_DEPTH_TEXTURE_FORMAT_CHOICES = [
    ("depth32f", "Depth 32F"),
]


def _default_for_param_kind(kind: str, choices) -> object:
    if choices:
        first = choices[0]
        if isinstance(first, tuple) and first:
            return first[0]
        return first
    if kind == "bool":
        return False
    if kind == "int":
        return 0
    if kind == "float":
        return 0.0
    if kind == "tc_material":
        return "(None)"
    return ""


def _default_for_inspect_field(registry, cls, class_name: str, field_path: str, kind: str, choices) -> object:
    try:
        instance = cls()
        return registry.get(instance, field_path)
    except Exception as e:
        log.warn(f"[PipelineEditor] failed to read default for {class_name}.{field_path}: {e}")
        return _default_for_param_kind(kind, choices)


def _material_choices() -> list[tuple[str, str]]:
    from termin.visualization.core.resources import ResourceManager

    rm = ResourceManager.instance()
    return [("(None)", "(None)")] + [(name, name) for name in rm.list_material_names()]


def _normalize_param_spec(kind: str, choices):
    if kind == "tc_material":
        return "enum", _material_choices()
    if choices:
        return "enum", choices
    return kind, choices


def _add_node_param(
    node,
    name: str,
    label: str,
    kind: str,
    default: object,
    choices=None,
    min_value=None,
    max_value=None,
    step=None,
) -> None:
    if name in _SOCKET_PARAM_NAMES:
        return
    kind, choices = _normalize_param_spec(kind, choices)
    if name not in node.params:
        node.params[name] = default
    specs = node.data.get("param_specs")
    if not isinstance(specs, dict):
        specs = {}
        node.data["param_specs"] = specs
    spec = {
        "label": label or name,
        "kind": kind,
    }
    if choices:
        items = []
        for c in choices:
            if isinstance(c, tuple) and c:
                value = str(c[0])
                label = str(c[1]) if len(c) > 1 else value
                items.append({"value": value, "label": label})
            else:
                items.append(str(c))
        spec["items"] = items
    if min_value is not None:
        spec["min"] = min_value
    if max_value is not None:
        spec["max"] = max_value
    if step is not None:
        spec["step"] = step
    specs[name] = spec


def _add_inspect_params(node, class_name: str, cls, seen: set[str]) -> None:
    try:
        from termin._native.inspect import InspectRegistry
        registry = InspectRegistry.instance()
        for info in registry.all_fields(class_name):
            if not info.is_inspectable:
                continue
            if info.path in seen:
                continue
            if info.path in _SOCKET_PARAM_NAMES:
                continue
            choices = [(c.value, c.label) for c in info.choices] if info.choices else None
            _add_node_param(
                node,
                info.path,
                info.label,
                info.kind,
                _default_for_inspect_field(registry, cls, class_name, info.path, info.kind, choices),
                choices,
                info.min,
                info.max,
                info.step,
            )
            seen.add(info.path)
    except Exception as e:
        log.warn(f"[PipelineEditor] failed to collect inspect params for {class_name}: {e}")


def _populate_pass_node_params(node, pass_class_name: str) -> None:
    from termin.visualization.core.resources import ResourceManager

    rm = ResourceManager.instance()
    rm.register_builtin_frame_passes()
    cls = rm.get_frame_pass(pass_class_name)
    if cls is None:
        log.warn(f"[PipelineEditor] pass class not found for node params: {pass_class_name}")
        return

    seen: set[str] = set()
    _add_inspect_params(node, pass_class_name, cls, seen)


def _populate_resource_node_params(node, graph_type: str) -> None:
    if graph_type == "Shadow Maps":
        return
    if graph_type == "Color Texture":
        _add_node_param(node, "format", "Format", "enum", "rgba8", _COLOR_TEXTURE_FORMAT_CHOICES)
    elif graph_type == "Depth Texture":
        _add_node_param(node, "format", "Format", "enum", "depth32f", _DEPTH_TEXTURE_FORMAT_CHOICES)
    else:
        _add_node_param(node, "format", "Format", "enum", "render_target", _FBO_FORMAT_CHOICES)
        _add_node_param(node, "samples", "MSAA", "enum", "1", [("1", "1"), ("2", "2"), ("4", "4"), ("8", "8")])
    _add_node_param(node, "filter", "Filter", "enum", "linear", [("linear", "Linear"), ("nearest", "Nearest")])
    _add_node_param(node, "size_mode", "Size", "enum", "viewport", [("viewport", "Viewport"), ("fixed", "Fixed")])
    _add_node_param(node, "scale", "Scale", "enum", "1.0", [("0.25", "0.25"), ("0.5", "0.5"), ("1.0", "1.0"), ("2.0", "2.0")])
    _add_node_param(node, "width", "Width", "int", 1024)
    _add_node_param(node, "height", "Height", "int", 1024)
    if graph_type != "FBO":
        return
    _add_node_param(node, "has_color", "Color", "bool", True)
    _add_node_param(node, "has_depth", "Depth", "bool", True)
    _add_node_param(node, "clear_color", "Clear Color", "bool", False)
    _add_node_param(node, "clear_color_r", "R", "float", 0.0)
    _add_node_param(node, "clear_color_g", "G", "float", 0.0)
    _add_node_param(node, "clear_color_b", "B", "float", 0.0)
    _add_node_param(node, "clear_color_a", "A", "float", 1.0)
    _add_node_param(node, "clear_depth", "Clear Depth", "bool", False)
    _add_node_param(node, "clear_depth_value", "Depth", "float", 1.0)


def _pass_class_name(title: str) -> str:
    return _TITLE_TO_PASS_CLASS.get(title, title)


def _graph_title_from_pass_class(pass_class_name: str) -> str:
    return _PASS_CLASS_TO_TITLE.get(pass_class_name, pass_class_name)


def _node_title(node_type: str, graph_type: str, instance_name: str) -> str:
    if instance_name:
        return f"{instance_name} ({graph_type})"
    if node_type == "resource" and graph_type == "FBO":
        return instance_name or "FBO"
    return graph_type


def _extract_pass_socket_info(pass_class_name: str) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]]]:
    from termin.nodegraph.pass_registry import get_pass_inplace_pairs, get_pass_sockets

    inputs, outputs = get_pass_sockets(pass_class_name)
    inplace_pairs = get_pass_inplace_pairs(pass_class_name)
    return list(inputs), list(outputs), list(inplace_pairs)


def _load_graph_from_pipeline_dict(data: dict):
    from tcnodegraph import Graph, GraphController

    graph = Graph()
    controller = GraphController(graph)
    node_ids: list[str] = []

    for i, node_data in enumerate(data.get("nodes", [])):
        node_type = node_data.get("node_type", "pass")
        raw_type = node_data.get("type", "Node")
        instance_name = node_data.get("name", "")

        # Normalize to real class name for pass/effect nodes.
        if node_type in ("pass", "effect"):
            graph_type = _pass_class_name(raw_type)
            display = _graph_title_from_pass_class(graph_type)
        else:
            graph_type = raw_type
            display = graph_type

        title = _node_title(node_type, display, instance_name)

        node = controller.create_node(
            node_type,
            title=title,
            x=float(node_data.get("x", 0.0)),
            y=float(node_data.get("y", 0.0)),
            node_id=f"node_{i}",
        )
        has_width = "width" in node_data
        has_height = "height" in node_data
        node.width = float(node_data.get("width", node.width))
        node.height = float(node_data.get("height", node.height))
        node.params.update(dict(node_data.get("params", {})))

        dynamic_inputs = list(node_data.get("dynamic_inputs", []))
        node.data["graph_type"] = graph_type
        node.data["instance_name"] = instance_name
        node.data["node_type"] = node_type
        node.data["dynamic_inputs"] = dynamic_inputs
        node.data["explicit_size"] = has_width or has_height

        if node_type == "resource":
            _populate_resource_node_params(node, graph_type)
            if graph_type == "Shadow Maps":
                controller.add_output_socket(node.id, "shadow", "shadow")
            elif graph_type == "Color Texture":
                controller.add_output_socket(node.id, "color", "color_texture")
            elif graph_type == "Depth Texture":
                controller.add_output_socket(node.id, "depth", "depth_texture")
            else:
                controller.add_output_socket(node.id, "fbo", "fbo")
        elif node_type == "external_rt":
            controller.add_output_socket(node.id, "fbo", "fbo")
        elif node_type == "render_target_input":
            controller.add_output_socket(node.id, "color", "fbo")
        elif node_type == "pipeline_output":
            controller.add_input_socket(node.id, "color", "fbo")
        elif node_type == "output":
            controller.add_input_socket(node.id, "color", "fbo")
            controller.add_input_socket(node.id, "depth", "fbo")
        elif node_type == "fbo_split":
            controller.add_input_socket(node.id, "fbo", "fbo")
            controller.add_output_socket(node.id, "color", "color_texture")
            controller.add_output_socket(node.id, "depth", "depth_texture")
        elif node_type == "fbo_join":
            controller.add_input_socket(node.id, "color", "color_texture")
            controller.add_input_socket(node.id, "depth", "depth_texture")
            controller.add_output_socket(node.id, "fbo", "fbo")
        elif node_type in ("pass", "effect"):
            pass_class = _pass_class_name(graph_type)
            _populate_pass_node_params(node, pass_class)
            inputs, outputs, inplace_pairs = _extract_pass_socket_info(pass_class)
            inplace_outputs = {out_name for _, out_name in inplace_pairs}

            for socket_name, socket_type in inputs:
                controller.add_input_socket(node.id, socket_name, socket_type)
            for socket_name, socket_type in outputs:
                controller.add_output_socket(node.id, socket_name, socket_type)
                if socket_name not in inplace_outputs:
                    controller.add_input_socket(node.id, f"{socket_name}_target", socket_type)

            for dyn in dynamic_inputs:
                if len(dyn) != 2:
                    continue
                dyn_name = str(dyn[0])
                dyn_type = str(dyn[1])
                has_dyn = any(s.name == dyn_name for s in node.inputs)
                if not has_dyn:
                    controller.add_input_socket(node.id, dyn_name, dyn_type)

        node_ids.append(node.id)

    for conn in data.get("connections", []):
        if conn is None:
            continue
        from_idx = conn.get("from_node")
        to_idx = conn.get("to_node")
        if from_idx is None or to_idx is None:
            continue
        if from_idx < 0 or to_idx < 0:
            continue
        if from_idx >= len(node_ids) or to_idx >= len(node_ids):
            continue

        controller.connect(
            node_ids[from_idx],
            str(conn.get("from_socket", "")),
            node_ids[to_idx],
            str(conn.get("to_socket", "")),
        )

    for frame in data.get("viewport_frames", []):
        group = controller.add_group(
            title=str(frame.get("title", "Viewport")),
            x=float(frame.get("x", 0.0)),
            y=float(frame.get("y", 0.0)),
            width=float(frame.get("width", 600.0)),
            height=float(frame.get("height", 400.0)),
        )
        group.data["viewport_name"] = str(frame.get("viewport_name", "main"))

    return graph


def _save_graph_to_pipeline_dict(graph) -> dict:
    nodes = list(graph.nodes.values())
    node_to_index = {n.id: i for i, n in enumerate(nodes)}

    out_nodes = []
    for node in nodes:
        graph_type = str(node.data.get("graph_type", node.title))
        node_type = str(node.data.get("node_type", node.kind))
        instance_name = str(node.data.get("instance_name", ""))

        # Map UI display names back to real class names for pass/effect nodes.
        if node_type in ("pass", "effect"):
            graph_type = _pass_class_name(graph_type)

        node_entry = {
            "type": graph_type,
            "x": node.x,
            "y": node.y,
        }
        if node_type != "pass":
            node_entry["node_type"] = node_type
        if instance_name:
            node_entry["name"] = instance_name
        if node.params:
            node_entry["params"] = dict(node.params)
        node_entry["width"] = node.width
        node_entry["height"] = node.height

        dynamic_inputs = node.data.get("dynamic_inputs", [])
        if dynamic_inputs:
            node_entry["dynamic_inputs"] = dynamic_inputs

        out_nodes.append(node_entry)

    out_connections = []
    for edge in graph.edges.values():
        from_idx = node_to_index.get(edge.src_node_id)
        to_idx = node_to_index.get(edge.dst_node_id)
        if from_idx is None or to_idx is None:
            continue
        out_connections.append(
            {
                "from_node": from_idx,
                "from_socket": edge.src_socket,
                "to_node": to_idx,
                "to_socket": edge.dst_socket,
            }
        )

    out_frames = []
    for group in graph.groups.values():
        out_frames.append(
            {
                "title": group.title,
                "viewport_name": str(group.data.get("viewport_name", "main")),
                "x": group.x,
                "y": group.y,
                "width": group.width,
                "height": group.height,
            }
        )

    return {
        "name": "graph_pipeline",
        "nodes": out_nodes,
        "connections": out_connections,
        "viewport_frames": out_frames,
    }


def _legacy_pipeline_to_graph(data: dict):
    """Convert legacy pipeline format (passes) to a node graph.

    Creates nodes for each pass, positioned vertically. Connections are not
    reconstructed since the legacy format doesn't store them explicitly.
    """
    from tcnodegraph import Graph, GraphController

    graph = Graph()
    controller = GraphController(graph)

    passes = data.get("passes", [])
    node_ids: list[str] = []

    for i, pass_data in enumerate(passes):
        pass_type = pass_data.get("type", "Unknown")
        pass_name = pass_data.get("pass_name", pass_type)
        real_class = _pass_class_name(pass_type)
        display_title = _graph_title_from_pass_class(real_class)

        node = controller.create_node(
            "pass",
            title=f"{pass_name} ({display_title})",
            x=200.0,
            y=80.0 + i * 140.0,
            node_id=f"node_{i}",
        )
        node.data["graph_type"] = real_class
        node.data["instance_name"] = pass_name
        node.data["node_type"] = "pass"
        node.data["dynamic_inputs"] = []
        node.data["explicit_size"] = False
        _populate_pass_node_params(node, real_class)

        inputs, outputs, inplace_pairs = _extract_pass_socket_info(real_class)
        inplace_outputs = {out_name for _, out_name in inplace_pairs}

        for socket_name, socket_type in inputs:
            controller.add_input_socket(node.id, socket_name, socket_type)
        for socket_name, socket_type in outputs:
            controller.add_output_socket(node.id, socket_name, socket_type)
            if socket_name not in inplace_outputs:
                controller.add_input_socket(node.id, f"{socket_name}_target", socket_type)

        node_ids.append(node.id)

    return graph


def _reload_pipeline_asset(file_path: str) -> None:
    """Reload the PipelineAsset for the given file so the inspector refreshes."""
    try:
        name = Path(file_path).stem
        from termin.visualization.core.resources import ResourceManager
        rm = ResourceManager.instance()
        asset = rm.get_pipeline_asset(name)
        if asset is not None and asset.is_loaded:
            asset.unload()
            asset.reload()
            asset.mark_just_saved()
    except Exception as e:
        log.warn(f"[PipelineEditor] Failed to reload pipeline asset: {e}")


def open_pipeline_editor_window(parent_ui: UI, directory: str | None = None, initial_file: str | None = None) -> None:
    """Open Pipeline Editor in a separate tcgui window.

    Args:
        parent_ui: Parent UI for window creation.
        directory: Directory for file dialogs.
        initial_file: Optional path to .pipeline/.scene_pipeline file to load immediately.
    """
    if parent_ui.create_window is None:
        log.error("[PipelineEditor] ui.create_window is not available")
        return

    child = parent_ui.create_window("Pipeline Editor", 1500, 920)
    if child is None:
        log.error("[PipelineEditor] failed to create window")
        return

    from tcnodegraph import Graph, NodeGraphView

    current_file: str | None = None
    current_file_uuid: str | None = None
    current_graph = Graph()
    graph_view = NodeGraphView(current_graph)
    graph_view.use_param_widgets = True
    graph_view.inline_param_editing = False
    graph_view.preferred_width = pct(100)
    graph_view.preferred_height = pct(100)
    graph_view.offset_x = 500
    graph_view.offset_y = 320

    root = VStack()
    root.preferred_width = pct(100)
    root.preferred_height = pct(100)
    root.spacing = 0

    toolbar = HStack()
    toolbar.preferred_height = px(34)
    toolbar.spacing = 6
    toolbar.padding = 6

    btn_open = Button()
    btn_open.text = "Open"

    btn_save = Button()
    btn_save.text = "Save"

    btn_save_as = Button()
    btn_save_as.text = "Save As"

    path_label = Label()
    path_label.text = "(no file)"
    path_label.stretch = True

    status_label = Label()
    status_label.text = "Ready"
    status_label.preferred_height = px(24)

    def _set_status(message: str) -> None:
        status_label.text = message

    def _set_file(path: str | None) -> None:
        nonlocal current_file
        current_file = path
        path_label.text = path if path else "(no file)"

    def _load_path(path: str) -> None:
        if not path:
            return
        nonlocal current_graph, current_file_uuid
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            current_file_uuid = data.get("uuid")

            # Legacy format: convert passes to graph nodes
            if "passes" in data and "nodes" not in data:
                current_graph = _legacy_pipeline_to_graph(data)
                _set_file(path)
                _set_status(f"Loaded (legacy, converted): {path}")
            else:
                current_graph = _load_graph_from_pipeline_dict(data)
                _set_file(path)
                _set_status(f"Loaded: {path}")

            graph_view.set_graph(current_graph)
        except Exception as e:
            log.error(f"[PipelineEditor] load failed: {e}")
            _set_status(f"Load failed: {e}")

    def _save_to(path: str) -> None:
        if not path:
            return
        nonlocal current_file_uuid
        try:
            graph_view.adapter.apply_item_positions_to_model()
            data = _save_graph_to_pipeline_dict(graph_view.adapter.graph)
            if current_file_uuid:
                data["uuid"] = current_file_uuid
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            # Reload the corresponding PipelineAsset so inspector picks up changes.
            _reload_pipeline_asset(path)

            _set_file(path)
            _set_status(f"Saved: {path}")
        except Exception as e:
            log.error(f"[PipelineEditor] save failed: {e}")
            _set_status(f"Save failed: {e}")

    def _create_resource_node(graph_type: str, wx: float, wy: float) -> None:
        node = graph_view.controller.create_node("resource", title=graph_type, x=wx, y=wy)
        node.data["graph_type"] = graph_type
        node.data["instance_name"] = ""
        node.data["node_type"] = "resource"
        node.data["dynamic_inputs"] = []
        node.data["explicit_size"] = False
        _populate_resource_node_params(node, graph_type)
        if graph_type == "Shadow Maps":
            graph_view.controller.add_output_socket(node.id, "shadow", "shadow")
        elif graph_type == "Color Texture":
            graph_view.controller.add_output_socket(node.id, "color", "color_texture")
        elif graph_type == "Depth Texture":
            graph_view.controller.add_output_socket(node.id, "depth", "depth_texture")
        else:
            graph_view.controller.add_output_socket(node.id, "fbo", "fbo")
        graph_view.refresh()

    def _create_pass_node(pass_class_name: str, node_type: str, wx: float, wy: float) -> None:
        display_title = _graph_title_from_pass_class(pass_class_name)
        node = graph_view.controller.create_node(node_type, title=display_title, x=wx, y=wy)
        node.data["graph_type"] = pass_class_name
        node.data["instance_name"] = ""
        node.data["node_type"] = node_type
        node.data["dynamic_inputs"] = []
        node.data["explicit_size"] = False
        _populate_pass_node_params(node, pass_class_name)
        inputs, outputs, inplace_pairs = _extract_pass_socket_info(pass_class_name)
        inplace_outputs = {out_name for _, out_name in inplace_pairs}
        for socket_name, socket_type in inputs:
            graph_view.controller.add_input_socket(node.id, socket_name, socket_type)
        for socket_name, socket_type in outputs:
            graph_view.controller.add_output_socket(node.id, socket_name, socket_type)
            if socket_name not in inplace_outputs:
                graph_view.controller.add_input_socket(node.id, f"{socket_name}_target", socket_type)
        graph_view.refresh()

    def _create_output_node(wx: float, wy: float) -> None:
        node = graph_view.controller.create_node("output", title="Render Target", x=wx, y=wy)
        node.data["graph_type"] = "RenderTarget"
        node.data["instance_name"] = ""
        node.data["node_type"] = "output"
        node.data["dynamic_inputs"] = []
        node.data["explicit_size"] = False
        graph_view.controller.add_input_socket(node.id, "color", "fbo")
        graph_view.controller.add_input_socket(node.id, "depth", "fbo")
        graph_view.refresh()

    def _create_render_target_input_node(wx: float, wy: float) -> None:
        node = graph_view.controller.create_node("render_target_input", title="Render Target Input", x=wx, y=wy)
        node.data["graph_type"] = "RenderTargetInput"
        node.data["instance_name"] = ""
        node.data["node_type"] = "render_target_input"
        node.data["dynamic_inputs"] = []
        node.data["explicit_size"] = False
        graph_view.controller.add_output_socket(node.id, "color", "fbo")
        graph_view.refresh()

    def _create_pipeline_output_node(wx: float, wy: float) -> None:
        node = graph_view.controller.create_node("pipeline_output", title="Pipeline Output", x=wx, y=wy)
        node.data["graph_type"] = "PipelineOutput"
        node.data["instance_name"] = ""
        node.data["node_type"] = "pipeline_output"
        node.data["dynamic_inputs"] = []
        node.data["explicit_size"] = False
        graph_view.controller.add_input_socket(node.id, "color", "fbo")
        graph_view.refresh()

    def _create_external_rt_node(wx: float, wy: float) -> None:
        node = graph_view.controller.create_node("external_rt", title="External RT", x=wx, y=wy)
        node.data["graph_type"] = "External RT"
        node.data["instance_name"] = ""
        node.data["node_type"] = "external_rt"
        node.data["dynamic_inputs"] = []
        node.data["explicit_size"] = False
        node.params["slot"] = ""
        graph_view.controller.add_output_socket(node.id, "fbo", "fbo")
        graph_view.refresh()

    def _create_fbo_split_node(wx: float, wy: float) -> None:
        node = graph_view.controller.create_node("fbo_split", title="FBO Split", x=wx, y=wy)
        node.data["graph_type"] = "FBO Split"
        node.data["instance_name"] = ""
        node.data["node_type"] = "fbo_split"
        node.data["dynamic_inputs"] = []
        node.data["explicit_size"] = False
        graph_view.controller.add_input_socket(node.id, "fbo", "fbo")
        graph_view.controller.add_output_socket(node.id, "color", "color_texture")
        graph_view.controller.add_output_socket(node.id, "depth", "depth_texture")
        graph_view.refresh()

    def _create_fbo_join_node(wx: float, wy: float) -> None:
        node = graph_view.controller.create_node("fbo_join", title="FBO Join", x=wx, y=wy)
        node.data["graph_type"] = "FBO Join"
        node.data["instance_name"] = ""
        node.data["node_type"] = "fbo_join"
        node.data["dynamic_inputs"] = []
        node.data["explicit_size"] = False
        graph_view.controller.add_input_socket(node.id, "color", "color_texture")
        graph_view.controller.add_input_socket(node.id, "depth", "depth_texture")
        graph_view.controller.add_output_socket(node.id, "fbo", "fbo")
        graph_view.refresh()

    def _build_context_menu(wx: float, wy: float) -> list[MenuItem]:
        from tcnodegraph.view import NodeItem, EdgeItem

        hit = graph_view.scene.hit_test(wx, wy)

        # Right-click on a node → node-specific actions
        if isinstance(hit, NodeItem):
            node_id = hit.node_id
            items: list[MenuItem] = [
                MenuItem("Delete Node", on_click=lambda: (_delete_node(node_id))),
                MenuItem("Rename", on_click=lambda: _rename_node(node_id)),
                MenuItem.sep(),
                MenuItem("Add FBO", on_click=lambda: _create_resource_node("FBO", wx, wy)),
                MenuItem("Add Color Texture", on_click=lambda: _create_resource_node("Color Texture", wx, wy)),
                MenuItem("Add Depth Texture", on_click=lambda: _create_resource_node("Depth Texture", wx, wy)),
                MenuItem("Add Shadow Maps", on_click=lambda: _create_resource_node("Shadow Maps", wx, wy)),
                MenuItem("Add Render Target Input", on_click=lambda: _create_render_target_input_node(wx, wy)),
                MenuItem("Add Pipeline Output", on_click=lambda: _create_pipeline_output_node(wx, wy)),
                MenuItem("Add External RT", on_click=lambda: _create_external_rt_node(wx, wy)),
                MenuItem("Add FBO Split", on_click=lambda: _create_fbo_split_node(wx, wy)),
                MenuItem("Add FBO Join", on_click=lambda: _create_fbo_join_node(wx, wy)),
                MenuItem("Add Legacy Render Target", on_click=lambda: _create_output_node(wx, wy)),
            ]
            return items

        # Right-click on an edge → edge-specific actions
        if isinstance(hit, EdgeItem):
            edge_id = hit.data.get("edge_id")
            if edge_id:
                return [MenuItem("Delete Connection", on_click=lambda: _delete_edge(edge_id))]
            return []

        # Empty space → create menu
        return _build_create_menu_items(wx, wy)

    def _delete_node(node_id: str) -> None:
        graph_view.controller.remove_node(node_id)
        graph_view.refresh()

    def _delete_edge(edge_id: str) -> None:
        graph_view.controller.remove_edge(edge_id)
        graph_view.refresh()

    def _build_create_menu_items(wx: float, wy: float) -> list[MenuItem]:
        items: list[MenuItem] = [
            MenuItem("Add Render Target Input", on_click=lambda: _create_render_target_input_node(wx, wy)),
            MenuItem("Add Pipeline Output", on_click=lambda: _create_pipeline_output_node(wx, wy)),
            MenuItem("Add Legacy Render Target", on_click=lambda: _create_output_node(wx, wy)),
            MenuItem.sep(),
            MenuItem("Add FBO", on_click=lambda: _create_resource_node("FBO", wx, wy)),
            MenuItem("Add Color Texture", on_click=lambda: _create_resource_node("Color Texture", wx, wy)),
            MenuItem("Add Depth Texture", on_click=lambda: _create_resource_node("Depth Texture", wx, wy)),
            MenuItem("Add Shadow Maps", on_click=lambda: _create_resource_node("Shadow Maps", wx, wy)),
            MenuItem("Add External RT", on_click=lambda: _create_external_rt_node(wx, wy)),
            MenuItem("Add FBO Split", on_click=lambda: _create_fbo_split_node(wx, wy)),
            MenuItem("Add FBO Join", on_click=lambda: _create_fbo_join_node(wx, wy)),
            MenuItem.sep(),
        ]
        try:
            from termin.visualization.core.resources import ResourceManager
            rm = ResourceManager.instance()
            rm.register_builtin_frame_passes()
            pass_names = sorted(rm.frame_passes.keys())
            effect_classes = {"BloomPass", "GrayscalePass", "MaterialPass", "TonemapPass", "PostProcessPass"}
            for cls_name in pass_names:
                cls = rm.get_frame_pass(cls_name)
                category = cls.category if cls is not None else "Other"
                kind = "effect" if (cls_name in effect_classes or str(category).lower().startswith("effect")) else "pass"
                label = f"{category}: {_graph_title_from_pass_class(cls_name)}"
                items.append(
                    MenuItem(
                        label,
                        on_click=lambda c=cls_name, k=kind: _create_pass_node(c, k, wx, wy),
                    )
                )
        except Exception as e:
            log.warn(f"[PipelineEditor] Cannot build pass menu: {e}")
        return items

    def _rename_node(node_id: str) -> None:
        node = graph_view.adapter.graph.nodes.get(node_id)
        if node is None or graph_view._ui is None:
            return
        current = str(node.data.get("instance_name", node.title))

        def _apply(result: str | None) -> None:
            if result is None:
                return
            new_name = result.strip()
            if not new_name:
                return
            node.title = new_name
            node.data["instance_name"] = new_name
            graph_view.refresh()

        show_input_dialog(
            graph_view._ui,
            title="Rename Node",
            message="Node name:",
            default=current,
            on_result=_apply,
        )

    def _on_open_click() -> None:
        start_dir = directory or str(Path.home())
        if current_file:
            start_dir = str(Path(current_file).parent)
        show_open_file_dialog(
            child,
            title="Open Scene Pipeline",
            directory=start_dir,
            filter_str="Scene Pipeline (*.scene_pipeline);;Pipeline (*.pipeline);;All Files (*)",
            on_result=lambda p: _load_path(p) if p else None,
            windowed=True,
        )

    def _on_save_click() -> None:
        if current_file:
            _save_to(current_file)
            return
        _on_save_as_click()

    def _on_save_as_click() -> None:
        start_dir = directory or str(Path.home())
        if current_file:
            start_dir = str(Path(current_file).parent)
        show_save_file_dialog(
            child,
            title="Save Pipeline",
            directory=start_dir,
            filter_str="Pipeline (*.pipeline);;Scene Pipeline (*.scene_pipeline);;All Files (*)",
            on_result=lambda p: _save_to(p) if p else None,
            windowed=True,
        )

    btn_open.on_click = _on_open_click
    btn_save.on_click = _on_save_click
    btn_save_as.on_click = _on_save_as_click
    graph_view.menu_items_provider = _build_context_menu

    toolbar.add_child(btn_open)
    toolbar.add_child(btn_save)
    toolbar.add_child(btn_save_as)
    toolbar.add_child(path_label)

    root.add_child(toolbar)
    root.add_child(graph_view)
    root.add_child(status_label)
    child.root = root

    # Auto-load file: explicit initial_file takes priority, then search project dir.
    if initial_file:
        _load_path(initial_file)
    elif directory:
        try:
            pdir = Path(directory)
            candidates = sorted(pdir.glob("*.pipeline")) + sorted(pdir.glob("*.scene_pipeline"))
            if not candidates:
                candidates = sorted(pdir.rglob("*.pipeline")) + sorted(pdir.rglob("*.scene_pipeline"))
            if candidates:
                _load_path(str(candidates[0]))
        except Exception as e:
            log.warn(f"[PipelineEditor] auto-load skipped: {e}")
