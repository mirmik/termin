"""Toolkit-neutral pipeline graph construction, persistence and mutations."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from tcnodegraph.controller import GraphController
from tcnodegraph.model import Graph, Node, Socket

from termin.editor_core.signal import Signal


_logger = logging.getLogger(__name__)

_TITLE_TO_PASS_CLASS = {
    "SkyboxPass": "SkyBoxPass",
    "Present": "PresentToScreenPass",
}
_PASS_CLASS_TO_TITLE = {value: key for key, value in _TITLE_TO_PASS_CLASS.items()}
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
_COLOR_TEXTURE_FORMAT_CHOICES = _FBO_FORMAT_CHOICES[1:]
_DEPTH_TEXTURE_FORMAT_CHOICES = [("depth32f", "Depth 32F")]


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


def _default_for_inspect_field(registry, cls, class_name: str, field_path: str, kind: str, choices):
    try:
        instance = cls()
        if "." not in field_path:
            return getattr(instance, field_path)
        return registry.get(instance, field_path)
    except Exception as error:
        _logger.warning(
            "Pipeline editor failed to read default for %s.%s: %s",
            class_name,
            field_path,
            error,
        )
        return _default_for_param_kind(kind, choices)


def _material_choices() -> list[tuple[str, str]]:
    from termin.editor_core.resource_manager import ResourceManager

    manager = ResourceManager.instance()
    return [("(None)", "(None)"), *((name, name) for name in manager.list_material_names())]


def _add_node_param(
    node: Node,
    name: str,
    label: str,
    kind: str,
    default: object,
    choices=None,
    minimum=None,
    maximum=None,
    step=None,
) -> None:
    if name in _SOCKET_PARAM_NAMES:
        return
    if kind == "tc_material":
        kind = "enum"
        choices = _material_choices()
    elif choices:
        kind = "enum"
    if name not in node.params:
        node.params[name] = default
    specs = node.data.get("param_specs")
    if not isinstance(specs, dict):
        specs = {}
        node.data["param_specs"] = specs
    spec: dict[str, Any] = {"label": label or name, "kind": kind}
    if choices:
        items = []
        for choice in choices:
            if isinstance(choice, tuple) and choice:
                value = str(choice[0])
                item_label = str(choice[1]) if len(choice) > 1 else value
                items.append({"value": value, "label": item_label})
            else:
                items.append(str(choice))
        spec["items"] = items
    if minimum is not None:
        spec["min"] = minimum
    if maximum is not None:
        spec["max"] = maximum
    if step is not None:
        spec["step"] = step
    specs[name] = spec


def _populate_pass_node_params(node: Node, pass_class_name: str) -> None:
    from termin.editor_core.resource_manager import ResourceManager
    from termin.inspect import InspectRegistry

    manager = ResourceManager.instance()
    manager.register_builtin_frame_passes()
    cls = manager.get_frame_pass(pass_class_name)
    if cls is None:
        _logger.warning("Pipeline editor pass class has no registered params: %s", pass_class_name)
        return
    registry = InspectRegistry.instance()
    seen = set()
    try:
        for info in registry.all_fields(pass_class_name):
            if not info.is_inspectable or info.path in seen or info.path in _SOCKET_PARAM_NAMES:
                continue
            choices = [(choice.value, choice.label) for choice in info.choices] if info.choices else None
            _add_node_param(
                node,
                info.path,
                info.label,
                info.kind,
                _default_for_inspect_field(
                    registry,
                    cls,
                    pass_class_name,
                    info.path,
                    info.kind,
                    choices,
                ),
                choices,
                info.min,
                info.max,
                info.step,
            )
            seen.add(info.path)
    except Exception:
        _logger.exception("Pipeline editor failed to collect params for %s", pass_class_name)


def _populate_resource_node_params(node: Node, graph_type: str) -> None:
    if graph_type == "Shadow Maps":
        return
    if graph_type == "Color Texture":
        _add_node_param(node, "format", "Format", "enum", "rgba8", _COLOR_TEXTURE_FORMAT_CHOICES)
    elif graph_type == "Depth Texture":
        _add_node_param(
            node,
            "format",
            "Format",
            "enum",
            "depth32f",
            _DEPTH_TEXTURE_FORMAT_CHOICES,
        )
    else:
        _add_node_param(node, "format", "Format", "enum", "render_target", _FBO_FORMAT_CHOICES)
        _add_node_param(
            node,
            "samples",
            "MSAA",
            "enum",
            "1",
            [("1", "1"), ("2", "2"), ("4", "4"), ("8", "8")],
        )
    _add_node_param(
        node,
        "filter",
        "Filter",
        "enum",
        "linear",
        [("linear", "Linear"), ("nearest", "Nearest")],
    )
    _add_node_param(
        node,
        "size_mode",
        "Size",
        "enum",
        "viewport",
        [("viewport", "Viewport"), ("fixed", "Fixed")],
    )
    _add_node_param(
        node,
        "scale",
        "Scale",
        "enum",
        "1.0",
        [("0.25", "0.25"), ("0.5", "0.5"), ("1.0", "1.0"), ("2.0", "2.0")],
    )
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
    return "FBO" if node_type == "resource" and graph_type == "FBO" else graph_type


def _extract_pass_socket_info(pass_class_name: str):
    from termin.editor_core.pipeline_pass_registry import get_pass_inplace_pairs, get_pass_sockets

    inputs, outputs = get_pass_sockets(pass_class_name)
    return list(inputs), list(outputs), list(get_pass_inplace_pairs(pass_class_name))


def _material_pass_texture_inputs(material_name: object) -> list[tuple[str, str]]:
    if not str(material_name) or str(material_name) == "(None)":
        return []
    from termin.render_components.material_pass import get_texture_inputs_for_material

    return list(get_texture_inputs_for_material(str(material_name)))


def _set_dynamic_input_sockets(
    graph: Graph,
    node: Node,
    dynamic_inputs: list[tuple[str, str]],
    keep_sockets: set[str],
) -> None:
    filtered = []
    for socket_name, socket_type in dynamic_inputs:
        name = str(socket_name)
        if not name:
            continue
        if name in keep_sockets:
            _logger.warning("Dynamic socket '%s' conflicts with static input on %s", name, node.title)
            continue
        filtered.append((name, str(socket_type)))
    wanted = {name for name, _ in filtered}
    remove_names = {
        socket.name
        for socket in node.inputs
        if socket.name not in keep_sockets and socket.name not in wanted
    }
    for edge_id in [
        edge_id
        for edge_id, edge in graph.edges.items()
        if edge.dst_node_id == node.id and edge.dst_socket in remove_names
    ]:
        del graph.edges[edge_id]
    node.inputs = [socket for socket in node.inputs if socket.name not in remove_names]
    existing = {socket.name: socket for socket in node.inputs}
    for socket_name, socket_type in filtered:
        socket = existing.get(socket_name)
        if socket is None:
            node.inputs.append(Socket(socket_name, socket_type, is_input=True))
        else:
            socket.socket_type = socket_type
    node.data["dynamic_inputs"] = filtered


def sync_material_pass_inputs(graph: Graph, node: Node) -> bool:
    if str(node.data.get("graph_type", "")) != "MaterialPass":
        return False
    static_inputs, _, _ = _extract_pass_socket_info("MaterialPass")
    _set_dynamic_input_sockets(
        graph,
        node,
        _material_pass_texture_inputs(node.params.get("material", "")),
        {name for name, _ in static_inputs},
    )
    return True


def _configure_node(controller: GraphController, node: Node, node_type: str, graph_type: str) -> None:
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
        node.params.setdefault("slot", "")
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
        inplace_outputs = {output for _, output in inplace_pairs}
        for socket_name, socket_type in inputs:
            controller.add_input_socket(node.id, socket_name, socket_type)
        for socket_name, socket_type in outputs:
            controller.add_output_socket(node.id, socket_name, socket_type)
            if socket_name not in inplace_outputs:
                controller.add_input_socket(node.id, f"{socket_name}_target", socket_type)


def load_pipeline_graph(data: dict) -> Graph:
    graph = Graph()
    controller = GraphController(graph)
    node_ids = []
    for index, node_data in enumerate(data.get("nodes", [])):
        node_type = str(node_data.get("node_type", "pass"))
        raw_type = str(node_data.get("type", "Node"))
        instance_name = str(node_data.get("name", ""))
        graph_type = _pass_class_name(raw_type) if node_type in ("pass", "effect") else raw_type
        display = _graph_title_from_pass_class(graph_type) if node_type in ("pass", "effect") else graph_type
        node = controller.create_node(
            node_type,
            title=_node_title(node_type, display, instance_name),
            x=float(node_data.get("x", 0.0)),
            y=float(node_data.get("y", 0.0)),
            node_id=f"node_{index}",
        )
        node.width = float(node_data.get("width", node.width))
        node.height = float(node_data.get("height", node.height))
        node.params.update(dict(node_data.get("params", {})))
        node.data.update(
            {
                "graph_type": graph_type,
                "instance_name": instance_name,
                "node_type": node_type,
                "dynamic_inputs": list(node_data.get("dynamic_inputs", [])),
                "explicit_size": "width" in node_data or "height" in node_data,
            }
        )
        _configure_node(controller, node, node_type, graph_type)
        for dynamic in node.data["dynamic_inputs"]:
            if len(dynamic) == 2 and not any(socket.name == str(dynamic[0]) for socket in node.inputs):
                controller.add_input_socket(node.id, str(dynamic[0]), str(dynamic[1]))
        sync_material_pass_inputs(graph, node)
        node_ids.append(node.id)
    for connection in data.get("connections", []):
        if connection is None:
            continue
        source = connection.get("from_node")
        destination = connection.get("to_node")
        if not isinstance(source, int) or not isinstance(destination, int):
            continue
        if not (0 <= source < len(node_ids) and 0 <= destination < len(node_ids)):
            continue
        result = controller.connect(
            node_ids[source],
            str(connection.get("from_socket", "")),
            node_ids[destination],
            str(connection.get("to_socket", "")),
        )
        if not result.ok:
            _logger.warning("Pipeline graph ignored invalid connection: %s", result.reason)
    for frame in data.get("viewport_frames", []):
        group = controller.add_group(
            str(frame.get("title", "Viewport")),
            float(frame.get("x", 0.0)),
            float(frame.get("y", 0.0)),
            float(frame.get("width", 600.0)),
            float(frame.get("height", 400.0)),
        )
        group.data["viewport_name"] = str(frame.get("viewport_name", "main"))
    return graph


def pass_list_to_pipeline_graph(data: dict) -> Graph:
    graph = Graph()
    controller = GraphController(graph)
    for index, pass_data in enumerate(data.get("passes", [])):
        pass_type = str(pass_data.get("type", "Unknown"))
        pass_name = str(pass_data.get("pass_name", pass_type))
        graph_type = _pass_class_name(pass_type)
        node = controller.create_node(
            "pass",
            title=f"{pass_name} ({_graph_title_from_pass_class(graph_type)})",
            x=200.0,
            y=80.0 + index * 140.0,
            node_id=f"node_{index}",
        )
        node.data.update(
            {
                "graph_type": graph_type,
                "instance_name": pass_name,
                "node_type": "pass",
                "dynamic_inputs": [],
                "explicit_size": False,
            }
        )
        _configure_node(controller, node, "pass", graph_type)
        sync_material_pass_inputs(graph, node)
    return graph


def save_pipeline_graph(graph: Graph) -> dict:
    nodes = list(graph.nodes.values())
    node_indices = {node.id: index for index, node in enumerate(nodes)}
    serialized_nodes = []
    for node in nodes:
        graph_type = str(node.data.get("graph_type", node.title))
        node_type = str(node.data.get("node_type", node.kind))
        if node_type in ("pass", "effect"):
            graph_type = _pass_class_name(graph_type)
        entry: dict[str, Any] = {"type": graph_type, "x": node.x, "y": node.y}
        if node_type != "pass":
            entry["node_type"] = node_type
        instance_name = str(node.data.get("instance_name", ""))
        if instance_name:
            entry["name"] = instance_name
        if node.params:
            entry["params"] = dict(node.params)
        entry["width"] = node.width
        entry["height"] = node.height
        dynamic_inputs = node.data.get("dynamic_inputs", [])
        if dynamic_inputs:
            entry["dynamic_inputs"] = dynamic_inputs
        serialized_nodes.append(entry)
    connections = []
    for edge in graph.edges.values():
        source = node_indices.get(edge.src_node_id)
        destination = node_indices.get(edge.dst_node_id)
        if source is not None and destination is not None:
            connections.append(
                {
                    "from_node": source,
                    "from_socket": edge.src_socket,
                    "to_node": destination,
                    "to_socket": edge.dst_socket,
                }
            )
    frames = [
        {
            "title": group.title,
            "viewport_name": str(group.data.get("viewport_name", "main")),
            "x": group.x,
            "y": group.y,
            "width": group.width,
            "height": group.height,
        }
        for group in graph.groups.values()
    ]
    return {
        "name": "graph_pipeline",
        "nodes": serialized_nodes,
        "connections": connections,
        "viewport_frames": frames,
    }


def reload_pipeline_asset(file_path: str | Path) -> None:
    try:
        from termin.editor_core.resource_manager import ResourceManager

        asset = ResourceManager.instance().get_pipeline_asset(Path(file_path).stem)
        if asset is not None and asset.is_loaded:
            asset.unload()
            asset.reload()
            asset.mark_just_saved()
    except Exception:
        _logger.exception("Pipeline editor failed to reload asset for %s", file_path)


class PipelineEditorController:
    """Own current pipeline graph, file identity, node factory and persistence."""

    def __init__(self, graph: Graph | None = None) -> None:
        self.graph = graph or Graph()
        self.graph_controller = GraphController(self.graph)
        self.file_path: Path | None = None
        self.file_uuid: str | None = None
        self.status = "Ready"
        self.graph_changed = Signal()
        self.status_changed = Signal()

    def set_graph(self, graph: Graph) -> None:
        self.graph = graph
        self.graph_controller = GraphController(graph)
        self.graph_changed.emit(graph)

    def load(self, path: str | Path) -> Graph:
        file_path = Path(path)
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            graph = (
                pass_list_to_pipeline_graph(data)
                if "passes" in data and "nodes" not in data
                else load_pipeline_graph(data)
            )
            file_uuid = data.get("uuid")
            if file_uuid is not None and not isinstance(file_uuid, str):
                raise ValueError("pipeline uuid must be a string")
            self.file_uuid = file_uuid
            self.file_path = file_path
            self.set_graph(graph)
            self._set_status(f"Loaded: {file_path}")
            return graph
        except Exception:
            _logger.exception("Pipeline editor failed to load %s", file_path)
            self._set_status(f"Load failed: {file_path}")
            raise

    def save(self, path: str | Path | None = None) -> Path:
        file_path = Path(path) if path is not None else self.file_path
        if file_path is None:
            raise ValueError("pipeline editor has no save path")
        data = save_pipeline_graph(self.graph)
        if self.file_uuid:
            data["uuid"] = self.file_uuid
        try:
            file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            reload_pipeline_asset(file_path)
            self.file_path = file_path
            self._set_status(f"Saved: {file_path}")
            return file_path
        except Exception:
            _logger.exception("Pipeline editor failed to save %s", file_path)
            self._set_status(f"Save failed: {file_path}")
            raise

    def create_node(self, node_type: str, graph_type: str, x: float, y: float) -> Node:
        display = (
            _graph_title_from_pass_class(graph_type)
            if node_type in ("pass", "effect")
            else graph_type
        )
        node = self.graph_controller.create_node(node_type, title=display, x=x, y=y)
        node.data.update(
            {
                "graph_type": graph_type,
                "instance_name": "",
                "node_type": node_type,
                "dynamic_inputs": [],
                "explicit_size": False,
            }
        )
        _configure_node(self.graph_controller, node, node_type, graph_type)
        sync_material_pass_inputs(self.graph, node)
        self.graph_changed.emit(self.graph)
        return node

    def rename_node(self, node_id: str, name: str) -> bool:
        node = self.graph.nodes.get(node_id)
        normalized = name.strip()
        if node is None or not normalized:
            return False
        node.title = normalized
        node.data["instance_name"] = normalized
        self.graph_changed.emit(self.graph)
        return True

    def set_param(self, node: Node, name: str, value: object) -> None:
        if not self.graph_controller.set_node_param(node.id, name, value):
            raise KeyError(node.id)
        self.synchronize_param(node)
        self.notify_graph_changed()

    def synchronize_param(self, node: Node) -> None:
        if self.graph.nodes.get(node.id) is not node:
            raise KeyError(node.id)
        sync_material_pass_inputs(self.graph, node)

    def remove_node(self, node_id: str) -> bool:
        if not self.graph_controller.remove_node(node_id):
            return False
        self.graph_changed.emit(self.graph)
        return True

    def remove_edge(self, edge_id: str) -> bool:
        if not self.graph_controller.remove_edge(edge_id):
            return False
        self.graph_changed.emit(self.graph)
        return True

    def notify_graph_changed(self) -> None:
        self.graph_changed.emit(self.graph)

    def available_passes(self) -> tuple[tuple[str, str, str], ...]:
        from termin.editor_core.resource_manager import ResourceManager

        manager = ResourceManager.instance()
        manager.register_builtin_frame_passes()
        effect_classes = {"BloomPass", "GrayscalePass", "HighlightPass", "MaterialPass", "TonemapPass"}
        result = []
        for class_name in sorted(manager.frame_passes):
            cls = manager.get_frame_pass(class_name)
            category = "Other" if cls is None else str(cls.category)
            node_type = (
                "effect"
                if class_name in effect_classes or category.lower().startswith("effect")
                else "pass"
            )
            result.append((class_name, node_type, f"{category}: {_graph_title_from_pass_class(class_name)}"))
        return tuple(result)

    def _set_status(self, status: str) -> None:
        self.status = status
        self.status_changed.emit(status)


__all__ = [
    "PipelineEditorController",
    "load_pipeline_graph",
    "pass_list_to_pipeline_graph",
    "reload_pipeline_asset",
    "save_pipeline_graph",
    "sync_material_pass_inputs",
]
