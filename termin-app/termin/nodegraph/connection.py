"""NodeConnection - visual connection between sockets."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QPainterPath
from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsItem, QStyleOptionGraphicsItem, QWidget

if TYPE_CHECKING:
    from termin.nodegraph.socket import NodeSocket
    from termin.nodegraph.scene import NodeGraphScene


class NodeConnection(QGraphicsPathItem):
    """
    Visual connection (edge) between two sockets.

    Draws a bezier curve from output socket to input socket.
    """

    COLOR_DEFAULT = QColor(150, 150, 150)
    COLOR_HOVER = QColor(200, 200, 100)
    COLOR_SELECTED = QColor(255, 180, 50)
    LINE_WIDTH = 2.5

    def __init__(
        self,
        start_socket: Optional["NodeSocket"] = None,
        end_socket: Optional["NodeSocket"] = None,
        parent: Optional[QGraphicsItem] = None,
    ):
        super().__init__(parent)

        self.start_socket = start_socket
        self.end_socket = end_socket

        # Temporary end point for dragging
        self._temp_end: Optional[QPointF] = None

        # Setup
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setZValue(-1)  # Draw behind nodes

        self.update_path()

    def set_start_socket(self, socket: "NodeSocket") -> None:
        """Set the start socket."""
        self.start_socket = socket
        self.update_path()

    def set_end_socket(self, socket: "NodeSocket") -> None:
        """Set the end socket and finalize connection."""
        self.end_socket = socket
        self._temp_end = None

        # Register connection with both sockets
        if self.start_socket:
            self.start_socket.add_connection(self)
        if self.end_socket:
            self.end_socket.add_connection(self)

        self.update_path()

    def set_temp_end(self, pos: QPointF) -> None:
        """Set temporary end point (while dragging)."""
        self._temp_end = pos
        self.update_path()

    def update_path(self) -> None:
        """Recalculate the bezier path."""
        path = QPainterPath()

        # Get start position
        if self.start_socket and self.start_socket.node:
            start = self.start_socket.node.get_socket_pos(self.start_socket)
        else:
            start = QPointF(0, 0)

        # Get end position
        if self.end_socket and self.end_socket.node:
            end = self.end_socket.node.get_socket_pos(self.end_socket)
        elif self._temp_end:
            end = self._temp_end
        else:
            end = start

        # Calculate control points for bezier curve
        dx = abs(end.x() - start.x()) * 0.5
        dx = max(dx, 50)  # Minimum curve distance

        ctrl1 = QPointF(start.x() + dx, start.y())
        ctrl2 = QPointF(end.x() - dx, end.y())

        # Build path
        path.moveTo(start)
        path.cubicTo(ctrl1, ctrl2, end)

        self.setPath(path)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        # Determine color
        if self.isSelected():
            color = self.COLOR_SELECTED
        else:
            # Use socket type color if available
            if self.start_socket:
                color = self.start_socket.color
            else:
                color = self.COLOR_DEFAULT

        pen = QPen(color, self.LINE_WIDTH)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self.path())

    def remove(self) -> None:
        """Remove this connection from both sockets and scene."""
        if self.start_socket:
            self.start_socket.remove_connection(self)
        if self.end_socket:
            self.end_socket.remove_connection(self)

        scene = self.scene()
        if scene:
            scene.removeItem(self)

    def get_other_socket(self, socket: "NodeSocket") -> Optional["NodeSocket"]:
        """Get the socket on the other end of this connection."""
        if socket == self.start_socket:
            return self.end_socket
        if socket == self.end_socket:
            return self.start_socket
        return None
