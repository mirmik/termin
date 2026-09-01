"""Toolkit-neutral pipeline graph construction, persistence and mutations."""

from __future__ import annotations

import json
import logging
import os
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Any

from termin.nodegraph.controller import GraphController
from termin.nodegraph.model import Graph, Node, Socket
from termin.nodegraph.schema import ConnectionValidator

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


@dataclass(frozen=True)
class _PassNodeBaseline:
    envelope: dict
    graph_type: str
    instance_name: str
    params: dict


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
        return ""
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
    choices = [("", "(None)")]
    for name in manager.list_material_names():
        asset = manager.get_material_asset(name)
        if asset is None:
            _logger.error("Pipeline editor cannot resolve UUID for material '%s'", name)
            continue
        choices.append((asset.uuid, name))
    return choices


def _material_reference_for_editor(value: object) -> str:
    """Convert a persisted material handle into the UUID used by editor widgets."""
    if isinstance(value, dict):
        uuid = value.get("uuid")
        if isinstance(uuid, str) and uuid:
            return uuid
        if value.get("type") == "none":
            return ""
        _logger.error("Pipeline editor found an invalid material reference: %r", value)
        return ""

    if not isinstance(value, str) or not value or value == "(None)":
        return ""

    from termin.editor_core.resource_manager import ResourceManager

    manager = ResourceManager.instance()
    asset = manager.get_material_asset_by_uuid(value)
    if asset is not None:
        return asset.uuid
    asset = manager.get_material_asset(value)
    if asset is not None:
        return asset.uuid
    _logger.error("Pipeline editor cannot migrate unknown material reference '%s'", value)
    return value


def _material_reference_for_storage(value: object) -> dict[str, str]:
    """Return the canonical serialized tc_material handle for a graph document."""
    if not value or value == "(None)":
        return {"type": "none"}

    from termin.editor_core.resource_manager import ResourceManager

    manager = ResourceManager.instance()
    identifier = str(value)
    asset = manager.get_material_asset_by_uuid(identifier)
    if asset is None:
        # This is the one-way migration path for pre-UUID pipeline documents.
        asset = manager.get_material_asset(identifier)
    if asset is None:
        message = f"Pipeline editor cannot serialize unknown material reference '{identifier}'"
        _logger.error(message)
        raise ValueError(message)
    return {
        "uuid": asset.uuid,
        "name": asset.name,
        "type": "uuid",
        "kind": "tc_material",
    }


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
    from termin.inspect import InspectRegistry
    from termin.render_framework import tc_pass_registry_get_class

    cls = tc_pass_registry_get_class(pass_class_name)
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
    if graph_type in ("Color Texture", "Multiview Color Texture"):
        _add_node_param(node, "format", "Format", "enum", "rgba8", _COLOR_TEXTURE_FORMAT_CHOICES)
    elif graph_type in ("Depth Texture", "Multiview Depth Texture"):
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
    if graph_type not in ("FBO", "Multiview FBO"):
        return
    if graph_type == "Multiview FBO":
        node.params["array_layers"] = 2
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
    controller: GraphController,
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
        for edge_id, edge in controller.graph.edges.items()
        if edge.dst_node_id == node.id and edge.dst_socket in remove_names
    ]:
        controller.remove_edge(edge_id)
    node.inputs = [socket for socket in node.inputs if socket.name not in remove_names]
    existing = {socket.name: socket for socket in node.inputs}
    for socket_name, socket_type in filtered:
        socket = existing.get(socket_name)
        if socket is None:
            node.inputs.append(Socket(socket_name, socket_type, is_input=True))
        else:
            socket.socket_type = socket_type
    node.data["dynamic_inputs"] = filtered
    controller.update_node(node.id, inputs=node.inputs, data=node.data)


def sync_material_pass_inputs(controller: GraphController, node: Node) -> bool:
    if str(node.data.get("graph_type", "")) != "MaterialPass":
        return False
    static_inputs, _, _ = _extract_pass_socket_info("MaterialPass")
    _set_dynamic_input_sockets(
        controller,
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
        elif graph_type == "Multiview Color Texture":
            node.params["resource_type"] = "multiview_color_texture"
            node.params["array_layers"] = 2
            controller.add_output_socket(node.id, "color", "multiview_color_texture")
        elif graph_type == "Multiview Depth Texture":
            node.params["resource_type"] = "multiview_depth_texture"
            node.params["array_layers"] = 2
            controller.add_output_socket(node.id, "depth", "multiview_depth_texture")
        elif graph_type == "Multiview FBO":
            node.params["resource_type"] = "multiview_fbo"
            node.params["array_layers"] = 2
            controller.add_output_socket(node.id, "fbo", "multiview_fbo")
        else:
            controller.add_output_socket(node.id, "fbo", "fbo")
    elif node_type == "external_rt":
        node.params.setdefault("slot", "")
        controller.add_output_socket(node.id, "fbo", "fbo")
    elif node_type == "render_target_input":
        controller.add_output_socket(node.id, "color", "fbo")
    elif node_type == "pipeline_output":
        node.params.setdefault("color_content", "display_linear")
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
    elif node_type == "external_xr_multiview_fbo":
        node.params.setdefault("slot", "XR_MULTIVIEW_TARGET")
        controller.add_output_socket(node.id, "fbo", "external_xr_multiview_fbo")
    elif node_type == "multiview_fbo_split":
        controller.add_input_socket(node.id, "fbo", "multiview_fbo")
        controller.add_output_socket(node.id, "color", "multiview_color_texture")
        controller.add_output_socket(node.id, "depth", "multiview_depth_texture")
    elif node_type == "multiview_fbo_join":
        controller.add_input_socket(node.id, "color", "multiview_color_texture")
        controller.add_input_socket(node.id, "depth", "multiview_depth_texture")
        controller.add_output_socket(node.id, "fbo", "multiview_fbo")
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


def _load_pipeline_connection(
    controller: GraphController,
    node_ids: list[str],
    index: int,
    connection: object,
) -> None:
    if not isinstance(connection, dict):
        raise ValueError(f"pipeline connection {index} must be an object")
    source = connection.get("from_node")
    destination = connection.get("to_node")
    if isinstance(source, bool) or not isinstance(source, int):
        raise ValueError(f"pipeline connection {index} from_node must be an integer")
    if isinstance(destination, bool) or not isinstance(destination, int):
        raise ValueError(f"pipeline connection {index} to_node must be an integer")
    if not 0 <= source < len(node_ids):
        raise ValueError(f"pipeline connection {index} from_node is out of range: {source}")
    if not 0 <= destination < len(node_ids):
        raise ValueError(f"pipeline connection {index} to_node is out of range: {destination}")
    source_socket = connection.get("from_socket")
    destination_socket = connection.get("to_socket")
    if not isinstance(source_socket, str) or not source_socket:
        raise ValueError(f"pipeline connection {index} from_socket must be a nonempty string")
    if not isinstance(destination_socket, str) or not destination_socket:
        raise ValueError(f"pipeline connection {index} to_socket must be a nonempty string")
    result = controller.connect(
        node_ids[source],
        source_socket,
        node_ids[destination],
        destination_socket,
    )
    if not result.ok:
        raise ValueError(
            f"pipeline connection {index} rejected "
            f"({source}.{source_socket} -> {destination}.{destination_socket}): "
            f"{result.reason}"
        )


def load_pipeline_graph(data: dict) -> Graph:
    nodes_data = data.get("nodes")
    if not isinstance(nodes_data, list):
        raise ValueError("pipeline graph nodes must be a list")
    connections_data = data.get("connections", [])
    if not isinstance(connections_data, list):
        raise ValueError("pipeline graph connections must be a list")
    viewport_frames = data.get("viewport_frames", [])
    if not isinstance(viewport_frames, list):
        raise ValueError("pipeline graph viewport_frames must be a list")

    graph = Graph()
    execution_model = str(data.get("execution_model", "single_view"))
    if execution_model not in ("single_view", "xr_multiview"):
        raise ValueError(f"Unsupported pipeline execution_model: {execution_model}")
    controller = GraphController(
        graph,
        validator=PipelineConnectionValidator(),
    )
    controller.set_graph_data({"execution_model": execution_model})
    node_ids = []
    for index, node_data in enumerate(nodes_data):
        if not isinstance(node_data, dict):
            raise ValueError(f"pipeline graph node {index} must be an object")
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
        if graph_type == "MaterialPass" and "material" in node.params:
            node.params["material"] = _material_reference_for_editor(node.params["material"])
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
        controller.update_node(
            node.id,
            width=node.width,
            height=node.height,
            params=node.params,
            data=node.data,
        )
        node = graph.nodes[node.id]
        for dynamic in node.data["dynamic_inputs"]:
            if len(dynamic) == 2 and not any(socket.name == str(dynamic[0]) for socket in node.inputs):
                controller.add_input_socket(node.id, str(dynamic[0]), str(dynamic[1]))
        sync_material_pass_inputs(controller, graph.nodes[node.id])
        node_ids.append(node.id)
    for index, connection in enumerate(connections_data):
        _load_pipeline_connection(controller, node_ids, index, connection)
    for index, frame in enumerate(viewport_frames):
        if not isinstance(frame, dict):
            raise ValueError(f"pipeline graph viewport frame {index} must be an object")
        group = controller.add_group(
            str(frame.get("title", "Viewport")),
            float(frame.get("x", 0.0)),
            float(frame.get("y", 0.0)),
            float(frame.get("width", 600.0)),
            float(frame.get("height", 400.0)),
        )
        controller.set_group_data(
            group.id, {"viewport_name": str(frame.get("viewport_name", "main"))}
        )
    return graph


def pass_list_to_pipeline_graph(data: dict) -> Graph:
    passes = data.get("passes")
    if not isinstance(passes, list):
        raise ValueError("pipeline pass-list passes must be a list")
    graph = Graph()
    controller = GraphController(graph)
    for index, pass_data in enumerate(passes):
        if not isinstance(pass_data, dict):
            raise ValueError(f"pipeline pass {index} must be an object")
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
        pass_values = pass_data.get("data", {})
        if not isinstance(pass_values, dict):
            raise ValueError(f"pipeline pass {index} data must be an object")
        node.params.update(pass_values)
        controller.update_node(node.id, params=node.params, data=node.data)
        sync_material_pass_inputs(controller, graph.nodes[node.id])
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
            params = dict(node.params)
            if graph_type == "MaterialPass" and "material" in params:
                params["material"] = _material_reference_for_storage(params["material"])
            entry["params"] = params
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
        "execution_model": str(graph.data.get("execution_model", "single_view")),
        "nodes": serialized_nodes,
        "connections": connections,
        "viewport_frames": frames,
    }


def reload_pipeline_asset(file_path: str | Path) -> bool:
    try:
        from termin.editor_core.resource_manager import ResourceManager

        asset = ResourceManager.instance().get_pipeline_asset(Path(file_path).stem)
        if asset is not None and asset.is_loaded:
            if asset.reload():
                asset.mark_just_saved()
            else:
                _logger.error("Pipeline editor could not reload asset for %s", file_path)
                return False
        return True
    except Exception:
        _logger.exception("Pipeline editor failed to reload asset for %s", file_path)
        return False


def _replace_file_bytes(file_path: Path, content: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{file_path.name}.",
        suffix=".tmp",
        dir=file_path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        mode = file_path.stat().st_mode & 0o777 if file_path.exists() else 0o644
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as temporary_file:
            descriptor = -1
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, file_path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


class PipelineConnectionValidator(ConnectionValidator):
    """Apply the renderer's canonical socket assignment contract in the editor."""

    def validate(
        self,
        src_type: str,
        dst_type: str,
        *,
        src_node_id: str,
        src_socket: str,
        dst_node_id: str,
        dst_socket: str,
    ) -> bool:
        del src_node_id, src_socket, dst_node_id, dst_socket
        from termin.render_framework import graph_socket_type_assignable

        return graph_socket_type_assignable(src_type, dst_type)


class PipelineEditorController:
    """Own current pipeline graph, file identity, node factory and persistence."""

    def __init__(self, graph: Graph | None = None) -> None:
        self.graph = graph or Graph()
        self.graph_controller = GraphController(
            self.graph,
            validator=PipelineConnectionValidator(),
        )
        self.file_path: Path | None = None
        self.file_uuid: str | None = None
        self.source_format = "graph"
        self._pass_list_source: dict | None = None
        self._pass_node_baselines: dict[str, _PassNodeBaseline] = {}
        self.status = "Ready"
        self.graph_changed = Signal()
        self.status_changed = Signal()

    def set_graph(self, graph: Graph) -> None:
        self.graph = graph
        self.graph_controller.replace_graph(graph)
        self.graph_changed.emit(graph)

    def load(self, path: str | Path) -> Graph:
        file_path = Path(path)
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("pipeline document must be a JSON object")
            has_pass_list = "passes" in data
            has_graph = any(key in data for key in ("nodes", "connections", "viewport_frames"))
            if has_pass_list and has_graph:
                raise ValueError("pipeline document mixes graph and pass-list fields")
            if has_pass_list:
                graph = pass_list_to_pipeline_graph(data)
                source_format = "pass-list"
                pass_list_source, pass_node_baselines = self._make_pass_list_state(data, graph)
            elif "nodes" in data:
                graph = load_pipeline_graph(data)
                source_format = "graph"
                pass_list_source, pass_node_baselines = None, {}
            else:
                raise ValueError("pipeline document has no supported authored format")
            file_uuid = data.get("uuid")
            if file_uuid is not None and not isinstance(file_uuid, str):
                raise ValueError("pipeline uuid must be a string")
            self.graph_controller.replace_graph(graph)
            self.graph = graph
            self.file_uuid = file_uuid
            self.source_format = source_format
            self.file_path = file_path
            self._pass_list_source = pass_list_source
            self._pass_node_baselines = pass_node_baselines
            self.graph_changed.emit(graph)
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
        try:
            data = (
                self._merge_pass_list_document()
                if self.source_format == "pass-list"
                else save_pipeline_graph(self.graph)
            )
            if self.file_uuid:
                data["uuid"] = self.file_uuid
            self._validate_save_candidate(data)
            serialized = json.dumps(data, indent=2).encode("utf-8")
            original_exists = file_path.exists()
            original_content = file_path.read_bytes() if original_exists else None
            _replace_file_bytes(file_path, serialized)
            if not reload_pipeline_asset(file_path):
                try:
                    if original_content is None:
                        file_path.unlink()
                    else:
                        _replace_file_bytes(file_path, original_content)
                except Exception:
                    _logger.exception(
                        "Pipeline editor failed to restore %s after reload failure",
                        file_path,
                    )
                raise RuntimeError(f"pipeline asset reload failed: {file_path}")
            self.file_path = file_path
            if self.source_format == "pass-list":
                self._pass_list_source, self._pass_node_baselines = self._make_pass_list_state(
                    data,
                    self.graph,
                )
            self._set_status(f"Saved: {file_path}")
            return file_path
        except Exception:
            _logger.exception("Pipeline editor failed to save %s", file_path)
            self._set_status(f"Save failed: {file_path}")
            raise

    @staticmethod
    def _make_pass_list_state(
        data: dict,
        graph: Graph,
    ) -> tuple[dict, dict[str, _PassNodeBaseline]]:
        snapshot = deepcopy(data)
        passes = snapshot.get("passes")
        if not isinstance(passes, list):
            raise ValueError("pipeline pass-list passes must be a list")
        nodes = list(graph.nodes.values())
        if len(nodes) != len(passes):
            raise ValueError("pipeline pass-list graph does not match its source passes")
        baselines = {
            node.id: _PassNodeBaseline(
                envelope=deepcopy(pass_data),
                graph_type=str(node.data.get("graph_type", node.title)),
                instance_name=str(node.data.get("instance_name", "")),
                params=deepcopy(node.params),
            )
            for node, pass_data in zip(nodes, passes, strict=True)
        }
        return snapshot, baselines

    @staticmethod
    def _stored_pass_params(graph_type: str, params: dict) -> dict:
        result = deepcopy(params)
        if graph_type == "MaterialPass" and "material" in result:
            result["material"] = _material_reference_for_storage(result["material"])
        return result

    def _merge_pass_list_document(self) -> dict:
        if self._pass_list_source is None:
            raise ValueError("pipeline editor has no pass-list source snapshot")
        if self.graph.edges:
            raise ValueError("pass-list pipelines cannot be saved with graph connections")
        if self.graph.groups:
            raise ValueError("pass-list pipelines cannot be saved with viewport groups")

        merged = deepcopy(self._pass_list_source)
        merged_passes = []
        for node in self.graph.nodes.values():
            node_type = str(node.data.get("node_type", node.kind))
            if node_type not in ("pass", "effect"):
                raise ValueError(
                    f"pass-list pipelines cannot contain non-pass node '{node.id}'"
                )
            graph_type = str(node.data.get("graph_type", node.title))
            instance_name = str(node.data.get("instance_name", ""))
            stored_params = self._stored_pass_params(graph_type, node.params)
            baseline = self._pass_node_baselines.get(node.id)
            if baseline is None:
                merged_passes.append(
                    {
                        "type": graph_type,
                        "pass_name": instance_name or graph_type,
                        "data": stored_params,
                    }
                )
                continue
            if graph_type != baseline.graph_type:
                raise ValueError(f"pass-list pass type edits are not supported: {node.id}")

            envelope = deepcopy(baseline.envelope)
            if instance_name != baseline.instance_name:
                envelope["pass_name"] = instance_name or graph_type
            pass_data = envelope.get("data", {})
            if not isinstance(pass_data, dict):
                raise ValueError(f"pipeline pass '{node.id}' data must be an object")
            baseline_params = self._stored_pass_params(graph_type, baseline.params)
            for name in baseline_params.keys() | stored_params.keys():
                if name not in stored_params:
                    pass_data.pop(name, None)
                elif name not in baseline_params or stored_params[name] != baseline_params[name]:
                    pass_data[name] = deepcopy(stored_params[name])
            envelope["data"] = pass_data
            merged_passes.append(envelope)
        merged["passes"] = merged_passes
        return merged

    @staticmethod
    def _validate_save_candidate(data: dict) -> None:
        from termin.default_assets.render.pipeline_asset import validate_pipeline_document
        from termin.editor_core.resource_manager import ResourceManager

        validate_pipeline_document(data, ResourceManager.instance())

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
        self.graph_controller.update_node(node.id, params=node.params, data=node.data)
        sync_material_pass_inputs(self.graph_controller, self.graph.nodes[node.id])
        self.graph_changed.emit(self.graph)
        return self.graph.nodes[node.id]

    def rename_node(self, node_id: str, name: str) -> bool:
        node = self.graph.nodes.get(node_id)
        normalized = name.strip()
        if node is None or not normalized:
            return False
        node.data["instance_name"] = normalized
        self.graph_controller.update_node(node_id, title=normalized, data=node.data)
        self.graph_changed.emit(self.graph)
        return True

    def set_param(self, node: Node, name: str, value: object) -> None:
        if not self.graph_controller.set_node_param(node.id, name, value):
            raise KeyError(node.id)
        self.synchronize_param(self.graph.nodes[node.id])
        self.notify_graph_changed()

    def synchronize_param(self, node: Node) -> None:
        if node.id not in self.graph.nodes:
            raise KeyError(node.id)
        sync_material_pass_inputs(self.graph_controller, self.graph.nodes[node.id])

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
        from termin.default_assets.builtin_types import (
            get_default_builtin_frame_pass_specs,
        )
        from termin.render_framework import tc_pass_registry_get_class

        effect_classes = {"BloomPass", "GrayscalePass", "HighlightPass", "MaterialPass", "TonemapPass"}
        result = []
        class_names = {
            class_name
            for _module_name, class_name in get_default_builtin_frame_pass_specs()
        }
        for class_name in sorted(class_names):
            cls = tc_pass_registry_get_class(class_name)
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
