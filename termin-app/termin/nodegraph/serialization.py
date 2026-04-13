"""Graph serialization for the pipeline editor.

Extends the existing RenderPipeline format with visual graph information
(node positions, connections, viewport frames).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Any

if TYPE_CHECKING:
    from termin.nodegraph.scene import NodeGraphScene
    from termin.nodegraph.node import GraphNode
    from termin.nodegraph.connection import NodeConnection
    from termin.nodegraph.viewport_frame import ViewportFrame


def serialize_graph(scene: "NodeGraphScene") -> dict:
    """
    Serialize the entire node graph to a dictionary.

    Format is compatible with RenderPipeline but adds graph-specific data.

    Returns:
        {
            "name": str,
            "nodes": [...],
            "connections": [...],
            "viewport_frames": [...],
        }
    """
    nodes = scene.get_nodes()
    connections = scene.get_connections()
    viewport_frames = scene.get_viewport_frames()

    # Build node index map for connections
    node_to_index = {node: i for i, node in enumerate(nodes)}

    return {
        "name": "graph_pipeline",
        "nodes": [_serialize_node(node) for node in nodes],
        "connections": [
            _serialize_connection(conn, node_to_index)
            for conn in connections
        ],
        "viewport_frames": [_serialize_viewport_frame(frame) for frame in viewport_frames],
    }


def _serialize_node(node: "GraphNode") -> dict:
    """Serialize a single node. Only saves data that can't be reconstructed."""
    pos = node.pos()

    # Save all parameter values
    params = {}
    for param in node._params:
        value = node._param_values.get(param.name, param.default)
        if value is not None:
            params[param.name] = value

    result = {
        "type": node.title,
        "x": pos.x(),
        "y": pos.y(),
    }

    # Only include node_type if not "pass" (most common)
    if node.node_type != "pass":
        result["node_type"] = node.node_type

    # Only include optional fields if they have values
    if node.name:
        result["name"] = node.name

    if params:
        result["params"] = params

    # Only save size if changed from default
    if node._width != node.DEFAULT_WIDTH:
        result["width"] = node._width

    if node._height_override is not None:
        result["height"] = node._height_override

    # Save dynamic input sockets for nodes with has_dynamic_inputs
    # This ensures we can restore sockets before materials are loaded
    pass_class = node.data.get("pass_class")
    if pass_class == "MaterialPass":
        # Get dynamic sockets (exclude static ones like output_res_target)
        static_sockets = {"output_res_target"}
        dynamic_inputs = []
        for sock in node.input_sockets:
            if sock.name not in static_sockets:
                dynamic_inputs.append((sock.name, sock.socket_type))
        if dynamic_inputs:
            result["dynamic_inputs"] = dynamic_inputs
    elif pass_class == "ColorPass":
        # Get dynamic sockets (exclude static ones)
        static_sockets = {"input_res", "shadow_res", "output_res_target"}
        dynamic_inputs = []
        for sock in node.input_sockets:
            if sock.name not in static_sockets:
                dynamic_inputs.append((sock.name, sock.socket_type))
        if dynamic_inputs:
            result["dynamic_inputs"] = dynamic_inputs

    return result


def _serialize_connection(conn: "NodeConnection", node_to_index: dict) -> dict:
    """Serialize a connection between nodes."""
    start = conn.start_socket
    end = conn.end_socket

    if start is None or end is None or start.node is None or end.node is None:
        return None

    from_index = node_to_index.get(start.node)
    to_index = node_to_index.get(end.node)

    if from_index is None or to_index is None:
        return None

    return {
        "from_node": from_index,
        "from_socket": start.name,
        "to_node": to_index,
        "to_socket": end.name,
    }


def _serialize_viewport_frame(frame: "ViewportFrame") -> dict:
    """Serialize a viewport frame."""
    # Combine pos() and rect() for absolute position
    pos = frame.pos()
    rect = frame.rect()
    return {
        "title": frame.title,
        "viewport_name": frame.viewport_name,
        "x": pos.x() + rect.x(),
        "y": pos.y() + rect.y(),
        "width": rect.width(),
        "height": rect.height(),
    }


def deserialize_graph(data: dict, scene: "NodeGraphScene") -> None:
    """
    Deserialize a graph from dictionary into a scene.

    Clears the existing scene and populates it with deserialized nodes.

    Args:
        data: Serialized graph data
        scene: Target scene to populate
    """
    from termin.nodegraph.nodes import create_node
    from termin.nodegraph.viewport_frame import ViewportFrame
    from termin.nodegraph.connection import NodeConnection

    # Clear existing
    scene.clear_graph()

    # List of nodes by index
    nodes_list: List["GraphNode"] = []

    # Create viewport frames first
    for frame_data in data.get("viewport_frames", []):
        frame = ViewportFrame(
            title=frame_data.get("title", "Viewport"),
            viewport_name=frame_data.get("viewport_name", "main"),
            x=frame_data.get("x", 0),
            y=frame_data.get("y", 0),
            width=frame_data.get("width", 600),
            height=frame_data.get("height", 400),
        )
        scene.add_viewport_frame(frame)

    # Create nodes
    for node_data in data.get("nodes", []):
        node_type = node_data.get("node_type", "pass")
        title = node_data.get("type", "Node")

        # Create node using factory
        node = create_node(node_type, title)

        # Restore instance name
        node.name = node_data.get("name", "")

        # Set position
        node.setPos(node_data.get("x", 0), node_data.get("y", 0))

        # Set size if overridden
        width = node_data.get("width")
        if width is not None:
            node._width = width

        height = node_data.get("height")
        if height is not None:
            node._height_override = height
            node._update_height()

        # Restore dynamic inputs BEFORE setting params (to avoid material lookup)
        # This ensures sockets exist for connection restoration
        dynamic_inputs = node_data.get("dynamic_inputs")
        if dynamic_inputs:
            # Determine static sockets based on node type
            pass_class = node.data.get("pass_class")
            if pass_class == "ColorPass":
                keep_sockets = {"input_res", "shadow_res", "output_res_target"}
            else:
                keep_sockets = {"output_res_target"}

            # Use update_dynamic_inputs to create sockets
            node.update_dynamic_inputs(
                dynamic_inputs,
                keep_sockets=keep_sockets,
            )
            # Mark that we restored from serialization (skip material lookup)
            node._dynamic_inputs_restored = True

        # Set parameters
        params = node_data.get("params", {})
        for name, value in params.items():
            node.set_param(name, value)

        # Clear the flag after params are set
        if hasattr(node, "_dynamic_inputs_restored"):
            del node._dynamic_inputs_restored

        scene.add_node(node)
        nodes_list.append(node)

    # Create connections
    for conn_data in data.get("connections", []):
        if conn_data is None:
            continue

        from_node_idx = conn_data.get("from_node")
        from_socket_name = conn_data.get("from_socket")
        to_node_idx = conn_data.get("to_node")
        to_socket_name = conn_data.get("to_socket")

        # Get nodes by index
        if from_node_idx is None or to_node_idx is None:
            continue
        if from_node_idx >= len(nodes_list) or to_node_idx >= len(nodes_list):
            continue

        from_node = nodes_list[from_node_idx]
        to_node = nodes_list[to_node_idx]

        # Find sockets
        from_socket = None
        for sock in from_node.output_sockets:
            if sock.name == from_socket_name:
                from_socket = sock
                break

        to_socket = None
        for sock in to_node.input_sockets:
            if sock.name == to_socket_name:
                to_socket = sock
                break

        if from_socket is None or to_socket is None:
            continue

        # Create connection
        conn = NodeConnection()
        conn.set_start_socket(from_socket)
        conn.set_end_socket(to_socket)
        scene.add_connection(conn)
