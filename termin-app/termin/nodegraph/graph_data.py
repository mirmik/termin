"""Pure data structures for render graph representation.

These classes contain no Qt dependencies and can be used for:
- Serialization/deserialization
- Compilation to RenderPipeline
- Transfer to C++ for compilation

The Qt NodeGraphScene uses these for storage and serializes to/from them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SocketData:
    """Data for a node socket (input or output)."""
    name: str
    socket_type: str  # "fbo", "shadow", "texture", etc.
    is_input: bool


@dataclass
class NodeData:
    """Data for a graph node."""
    id: str  # Unique node ID
    node_type: str  # "pass", "resource", "output"
    pass_class: str  # For pass nodes: class name like "ColorPass"
    name: str  # Instance name (shown in header)
    params: Dict[str, Any] = field(default_factory=dict)
    inputs: List[SocketData] = field(default_factory=list)
    outputs: List[SocketData] = field(default_factory=list)

    # Position in graph (for UI, not used in compilation)
    x: float = 0.0
    y: float = 0.0


@dataclass
class ConnectionData:
    """Data for a connection between sockets."""
    from_node_id: str
    from_socket: str  # Socket name
    to_node_id: str
    to_socket: str  # Socket name


@dataclass
class ViewportFrameData:
    """Data for a viewport frame (groups nodes for a viewport)."""
    viewport_name: str
    x: float = 0.0
    y: float = 0.0
    width: float = 400.0
    height: float = 300.0


@dataclass
class GraphData:
    """Complete graph data for compilation."""
    nodes: List[NodeData] = field(default_factory=list)
    connections: List[ConnectionData] = field(default_factory=list)
    viewport_frames: List[ViewportFrameData] = field(default_factory=list)

    def get_node(self, node_id: str) -> Optional[NodeData]:
        """Find node by ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def get_connections_to(self, node_id: str, socket_name: str) -> List[ConnectionData]:
        """Get all connections to a specific input socket."""
        return [c for c in self.connections
                if c.to_node_id == node_id and c.to_socket == socket_name]

    def get_connections_from(self, node_id: str, socket_name: str) -> List[ConnectionData]:
        """Get all connections from a specific output socket."""
        return [c for c in self.connections
                if c.from_node_id == node_id and c.from_socket == socket_name]

    @classmethod
    def from_dict(cls, data: dict) -> "GraphData":
        """Deserialize from dict (JSON-compatible format).

        Supports the existing serialization format where:
        - "type" is the pass class name (e.g., "ColorPass")
        - "node_type" is optional, defaults to "pass"
        - Connections use node indices, not IDs
        - Sockets are inferred from pass class registry
        """
        from termin.nodegraph.pass_registry import get_pass_sockets

        nodes = []
        for i, node_data in enumerate(data.get("nodes", [])):
            # "type" contains the pass class name like "ColorPass"
            pass_class = node_data.get("type", "")
            # "node_type" is the category: "pass", "resource", "output"
            node_type = node_data.get("node_type", "pass")

            # Get sockets from pass registry or dynamic_inputs in data
            inputs = []
            outputs = []
            if node_type == "pass" and pass_class:
                node_inputs, node_outputs = get_pass_sockets(pass_class)
                inputs = [
                    SocketData(name=name, socket_type=stype, is_input=True)
                    for name, stype in node_inputs
                ]
                outputs = [
                    SocketData(name=name, socket_type=stype, is_input=False)
                    for name, stype in node_outputs
                ]
                # Add dynamic inputs from serialized data
                for dyn_name, dyn_type in node_data.get("dynamic_inputs", []):
                    if not any(s.name == dyn_name for s in inputs):
                        inputs.append(SocketData(name=dyn_name, socket_type=dyn_type, is_input=True))
            elif node_type == "resource":
                # Resource nodes have single output named "fbo" (matches serialization format)
                outputs = [SocketData(name="fbo", socket_type="fbo", is_input=False)]

            nodes.append(NodeData(
                id=str(i),  # Use index as ID since serialization uses indices
                node_type=node_type,
                pass_class=pass_class,
                name=node_data.get("name", ""),
                params=node_data.get("params", {}),
                inputs=inputs,
                outputs=outputs,
                x=node_data.get("x", 0.0),
                y=node_data.get("y", 0.0),
            ))

        # Connections use node indices
        connections = [
            ConnectionData(
                from_node_id=str(c.get("from_node", 0)),
                from_socket=c.get("from_socket", ""),
                to_node_id=str(c.get("to_node", 0)),
                to_socket=c.get("to_socket", ""),
            )
            for c in data.get("connections", [])
        ]

        viewport_frames = [
            ViewportFrameData(
                viewport_name=vf.get("viewport_name", ""),
                x=vf.get("x", 0.0),
                y=vf.get("y", 0.0),
                width=vf.get("width", 400.0),
                height=vf.get("height", 300.0),
            )
            for vf in data.get("viewport_frames", [])
        ]

        return cls(nodes=nodes, connections=connections, viewport_frames=viewport_frames)

    def to_dict(self) -> dict:
        """Serialize to dict (JSON-compatible format)."""
        return {
            "nodes": [
                {
                    "id": n.id,
                    "type": n.node_type,
                    "pass_class": n.pass_class,
                    "name": n.name,
                    "params": n.params,
                    "inputs": [
                        {"name": s.name, "socket_type": s.socket_type}
                        for s in n.inputs
                    ],
                    "outputs": [
                        {"name": s.name, "socket_type": s.socket_type}
                        for s in n.outputs
                    ],
                    "x": n.x,
                    "y": n.y,
                }
                for n in self.nodes
            ],
            "connections": [
                {
                    "from_node": c.from_node_id,
                    "from_socket": c.from_socket,
                    "to_node": c.to_node_id,
                    "to_socket": c.to_socket,
                }
                for c in self.connections
            ],
            "viewport_frames": [
                {
                    "viewport_name": vf.viewport_name,
                    "x": vf.x,
                    "y": vf.y,
                    "width": vf.width,
                    "height": vf.height,
                }
                for vf in self.viewport_frames
            ],
        }
