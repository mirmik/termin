"""NodeSocket - connection points on nodes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, List

from PyQt6.QtGui import QColor

if TYPE_CHECKING:
    from termin.nodegraph.node import GraphNode
    from termin.nodegraph.connection import NodeConnection


class NodeSocket:
    """
    A connection point on a node.

    Sockets can be inputs (left side) or outputs (right side).
    Each socket has a data type that determines compatible connections.
    """

    # Socket type colors
    TYPE_COLORS = {
        "fbo": QColor(100, 180, 100),       # Green - framebuffer
        "texture": QColor(180, 150, 100),   # Orange - texture
        "shadow": QColor(80, 80, 120),      # Purple - shadow maps
        "any": QColor(150, 150, 150),       # Gray - any type
        "flow": QColor(200, 200, 200),      # White - execution flow
    }

    def __init__(
        self,
        name: str,
        socket_type: str = "any",
        multi: bool = False,
    ):
        """
        Args:
            name: Display name of the socket
            socket_type: Data type ("fbo", "texture", "shadow", "any")
            multi: Whether multiple connections are allowed
        """
        self.name = name
        self.socket_type = socket_type
        self.multi = multi

        # Set by parent node
        self.node: Optional[GraphNode] = None
        self.is_input: bool = True
        self.index: int = 0

        # Connections
        self.connections: List[NodeConnection] = []

    @property
    def color(self) -> QColor:
        """Get socket color based on type."""
        return self.TYPE_COLORS.get(self.socket_type, self.TYPE_COLORS["any"])

    def can_connect_to(self, other: "NodeSocket") -> bool:
        """Check if this socket can connect to another."""
        # Can't connect to same node
        if self.node is other.node:
            return False

        # Can't connect input to input or output to output
        if self.is_input == other.is_input:
            return False

        # Check type compatibility
        if self.socket_type == "any" or other.socket_type == "any":
            return True

        return self.socket_type == other.socket_type

    def add_connection(self, connection: "NodeConnection") -> None:
        """Add a connection to this socket."""
        if not self.multi:
            # Remove existing connections for single-connection sockets
            for conn in self.connections[:]:
                conn.remove()
        self.connections.append(connection)

    def remove_connection(self, connection: "NodeConnection") -> None:
        """Remove a connection from this socket."""
        if connection in self.connections:
            self.connections.remove(connection)

    def is_connected(self) -> bool:
        """Check if socket has any connections."""
        return len(self.connections) > 0
