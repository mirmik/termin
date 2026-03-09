"""NodeGraphScene - QGraphicsScene for the node graph."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, List

from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QColor, QPen, QBrush, QPainter
from PyQt6.QtWidgets import QGraphicsScene

from termin.nodegraph.node import GraphNode
from termin.nodegraph.socket import NodeSocket
from termin.nodegraph.connection import NodeConnection

if TYPE_CHECKING:
    from termin.nodegraph.viewport_frame import ViewportFrame


class NodeGraphScene(QGraphicsScene):
    """
    Scene for the node graph editor.

    Manages nodes, connections, and the grid background.
    """

    # Grid settings
    GRID_SIZE = 20
    GRID_COLOR_LIGHT = QColor(55, 55, 55)
    GRID_COLOR_DARK = QColor(45, 45, 45)
    BG_COLOR = QColor(38, 38, 38)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Scene size
        self.setSceneRect(-5000, -5000, 10000, 10000)
        self.setBackgroundBrush(QBrush(self.BG_COLOR))

        # Track nodes, connections and viewport frames
        self._nodes: List[GraphNode] = []
        self._connections: List[NodeConnection] = []
        self._viewport_frames: List["ViewportFrame"] = []

        # Connection being dragged
        self._drag_connection: Optional[NodeConnection] = None
        self._drag_start_socket: Optional[NodeSocket] = None

    def drawBackground(self, painter: QPainter, rect) -> None:
        """Draw grid background."""
        super().drawBackground(painter, rect)

        # Calculate grid bounds
        left = int(rect.left()) - (int(rect.left()) % self.GRID_SIZE)
        top = int(rect.top()) - (int(rect.top()) % self.GRID_SIZE)

        # Draw small grid
        painter.setPen(QPen(self.GRID_COLOR_LIGHT, 0.5))
        for x in range(left, int(rect.right()), self.GRID_SIZE):
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
        for y in range(top, int(rect.bottom()), self.GRID_SIZE):
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)

        # Draw large grid
        large_grid = self.GRID_SIZE * 5
        left = int(rect.left()) - (int(rect.left()) % large_grid)
        top = int(rect.top()) - (int(rect.top()) % large_grid)

        painter.setPen(QPen(self.GRID_COLOR_DARK, 1))
        for x in range(left, int(rect.right()), large_grid):
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
        for y in range(top, int(rect.bottom()), large_grid):
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)

    def add_node(self, node: GraphNode) -> None:
        """Add a node to the scene."""
        self.addItem(node)
        self._nodes.append(node)

    def remove_node(self, node: GraphNode) -> None:
        """Remove a node and its connections from the scene."""
        # Remove all connections
        for socket in node.input_sockets + node.output_sockets:
            for connection in socket.connections[:]:
                connection.remove()

        # Remove node
        if node in self._nodes:
            self._nodes.remove(node)
        self.removeItem(node)

    def add_connection(self, connection: NodeConnection) -> None:
        """Add a connection to the scene."""
        self.addItem(connection)
        self._connections.append(connection)

    def remove_connection(self, connection: NodeConnection) -> None:
        """Remove a connection from the scene."""
        if connection in self._connections:
            self._connections.remove(connection)
        connection.remove()

    def get_nodes(self) -> List[GraphNode]:
        """Get all nodes in the scene."""
        return self._nodes.copy()

    def get_connections(self) -> List[NodeConnection]:
        """Get all connections in the scene."""
        return self._connections.copy()

    def add_viewport_frame(self, frame: "ViewportFrame") -> None:
        """Add a viewport frame to the scene."""
        self.addItem(frame)
        self._viewport_frames.append(frame)

    def remove_viewport_frame(self, frame: "ViewportFrame") -> None:
        """Remove a viewport frame from the scene."""
        if frame in self._viewport_frames:
            self._viewport_frames.remove(frame)
        self.removeItem(frame)

    def get_viewport_frames(self) -> List["ViewportFrame"]:
        """Get all viewport frames in the scene."""
        return self._viewport_frames.copy()

    def start_connection_drag(self, socket: NodeSocket, pos: QPointF) -> None:
        """Start dragging a new connection from a socket."""
        self._drag_start_socket = socket
        self._drag_connection = NodeConnection()

        if socket.is_input:
            # Dragging from input - connection goes backwards
            self._drag_connection.set_temp_end(pos)
            # We'll set start socket when we find the end
        else:
            # Dragging from output
            self._drag_connection.set_start_socket(socket)
            self._drag_connection.set_temp_end(pos)

        self.addItem(self._drag_connection)

    def update_connection_drag(self, pos: QPointF) -> None:
        """Update the dragged connection position."""
        if self._drag_connection:
            self._drag_connection.set_temp_end(pos)

    def finish_connection_drag(self, end_socket: Optional[NodeSocket]) -> bool:
        """
        Finish the connection drag.

        Returns True if connection was created.
        """
        if not self._drag_connection or not self._drag_start_socket:
            self._cancel_connection_drag()
            return False

        if not end_socket:
            self._cancel_connection_drag()
            return False

        # Check if connection is valid
        if not self._drag_start_socket.can_connect_to(end_socket):
            self._cancel_connection_drag()
            return False

        # Determine which is input and which is output
        if self._drag_start_socket.is_input:
            input_socket = self._drag_start_socket
            output_socket = end_socket
        else:
            input_socket = end_socket
            output_socket = self._drag_start_socket

        # Create the final connection
        self.removeItem(self._drag_connection)

        connection = NodeConnection()
        connection.set_start_socket(output_socket)
        connection.set_end_socket(input_socket)
        self.add_connection(connection)

        self._drag_connection = None
        self._drag_start_socket = None
        return True

    def _cancel_connection_drag(self) -> None:
        """Cancel the current connection drag."""
        if self._drag_connection:
            self.removeItem(self._drag_connection)
            self._drag_connection = None
        self._drag_start_socket = None

    def delete_selected(self) -> None:
        """Delete all selected items."""
        from termin.nodegraph.viewport_frame import ViewportFrame

        for item in self.selectedItems():
            if isinstance(item, GraphNode):
                self.remove_node(item)
            elif isinstance(item, NodeConnection):
                self.remove_connection(item)
            elif isinstance(item, ViewportFrame):
                self.remove_viewport_frame(item)

    def clear_graph(self) -> None:
        """Clear all nodes, connections and viewport frames."""
        for node in self._nodes[:]:
            self.remove_node(node)
        for frame in self._viewport_frames[:]:
            self.remove_viewport_frame(frame)
        self._nodes.clear()
        self._connections.clear()
        self._viewport_frames.clear()
