"""ViewportFrame - visual container that defines viewport context for nodes."""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Any

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QColor, QPen, QBrush, QFont, QPainter, QPainterPath
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsProxyWidget,
    QStyleOptionGraphicsItem,
    QWidget,
    QGraphicsSceneMouseEvent,
    QComboBox,
    QLineEdit,
    QLabel,
    QHBoxLayout,
    QFrame,
)

if TYPE_CHECKING:
    from termin.nodegraph.node import GraphNode


# Resize handle size
HANDLE_SIZE = 12
PARAM_ROW_HEIGHT = 28


class ViewportFrame(QGraphicsRectItem):
    """
    Visual frame that groups nodes belonging to a viewport.

    Nodes inside the frame automatically inherit the viewport context:
    - Passes get viewport_name for resolution and camera
    - Resources get viewport_name for size mode

    The frame can be resized by dragging edges/corners.
    """

    def __init__(
        self,
        title: str = "Viewport",
        viewport_name: str = "main",
        x: float = 0,
        y: float = 0,
        width: float = 600,
        height: float = 400,
    ):
        super().__init__(x, y, width, height)

        self.title = title
        self.viewport_name = viewport_name
        self._min_width = 300
        self._min_height = 150

        # Visual settings
        self._title_height = 30
        self._params_height = PARAM_ROW_HEIGHT  # One row for viewport selector
        self._header_height = self._title_height + self._params_height
        self._corner_radius = 8
        self._border_color = QColor(100, 150, 200, 200)
        self._fill_color = QColor(60, 80, 100, 40)
        self._title_color = QColor(80, 120, 160, 180)
        self._params_bg_color = QColor(50, 60, 75, 150)

        # Resize state
        self._resize_edge: Optional[str] = None
        self._resize_start_rect: Optional[QRectF] = None
        self._resize_start_pos: Optional[QPointF] = None

        # Parameter widgets
        self._param_widgets_created = False
        self._viewport_input: Optional[QLineEdit] = None
        self._viewport_proxy: Optional[QGraphicsProxyWidget] = None

        # Make selectable and movable
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

        # Draw behind nodes
        self.setZValue(-100)

        # Accept hover for resize cursor
        self.setAcceptHoverEvents(True)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        """Draw the viewport frame."""
        rect = self.rect()

        # Background
        path = QPainterPath()
        path.addRoundedRect(rect, self._corner_radius, self._corner_radius)

        painter.fillPath(path, QBrush(self._fill_color))

        # Border
        pen_width = 3 if self.isSelected() else 2
        pen = QPen(self._border_color, pen_width)
        if self.isSelected():
            pen.setColor(QColor(150, 200, 255, 255))
        painter.setPen(pen)
        painter.drawPath(path)

        # Title bar
        title_rect = QRectF(
            rect.x(),
            rect.y(),
            rect.width(),
            self._title_height,
        )
        title_path = QPainterPath()
        title_path.addRoundedRect(
            title_rect.adjusted(2, 2, -2, 0),
            self._corner_radius - 2,
            self._corner_radius - 2,
        )
        painter.fillPath(title_path, QBrush(self._title_color))

        # Title text
        painter.setPen(QPen(QColor(220, 230, 240)))
        font = QFont("Segoe UI", 11, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(
            title_rect.adjusted(12, 0, -12, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self.title,
        )

        # Parameters background
        params_rect = QRectF(
            rect.x() + 2,
            rect.y() + self._title_height,
            rect.width() - 4,
            self._params_height,
        )
        painter.fillRect(params_rect, QBrush(self._params_bg_color))

        # Draw parameter labels
        self._draw_param_labels(painter, rect)

        # Ensure param widgets exist
        self._ensure_param_widgets()

    def _draw_param_labels(self, painter: QPainter, rect: QRectF) -> None:
        """Draw parameter labels."""
        font = QFont("Segoe UI", 9)
        painter.setFont(font)
        painter.setPen(QPen(QColor(180, 190, 200)))

        y1 = rect.y() + self._title_height + 4

        # Viewport name label
        painter.drawText(QRectF(rect.x() + 8, y1, 60, 20),
                        Qt.AlignmentFlag.AlignVCenter, "Viewport")

    def _ensure_param_widgets(self) -> None:
        """Create parameter edit widgets."""
        if self._param_widgets_created:
            return
        self._param_widgets_created = True

        rect = self.rect()
        y1 = rect.y() + self._title_height + 2

        style = """
            QLineEdit {
                background: #3a3a4a;
                border: 1px solid #555;
                border-radius: 3px;
                color: #ddd;
                padding: 2px 4px;
                font-size: 10px;
            }
        """

        # Viewport name input
        viewport_input = QLineEdit()
        viewport_input.setText(self.viewport_name)
        viewport_input.setFixedSize(150, 20)
        viewport_input.setStyleSheet(style)
        viewport_input.setPlaceholderText("viewport name")
        viewport_input.textChanged.connect(self._on_viewport_name_changed)

        self._viewport_input = viewport_input

        proxy = QGraphicsProxyWidget(self)
        proxy.setWidget(viewport_input)
        proxy.setPos(rect.x() + 70, y1)
        self._viewport_proxy = proxy

    def _on_viewport_name_changed(self, value: str) -> None:
        """Handle viewport name change."""
        self.viewport_name = value

    def _update_param_widget_positions(self) -> None:
        """Update parameter widget positions after rect change."""
        if self._viewport_proxy is None:
            return
        rect = self.rect()
        y1 = rect.y() + self._title_height + 2
        self._viewport_proxy.setPos(rect.x() + 70, y1)

    def get_resize_edge(self, pos: QPointF) -> Optional[str]:
        """Determine which edge/corner is under the cursor."""
        rect = self.rect()
        x, y = pos.x(), pos.y()

        on_left = abs(x - rect.left()) < HANDLE_SIZE
        on_right = abs(x - rect.right()) < HANDLE_SIZE
        on_top = abs(y - rect.top()) < HANDLE_SIZE
        on_bottom = abs(y - rect.bottom()) < HANDLE_SIZE

        # Corners
        if on_top and on_left:
            return 'tl'
        if on_top and on_right:
            return 'tr'
        if on_bottom and on_left:
            return 'bl'
        if on_bottom and on_right:
            return 'br'

        # Edges (but not in header area for top)
        if on_left:
            return 'left'
        if on_right:
            return 'right'
        if on_top and y > rect.top() + self._header_height:
            return 'top'
        if on_bottom:
            return 'bottom'

        return None

    def hoverMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Update cursor based on position."""
        pos = event.pos()
        edge = self.get_resize_edge(pos)

        cursor_map = {
            'left': Qt.CursorShape.SizeHorCursor,
            'right': Qt.CursorShape.SizeHorCursor,
            'top': Qt.CursorShape.SizeVerCursor,
            'bottom': Qt.CursorShape.SizeVerCursor,
            'tl': Qt.CursorShape.SizeFDiagCursor,
            'br': Qt.CursorShape.SizeFDiagCursor,
            'tr': Qt.CursorShape.SizeBDiagCursor,
            'bl': Qt.CursorShape.SizeBDiagCursor,
        }

        if edge in cursor_map:
            self.setCursor(cursor_map[edge])
        elif self._is_in_header(pos):
            # Show open hand in header to indicate draggable
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            # Body area - default cursor
            self.unsetCursor()

        super().hoverMoveEvent(event)

    def _is_in_header(self, pos: QPointF) -> bool:
        """Check if position is in the header area (title + params)."""
        rect = self.rect()
        header_bottom = rect.top() + self._header_height
        return (rect.left() <= pos.x() <= rect.right() and
                rect.top() <= pos.y() <= header_bottom)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Handle mouse press - drag only from header, resize from edges."""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()

            # Check resize edge first
            edge = self.get_resize_edge(pos)
            if edge:
                self._resize_edge = edge
                self._resize_start_rect = QRectF(self.rect())
                self._resize_start_pos = event.scenePos()
                event.accept()
                return

            # Only handle if clicking on header - allow drag/selection
            if self._is_in_header(pos):
                super().mousePressEvent(event)
                return

            # Clicking on body area - ignore to allow rubber band selection
            event.ignore()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Handle resize drag."""
        if self._resize_edge and self._resize_start_rect and self._resize_start_pos:
            delta = event.scenePos() - self._resize_start_pos
            new_rect = QRectF(self._resize_start_rect)

            edge = self._resize_edge

            # Adjust rect based on which edge is being dragged
            # Use explicit edge names to avoid substring matching bugs
            # (e.g., 't' in 'bottom' was True!)
            adjust_left = edge in ('left', 'tl', 'bl')
            adjust_right = edge in ('right', 'tr', 'br')
            adjust_top = edge in ('top', 'tl', 'tr')
            adjust_bottom = edge in ('bottom', 'bl', 'br')

            if adjust_left:
                new_left = new_rect.left() + delta.x()
                if new_rect.right() - new_left >= self._min_width:
                    new_rect.setLeft(new_left)

            if adjust_right:
                new_right = new_rect.right() + delta.x()
                if new_right - new_rect.left() >= self._min_width:
                    new_rect.setRight(new_right)

            if adjust_top:
                new_top = new_rect.top() + delta.y()
                if new_rect.bottom() - new_top >= self._min_height:
                    new_rect.setTop(new_top)

            if adjust_bottom:
                new_bottom = new_rect.bottom() + delta.y()
                if new_bottom - new_rect.top() >= self._min_height:
                    new_rect.setBottom(new_bottom)

            self.prepareGeometryChange()
            self.setRect(new_rect)
            self._update_param_widget_positions()
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """End resize."""
        if self._resize_edge:
            self._resize_edge = None
            self._resize_start_rect = None
            self._resize_start_pos = None
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def get_contained_nodes(self) -> List["GraphNode"]:
        """Get all GraphNode items inside this frame."""
        from termin.nodegraph.node import GraphNode

        frame_rect = self.sceneBoundingRect()
        contained = []

        if self.scene() is None:
            return contained

        for item in self.scene().items():
            if isinstance(item, GraphNode):
                # Check if node center is inside frame
                node_center = item.sceneBoundingRect().center()
                if frame_rect.contains(node_center):
                    contained.append(item)

        return contained

    def boundingRect(self) -> QRectF:
        """Extend bounding rect for resize handles."""
        rect = self.rect()
        return rect.adjusted(-HANDLE_SIZE, -HANDLE_SIZE, HANDLE_SIZE, HANDLE_SIZE)
