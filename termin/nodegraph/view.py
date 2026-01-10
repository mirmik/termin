"""NodeGraphView - QGraphicsView for the node graph."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPainter, QWheelEvent, QMouseEvent, QKeyEvent
from PyQt6.QtWidgets import QGraphicsView, QMenu

from termin.nodegraph.scene import NodeGraphScene
from termin.nodegraph.node import GraphNode
from termin.nodegraph.socket import NodeSocket

if TYPE_CHECKING:
    pass


class NodeGraphView(QGraphicsView):
    """
    View for the node graph with pan and zoom support.
    """

    ZOOM_FACTOR = 1.15
    ZOOM_MIN = 0.1
    ZOOM_MAX = 3.0

    def __init__(self, scene: NodeGraphScene, parent=None):
        super().__init__(scene, parent)

        self._scene = scene

        # View settings
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        # State
        self._zoom = 1.0
        self._panning = False
        self._pan_start = QPointF()
        self._connecting = False

        # Center the view
        self.centerOn(0, 0)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle zoom with mouse wheel."""
        if event.angleDelta().y() > 0:
            zoom = self.ZOOM_FACTOR
        else:
            zoom = 1 / self.ZOOM_FACTOR

        new_zoom = self._zoom * zoom
        if self.ZOOM_MIN <= new_zoom <= self.ZOOM_MAX:
            self._zoom = new_zoom
            self.scale(zoom, zoom)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press."""
        # Middle mouse for panning
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        # Right click for context menu
        if event.button() == Qt.MouseButton.RightButton:
            # Check if clicking on a node - let node handle its own context menu
            item = self.itemAt(event.pos())
            if isinstance(item, GraphNode):
                # Pass event to the node
                super().mousePressEvent(event)
                return
            # Show scene context menu
            self._show_context_menu(event.position())
            return

        # Left click - check if clicking on a socket
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            item = self.itemAt(event.pos())

            if isinstance(item, GraphNode):
                # Check if clicking on a socket
                local_pos = item.mapFromScene(scene_pos)
                socket = item.get_socket_at(local_pos)
                if socket:
                    # Start connection drag
                    self._connecting = True
                    self._scene.start_connection_drag(socket, scene_pos)
                    return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move."""
        if self._panning:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(
                int(self.horizontalScrollBar().value() - delta.x())
            )
            self.verticalScrollBar().setValue(
                int(self.verticalScrollBar().value() - delta.y())
            )
            return

        if self._connecting:
            scene_pos = self.mapToScene(event.pos())
            self._scene.update_connection_drag(scene_pos)
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release."""
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return

        if event.button() == Qt.MouseButton.LeftButton and self._connecting:
            self._connecting = False
            scene_pos = self.mapToScene(event.pos())

            # Check if releasing on a socket
            item = self.itemAt(event.pos())
            end_socket = None
            if isinstance(item, GraphNode):
                local_pos = item.mapFromScene(scene_pos)
                end_socket = item.get_socket_at(local_pos)

            self._scene.finish_connection_drag(end_socket)
            return

        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press."""
        if event.key() == Qt.Key.Key_Delete:
            self._scene.delete_selected()
            return

        if event.key() == Qt.Key.Key_F:
            # Frame all nodes
            self.fit_in_view()
            return

        super().keyPressEvent(event)

    def fit_in_view(self) -> None:
        """Fit all nodes in view."""
        items_rect = self._scene.itemsBoundingRect()
        if not items_rect.isEmpty():
            self.fitInView(items_rect, Qt.AspectRatioMode.KeepAspectRatio)
            # Update zoom level
            self._zoom = self.transform().m11()

    def _show_context_menu(self, pos) -> None:
        """Show context menu for creating nodes."""
        from termin.nodegraph.nodes import get_available_passes_by_category

        menu = QMenu(self)

        # Resources submenu
        resources_menu = menu.addMenu("Resources")
        resources_menu.addAction("FBO", lambda: self._create_node("resource", "FBO", pos))
        resources_menu.addAction("Shadow Maps", lambda: self._create_node("resource", "Shadow Maps", pos))

        # Build passes menu from registry
        categories = get_available_passes_by_category()

        # Effect passes go to Effects category
        effect_passes = {"BloomPass", "GrayscalePass", "MaterialPass"}

        for category, passes in categories.items():
            if not passes:
                continue

            submenu = menu.addMenu(category)
            for pass_class in passes:
                # Determine node type
                if pass_class in effect_passes:
                    node_type = "effect"
                else:
                    node_type = "pass"

                # Create readable label
                label = pass_class.replace("Pass", " Pass") if "Pass" in pass_class else pass_class
                # Capture variables in lambda
                submenu.addAction(
                    label,
                    lambda p=pos, t=node_type, c=pass_class: self._create_node(t, c, p)
                )

        menu.addSeparator()

        # Viewport frame (container)
        menu.addAction("Viewport Frame", lambda: self._create_viewport_frame(pos))

        menu.exec(self.mapToGlobal(pos.toPoint()))

    def _create_node(self, node_type: str, title: str, pos) -> None:
        """Create a new node at position."""
        from termin.nodegraph.nodes import create_node

        scene_pos = self.mapToScene(pos.toPoint())
        node = create_node(node_type, title)
        node.setPos(scene_pos)
        self._scene.add_node(node)

    def _create_viewport_frame(self, pos) -> None:
        """Create a new viewport frame at position."""
        from termin.nodegraph.viewport_frame import ViewportFrame

        scene_pos = self.mapToScene(pos.toPoint())
        frame = ViewportFrame(
            title="Viewport",
            x=scene_pos.x(),
            y=scene_pos.y(),
            width=500,
            height=350,
        )
        self._scene.add_viewport_frame(frame)
