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
HANDLE_SIZE = 10
PARAM_ROW_HEIGHT = 28


class ViewportFrame(QGraphicsRectItem):
    """
    Visual frame that groups nodes belonging to a viewport.

    Nodes inside the frame automatically inherit:
    - Viewport resolution for FBO sizing
    - Camera reference

    The frame can be resized by dragging edges/corners.
    """

    def __init__(
        self,
        title: str = "Viewport",
        x: float = 0,
        y: float = 0,
        width: float = 600,
        height: float = 400,
    ):
        super().__init__(x, y, width, height)

        self.title = title
        self._min_width = 300
        self._min_height = 200

        # Visual settings
        self._title_height = 30
        self._params_height = PARAM_ROW_HEIGHT * 2  # Two rows of params
        self._header_height = self._title_height + self._params_height
        self._corner_radius = 8
        self._border_color = QColor(100, 150, 200, 200)
        self._fill_color = QColor(60, 80, 100, 40)
        self._title_color = QColor(80, 120, 160, 180)
        self._params_bg_color = QColor(50, 60, 75, 150)

        # Parameters
        self._params: dict[str, Any] = {
            "display": "0",
            "camera": "Main Camera",
            "ndc_x": "0.0",
            "ndc_y": "0.0",
            "ndc_w": "1.0",
            "ndc_h": "1.0",
        }

        # Resize state
        self._resize_edge: Optional[str] = None
        self._resize_start_rect: Optional[QRectF] = None
        self._resize_start_pos: Optional[QPointF] = None

        # Parameter widgets
        self._param_widgets_created = False

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
        y2 = y1 + PARAM_ROW_HEIGHT

        # Row 1: Display and Camera
        painter.drawText(QRectF(rect.x() + 8, y1, 50, 20),
                        Qt.AlignmentFlag.AlignVCenter, "Display")
        painter.drawText(QRectF(rect.x() + 120, y1, 50, 20),
                        Qt.AlignmentFlag.AlignVCenter, "Camera")

        # Row 2: NDC rect
        painter.drawText(QRectF(rect.x() + 8, y2, 30, 20),
                        Qt.AlignmentFlag.AlignVCenter, "NDC")

    def _ensure_param_widgets(self) -> None:
        """Create parameter edit widgets."""
        if self._param_widgets_created:
            return
        self._param_widgets_created = True

        rect = self.rect()
        y1 = rect.y() + self._title_height + 2
        y2 = y1 + PARAM_ROW_HEIGHT

        style = """
            QComboBox, QLineEdit {
                background: #3a3a4a;
                border: 1px solid #555;
                border-radius: 3px;
                color: #ddd;
                padding: 2px 4px;
                font-size: 10px;
            }
            QComboBox::drop-down {
                border: none;
                width: 14px;
            }
            QComboBox::down-arrow {
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #aaa;
            }
        """

        # Display selector
        display_combo = QComboBox()
        display_combo.addItems(["0", "1", "2", "3"])
        display_combo.setCurrentText(self._params["display"])
        display_combo.setFixedSize(50, 20)
        display_combo.setStyleSheet(style)
        display_combo.currentTextChanged.connect(
            lambda v: self._params.__setitem__("display", v)
        )
        proxy1 = QGraphicsProxyWidget(self)
        proxy1.setWidget(display_combo)
        proxy1.setPos(rect.x() + 55, y1)

        # Camera selector
        camera_combo = QComboBox()
        camera_combo.addItems(["Main Camera", "Debug Camera", "Game Camera"])
        camera_combo.setCurrentText(self._params["camera"])
        camera_combo.setFixedSize(120, 20)
        camera_combo.setStyleSheet(style)
        camera_combo.currentTextChanged.connect(
            lambda v: self._params.__setitem__("camera", v)
        )
        proxy2 = QGraphicsProxyWidget(self)
        proxy2.setWidget(camera_combo)
        proxy2.setPos(rect.x() + 170, y1)

        # NDC inputs (x, y, w, h)
        ndc_labels = ["x", "y", "w", "h"]
        ndc_keys = ["ndc_x", "ndc_y", "ndc_w", "ndc_h"]
        x_offset = 40

        for i, (label, key) in enumerate(zip(ndc_labels, ndc_keys)):
            # Small label
            line_edit = QLineEdit()
            line_edit.setText(self._params[key])
            line_edit.setFixedSize(45, 20)
            line_edit.setStyleSheet(style)
            line_edit.setPlaceholderText(label)
            line_edit.textChanged.connect(
                lambda v, k=key: self._params.__setitem__(k, v)
            )
            proxy = QGraphicsProxyWidget(self)
            proxy.setWidget(line_edit)
            proxy.setPos(rect.x() + x_offset + i * 55, y2)

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
        edge = self.get_resize_edge(event.pos())

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
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

        super().hoverMoveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Start resize if on edge."""
        if event.button() == Qt.MouseButton.LeftButton:
            edge = self.get_resize_edge(event.pos())
            if edge:
                self._resize_edge = edge
                self._resize_start_rect = QRectF(self.rect())
                self._resize_start_pos = event.scenePos()
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Handle resize drag."""
        if self._resize_edge and self._resize_start_rect and self._resize_start_pos:
            delta = event.scenePos() - self._resize_start_pos
            new_rect = QRectF(self._resize_start_rect)

            edge = self._resize_edge

            # Adjust rect based on which edge is being dragged
            if 'l' in edge:  # left
                new_left = new_rect.left() + delta.x()
                if new_rect.right() - new_left >= self._min_width:
                    new_rect.setLeft(new_left)

            if 'r' in edge:  # right
                new_right = new_rect.right() + delta.x()
                if new_right - new_rect.left() >= self._min_width:
                    new_rect.setRight(new_right)

            if 't' in edge:  # top
                new_top = new_rect.top() + delta.y()
                if new_rect.bottom() - new_top >= self._min_height:
                    new_rect.setTop(new_top)

            if 'b' in edge:  # bottom
                new_bottom = new_rect.bottom() + delta.y()
                if new_bottom - new_rect.top() >= self._min_height:
                    new_rect.setBottom(new_bottom)

            self.setRect(new_rect)
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
