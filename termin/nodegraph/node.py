"""GraphNode - visual node representation using QGraphicsItem."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, List, Dict, Any, Callable

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QFontMetrics
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsTextItem,
    QGraphicsProxyWidget,
    QStyleOptionGraphicsItem,
    QWidget,
    QComboBox,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QMenu,
    QInputDialog,
)

if TYPE_CHECKING:
    from termin.nodegraph.socket import NodeSocket
    from termin.nodegraph.scene import NodeGraphScene


@dataclass
class NodeParam:
    """Parameter definition for a node."""
    name: str
    label: str
    param_type: str  # "choice", "text", "int", "float", "bool"
    default: Any = None
    choices: List[str] = field(default_factory=list)  # For "choice" type
    min_val: float = 0.0
    max_val: float = 100.0
    # Conditional visibility: {"param_name": "value"} - show when param_name == value
    visible_when: Dict[str, Any] = field(default_factory=dict)


class _NodeComboBox(QComboBox):
    """ComboBox that raises parent node z-value when dropdown is shown."""

    def __init__(self, node: "GraphNode", parent=None):
        super().__init__(parent)
        self._node = node
        self._proxy: QGraphicsProxyWidget | None = None
        self._saved_node_z = 0.0
        self._saved_proxy_z = 0.0

    def set_proxy(self, proxy: QGraphicsProxyWidget) -> None:
        """Set the proxy widget for z-order management."""
        self._proxy = proxy

    def showPopup(self):
        # Raise the node to top when showing dropdown
        self._saved_node_z = self._node.zValue()
        self._node.setZValue(10000)

        # Also raise the proxy widget within the node
        if self._proxy is not None:
            self._saved_proxy_z = self._proxy.zValue()
            self._proxy.setZValue(10000)

        super().showPopup()

    def hidePopup(self):
        super().hidePopup()
        # Restore z-values
        self._node.setZValue(self._saved_node_z)
        if self._proxy is not None:
            self._proxy.setZValue(self._saved_proxy_z)


class GraphNode(QGraphicsItem):
    """
    Visual representation of a node in the graph.

    Each node has:
    - Title bar with node name
    - Input sockets (left side)
    - Output sockets (right side)
    - Optional content area
    """

    # Visual settings
    DEFAULT_WIDTH = 180
    MIN_WIDTH = 140
    TITLE_HEIGHT = 28
    SOCKET_SPACING = 24
    SOCKET_RADIUS = 8
    CORNER_RADIUS = 6
    PADDING = 10
    PARAM_HEIGHT = 26
    RESIZE_HANDLE_SIZE = 12

    # Colors
    COLOR_TITLE_BG = QColor(60, 60, 80)
    COLOR_BODY_BG = QColor(45, 45, 55)
    COLOR_BORDER = QColor(30, 30, 35)
    COLOR_BORDER_SELECTED = QColor(255, 180, 50)
    COLOR_TITLE_TEXT = QColor(220, 220, 220)

    def __init__(
        self,
        title: str = "Node",
        node_type: str = "default",
        parent: Optional[QGraphicsItem] = None,
    ):
        super().__init__(parent)

        self.title = title  # Node type name (e.g., "ColorPass")
        self.name = ""  # User-defined instance name
        self.node_type = node_type

        self.input_sockets: List[NodeSocket] = []
        self.output_sockets: List[NodeSocket] = []

        # Parameters
        self._params: List[NodeParam] = []
        self._param_values: dict[str, Any] = {}
        self._param_widgets: dict[str, QGraphicsProxyWidget] = {}

        # Node data (for pipeline compilation)
        self.data: dict = {}

        # Resizable dimensions
        self._width = self.DEFAULT_WIDTH
        self._height_override: float | None = None  # None = auto-calculated
        self._resizing = False
        self._resize_start_pos: QPointF | None = None
        self._resize_start_width = 0.0
        self._resize_start_height = 0.0

        # Setup flags
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)

        self._update_height()

    def _update_height(self) -> None:
        """Recalculate node height based on sockets and visible parameters."""
        socket_count = max(len(self.input_sockets), len(self.output_sockets), 1)
        socket_height = socket_count * self.SOCKET_SPACING
        visible_param_count = len(self._get_visible_params())
        param_height = visible_param_count * self.PARAM_HEIGHT
        content_height = self.TITLE_HEIGHT + socket_height + param_height + self.PADDING

        if self._height_override is not None:
            self._height = max(content_height, self._height_override)
        else:
            self._height = content_height

    def add_input(self, socket: "NodeSocket") -> None:
        """Add input socket."""
        from termin.nodegraph.socket import NodeSocket
        socket.node = self
        socket.is_input = True
        socket.index = len(self.input_sockets)
        self.input_sockets.append(socket)
        self._update_height()
        self.update()

    def add_output(self, socket: "NodeSocket") -> None:
        """Add output socket."""
        from termin.nodegraph.socket import NodeSocket
        socket.node = self
        socket.is_input = False
        socket.index = len(self.output_sockets)
        self.output_sockets.append(socket)
        self._update_height()
        self.update()

    def add_param(self, param: NodeParam) -> None:
        """Add a parameter to the node."""
        self._params.append(param)
        self._param_values[param.name] = param.default
        self._update_height()
        self.update()

    def get_param(self, name: str) -> Any:
        """Get parameter value by name."""
        return self._param_values.get(name)

    def set_param(self, name: str, value: Any) -> None:
        """Set parameter value by name."""
        self._param_values[name] = value
        # Update data dict for pipeline compilation
        self.data[name] = value
        # Update visibility of dependent params
        self._update_param_visibility()

    def _is_param_visible(self, param: NodeParam) -> bool:
        """Check if param should be visible based on visible_when condition."""
        if not param.visible_when:
            return True
        for cond_param, cond_value in param.visible_when.items():
            actual_value = self._param_values.get(cond_param)
            if actual_value != cond_value:
                return False
        return True

    def _get_visible_params(self) -> List[NodeParam]:
        """Get list of currently visible parameters."""
        return [p for p in self._params if self._is_param_visible(p)]

    def _update_param_visibility(self) -> None:
        """Update visibility of param widgets based on conditions."""
        visible_params = self._get_visible_params()

        # Hide all widgets first
        for name, proxy in self._param_widgets.items():
            proxy.setVisible(False)

        # Position and show visible widgets
        socket_section = self._get_socket_section_height()
        widget_width = 100  # Same as in _create_param_widget
        for i, param in enumerate(visible_params):
            if param.name in self._param_widgets:
                proxy = self._param_widgets[param.name]
                y = self.TITLE_HEIGHT + socket_section + i * self.PARAM_HEIGHT + 3
                proxy.setPos(self._width - widget_width - 8, y)
                proxy.setVisible(True)

        # Update node height
        self._update_height()
        self.update()

    def _get_socket_section_height(self) -> float:
        """Get height of the socket section."""
        socket_count = max(len(self.input_sockets), len(self.output_sockets), 1)
        return socket_count * self.SOCKET_SPACING

    def _create_param_widget(self, param: NodeParam, y: float) -> QGraphicsProxyWidget:
        """Create widget for a parameter."""
        proxy = QGraphicsProxyWidget(self)

        # Fixed widget width, positioned from right edge
        widget_width = 100
        widget_x = int(self._width) - widget_width - 8

        # Get current value (may have been set before widget creation)
        current_value = self._param_values.get(param.name, param.default)

        if param.param_type == "choice":
            widget = _NodeComboBox(self)
            widget.addItems(param.choices)
            if current_value in param.choices:
                widget.setCurrentText(current_value)
            elif param.default in param.choices:
                widget.setCurrentText(param.default)
            # Record actual value after selection
            self._param_values[param.name] = widget.currentText()
            widget.currentTextChanged.connect(
                lambda v, n=param.name: self.set_param(n, v)
            )
            # Will set proxy after widget is assigned
            widget.set_proxy(proxy)

        elif param.param_type == "text":
            widget = QLineEdit()
            widget.setText(str(current_value) if current_value is not None else "")
            # Record actual value
            self._param_values[param.name] = widget.text()
            widget.textChanged.connect(
                lambda v, n=param.name: self.set_param(n, v)
            )

        elif param.param_type == "int":
            widget = QSpinBox()
            widget.setRange(int(param.min_val), int(param.max_val))
            widget.setValue(int(current_value) if current_value is not None else 0)
            # Record actual value after clamping
            self._param_values[param.name] = widget.value()
            widget.valueChanged.connect(
                lambda v, n=param.name: self.set_param(n, v)
            )

        elif param.param_type == "float":
            widget = QDoubleSpinBox()
            widget.setRange(param.min_val, param.max_val)
            widget.setValue(float(current_value) if current_value is not None else 0.0)
            # Record actual value after clamping
            self._param_values[param.name] = widget.value()
            widget.valueChanged.connect(
                lambda v, n=param.name: self.set_param(n, v)
            )

        elif param.param_type == "bool":
            widget = QCheckBox()
            widget.setChecked(bool(current_value) if current_value is not None else False)
            # Record actual value
            self._param_values[param.name] = widget.isChecked()
            widget.stateChanged.connect(
                lambda v, n=param.name: self.set_param(n, bool(v))
            )
            # Checkbox is narrower, keep it at right edge
            widget_width = 20
            widget_x = int(self._width) - widget_width - 8
        else:
            widget = QLineEdit()
            widget.setText(str(current_value) if current_value is not None else "")

        # Style the widget
        widget.setStyleSheet("""
            QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {
                background: #3a3a4a;
                border: 1px solid #555;
                border-radius: 3px;
                color: #ddd;
                padding: 2px 4px;
                font-size: 10px;
            }
            QComboBox::drop-down {
                border: none;
                width: 16px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #aaa;
                margin-right: 4px;
            }
            QCheckBox {
                background: transparent;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                background: #3a3a4a;
                border: 1px solid #555;
                border-radius: 2px;
            }
            QCheckBox::indicator:checked {
                background: #6a8fbd;
            }
        """)

        widget.setFixedSize(int(widget_width), 20)
        proxy.setWidget(widget)
        proxy.setPos(widget_x, y)

        return proxy

    def _ensure_param_widgets(self) -> None:
        """Create parameter widgets if needed."""
        if len(self._param_widgets) == len(self._params):
            return

        socket_section = self._get_socket_section_height()

        # Create widgets for ALL params (visibility handled separately)
        for i, param in enumerate(self._params):
            if param.name in self._param_widgets:
                continue

            y = self.TITLE_HEIGHT + socket_section + i * self.PARAM_HEIGHT + 3
            proxy = self._create_param_widget(param, y)
            self._param_widgets[param.name] = proxy

        # Apply correct visibility and positions
        self._update_param_visibility()

    def get_socket_pos(self, socket: "NodeSocket") -> QPointF:
        """Get socket position in scene coordinates."""
        y = self.TITLE_HEIGHT + self.SOCKET_SPACING // 2 + socket.index * self.SOCKET_SPACING
        if socket.is_input:
            x = 0
        else:
            x = self._width
        return self.mapToScene(QPointF(x, y))

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._width, self._height)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        w = int(self._width)
        h = int(self._height)

        # Body background
        painter.setBrush(QBrush(self.COLOR_BODY_BG))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(
            0, 0, w, h,
            self.CORNER_RADIUS, self.CORNER_RADIUS
        )

        # Title bar
        painter.setBrush(QBrush(self._get_title_color()))
        painter.drawRoundedRect(
            0, 0, w, self.TITLE_HEIGHT,
            self.CORNER_RADIUS, self.CORNER_RADIUS
        )
        # Square off bottom corners of title
        painter.drawRect(0, self.TITLE_HEIGHT - self.CORNER_RADIUS,
                        w, self.CORNER_RADIUS)

        # Border
        border_color = self.COLOR_BORDER_SELECTED if self.isSelected() else self.COLOR_BORDER
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(border_color, 2))
        painter.drawRoundedRect(
            0, 0, w, h,
            self.CORNER_RADIUS, self.CORNER_RADIUS
        )

        # Title text
        painter.setPen(QPen(self.COLOR_TITLE_TEXT))
        font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(
            QRectF(self.PADDING, 0, w - 2 * self.PADDING, self.TITLE_HEIGHT),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self.display_title
        )

        # Draw sockets
        self._draw_sockets(painter)

        # Draw inplace pairs (arcs connecting input to output)
        self._draw_inplace_pairs(painter)

        # Draw parameters
        self._draw_params(painter)

        # Ensure parameter widgets exist
        self._ensure_param_widgets()

        # Draw resize handle (bottom-right corner)
        self._draw_resize_handle(painter)

    @property
    def display_title(self) -> str:
        """Get display title: 'name (type)' if named, else just 'type'."""
        if self.name:
            return f"{self.name} ({self.title})"
        return self.title

    def _get_title_color(self) -> QColor:
        """Get title bar color based on node type."""
        colors = {
            "resource": QColor(80, 100, 60),    # Green for resources
            "pass": QColor(60, 80, 120),        # Blue for passes
            "viewport": QColor(120, 60, 80),    # Red for viewports
            "effect": QColor(100, 80, 60),      # Orange for effects
        }
        return colors.get(self.node_type, self.COLOR_TITLE_BG)

    def _draw_sockets(self, painter: QPainter) -> None:
        """Draw input and output sockets."""
        font = QFont("Segoe UI", 9)
        painter.setFont(font)
        w = int(self._width)

        # Input sockets (left side)
        for socket in self.input_sockets:
            y = self.TITLE_HEIGHT + self.SOCKET_SPACING // 2 + socket.index * self.SOCKET_SPACING

            # Socket circle
            painter.setBrush(QBrush(socket.color))
            painter.setPen(QPen(QColor(30, 30, 30), 1))
            painter.drawEllipse(
                QPointF(0, y),
                self.SOCKET_RADIUS // 2,
                self.SOCKET_RADIUS // 2
            )

            # Socket label
            painter.setPen(QPen(QColor(180, 180, 180)))
            painter.drawText(
                QRectF(self.SOCKET_RADIUS + 4, y - 10, w // 2, 20),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                socket.name
            )

        # Output sockets (right side)
        for socket in self.output_sockets:
            y = self.TITLE_HEIGHT + self.SOCKET_SPACING // 2 + socket.index * self.SOCKET_SPACING

            # Socket circle
            painter.setBrush(QBrush(socket.color))
            painter.setPen(QPen(QColor(30, 30, 30), 1))
            painter.drawEllipse(
                QPointF(w, y),
                self.SOCKET_RADIUS // 2,
                self.SOCKET_RADIUS // 2
            )

            # Socket label
            painter.setPen(QPen(QColor(180, 180, 180)))
            painter.drawText(
                QRectF(w // 2, y - 10, w // 2 - self.SOCKET_RADIUS - 4, 20),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                socket.name
            )

    def _draw_params(self, painter: QPainter) -> None:
        """Draw parameter labels for visible params only."""
        visible_params = self._get_visible_params()
        if not visible_params:
            return

        socket_section = self._get_socket_section_height()
        font = QFont("Segoe UI", 9)
        painter.setFont(font)
        painter.setPen(QPen(QColor(160, 160, 170)))

        # Widget is 100px wide, positioned 8px from right edge
        # Label goes from 8px to (width - 100 - 8 - 4) with some padding
        label_width = int(self._width) - 100 - 8 - 12

        for i, param in enumerate(visible_params):
            y = self.TITLE_HEIGHT + socket_section + i * self.PARAM_HEIGHT
            painter.drawText(
                QRectF(8, y, label_width, self.PARAM_HEIGHT),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                param.label
            )

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        """Handle item changes (movement, selection)."""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # Update all connected edges
            for socket in self.input_sockets + self.output_sockets:
                for connection in socket.connections:
                    connection.update_path()
        return super().itemChange(change, value)

    def get_socket_at(self, pos: QPointF) -> Optional["NodeSocket"]:
        """Find socket at given local position."""
        for socket in self.input_sockets + self.output_sockets:
            socket_pos = self.get_socket_pos(socket)
            local_socket_pos = self.mapFromScene(socket_pos)
            if (pos - local_socket_pos).manhattanLength() < self.SOCKET_RADIUS * 2:
                return socket
        return None

    def _draw_inplace_pairs(self, painter: QPainter) -> None:
        """Draw arcs connecting input/output socket pairs (inplace and target)."""
        from PyQt6.QtGui import QPainterPath

        # Build socket lookup by name
        inputs_by_name = {s.name: s for s in self.input_sockets}
        outputs_by_name = {s.name: s for s in self.output_sockets}

        w = int(self._width)

        # Collect all pairs to draw: (input_socket, output_socket, color)
        pairs_to_draw = []

        # 1. Inplace pairs (green)
        inplace_pairs = self.data.get("inplace_pairs", [])
        inplace_outputs = {out_name for _, out_name in inplace_pairs}

        for input_name, output_name in inplace_pairs:
            input_socket = inputs_by_name.get(input_name)
            output_socket = outputs_by_name.get(output_name)
            if input_socket and output_socket:
                pairs_to_draw.append((input_socket, output_socket, QColor(100, 150, 100, 180)))

        # 2. Target pairs for non-inplace outputs (blue)
        for output_socket in self.output_sockets:
            if output_socket.name in inplace_outputs:
                continue
            target_name = f"{output_socket.name}_target"
            target_socket = inputs_by_name.get(target_name)
            if target_socket:
                pairs_to_draw.append((target_socket, output_socket, QColor(100, 130, 180, 180)))

        # Draw all pairs
        painter.setBrush(Qt.BrushStyle.NoBrush)

        for input_socket, output_socket, color in pairs_to_draw:
            pen = QPen(color, 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)

            # Get Y positions
            in_y = self.TITLE_HEIGHT + self.SOCKET_SPACING // 2 + input_socket.index * self.SOCKET_SPACING
            out_y = self.TITLE_HEIGHT + self.SOCKET_SPACING // 2 + output_socket.index * self.SOCKET_SPACING

            path = QPainterPath()
            start_x = self.SOCKET_RADIUS + 2
            end_x = w - self.SOCKET_RADIUS - 2

            # If same Y, draw a simple line with slight curve
            if abs(in_y - out_y) < 2:
                mid_y = in_y - 8
                path.moveTo(start_x, in_y)
                path.cubicTo(
                    start_x + 20, mid_y,
                    end_x - 20, mid_y,
                    end_x, out_y
                )
            else:
                # Different Y - draw arc
                path.moveTo(start_x, in_y)
                path.cubicTo(
                    start_x + 30, in_y,
                    end_x - 30, out_y,
                    end_x, out_y
                )

            painter.drawPath(path)

    def _draw_resize_handle(self, painter: QPainter) -> None:
        """Draw resize handle in bottom-right corner."""
        size = self.RESIZE_HANDLE_SIZE
        w = int(self._width)
        h = int(self._height)
        x = w - size
        y = h - size

        # Draw diagonal lines as resize indicator
        painter.setPen(QPen(QColor(100, 100, 110), 1))
        for i in range(3):
            offset = 3 + i * 3
            painter.drawLine(
                x + offset, y + size - 2,
                x + size - 2, y + offset
            )

    def _get_resize_handle_rect(self) -> QRectF:
        """Get the resize handle rectangle."""
        size = self.RESIZE_HANDLE_SIZE
        return QRectF(
            self._width - size,
            self._height - size,
            size,
            size
        )

    def _is_in_resize_handle(self, pos: QPointF) -> bool:
        """Check if position is within resize handle."""
        return self._get_resize_handle_rect().contains(pos)

    def mousePressEvent(self, event) -> None:
        """Handle mouse press for resize."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self._is_in_resize_handle(event.pos()):
                self._resizing = True
                self._resize_start_pos = event.scenePos()
                self._resize_start_width = self._width
                self._resize_start_height = self._height
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        """Handle mouse move for resize."""
        if self._resizing and self._resize_start_pos is not None:
            delta = event.scenePos() - self._resize_start_pos
            new_width = self._resize_start_width + delta.x()
            new_width = max(self.MIN_WIDTH, new_width)

            new_height = self._resize_start_height + delta.y()
            # Calculate minimum height based on content
            socket_count = max(len(self.input_sockets), len(self.output_sockets), 1)
            min_content_height = (
                self.TITLE_HEIGHT +
                socket_count * self.SOCKET_SPACING +
                len(self._params) * self.PARAM_HEIGHT +
                self.PADDING
            )
            new_height = max(min_content_height, new_height)

            changed = False
            if new_width != self._width:
                self._width = new_width
                changed = True

            if new_height != self._height:
                self._height_override = new_height
                self._update_height()
                changed = True

            if changed:
                self.prepareGeometryChange()
                self._rebuild_param_widgets()
                self.update()
                # Update connections
                for socket in self.input_sockets + self.output_sockets:
                    for conn in socket.connections:
                        conn.update_path()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        """Handle mouse release for resize."""
        if self._resizing:
            self._resizing = False
            self._resize_start_pos = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _rebuild_param_widgets(self) -> None:
        """Rebuild parameter widgets after resize."""
        # Remove old widgets
        for proxy in self._param_widgets.values():
            proxy.setParentItem(None)
            if self.scene():
                self.scene().removeItem(proxy)
        self._param_widgets.clear()

    def hoverMoveEvent(self, event) -> None:
        """Change cursor when hovering over resize handle."""
        if self._is_in_resize_handle(event.pos()):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        """Reset cursor when leaving node."""
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().hoverLeaveEvent(event)

    def contextMenuEvent(self, event) -> None:
        """Show context menu for node."""
        event.accept()  # Prevent propagation to scene

        menu = QMenu()

        # Rename action
        rename_action = menu.addAction("Rename")
        rename_action.triggered.connect(self._rename_node)

        menu.addSeparator()

        # Delete action
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(self._delete_node)

        menu.exec(event.screenPos())

    def _rename_node(self) -> None:
        """Show rename dialog."""
        current_name = self.name if self.name else ""
        new_name, ok = QInputDialog.getText(
            None,
            "Rename Node",
            f"Enter name for {self.title}:",
            QLineEdit.EchoMode.Normal,
            current_name,
        )
        if ok:
            self.name = new_name.strip()
            self.update()

    def _delete_node(self) -> None:
        """Delete this node from the scene."""
        scene = self.scene()
        if scene is not None:
            from termin.nodegraph.scene import NodeGraphScene
            if isinstance(scene, NodeGraphScene):
                scene.remove_node(self)
