"""Python adapter for the document-owned C++ nodegraph view."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from termin.gui_native import TcDocument, WidgetHandle, WidgetRef
from termin.nodegraph._nodegraph_native import NativeNodeGraphView
from termin.nodegraph.body import NodeBodyContent, NodeBodyContentProvider, NodeBodyLayout
from termin.nodegraph.controller import GraphController
from termin.nodegraph.model import Graph, Node, Socket, _node_from_dict


_Color = tuple[float, float, float, float]


def _node_callback(callback: Callable) -> Callable:
    def invoke(node: dict, *args):
        return callback(_node_from_dict(node), *args)

    return invoke


def _socket_callback(callback: Callable) -> Callable:
    def invoke(node: dict, socket: dict, direction: str):
        return callback(_node_from_dict(node), Socket(**socket, is_input=direction == "input"), direction)

    return invoke


def _body_callback(provider: NodeBodyContentProvider) -> Callable:
    def invoke(document: TcDocument, node: dict):
        content = provider(document, _node_from_dict(node))
        if content is None:
            return None
        if not isinstance(content, NodeBodyContent) or not isinstance(content.widget, WidgetRef):
            raise TypeError("body provider must return NodeBodyContent with a WidgetRef")
        widget = content.widget
        if not widget.alive or widget.document != document:
            raise ValueError("node body must belong to the live view document")
        if widget.parent is not None:
            raise ValueError("node body widget must be parentless")
        layout = content.layout
        return (
            widget.handle,
            (layout.height, layout.inset_left, layout.inset_right,
             layout.inset_top, layout.inset_bottom, layout.gap_before),
            _node_callback(content.update) if content.update is not None else None,
        )

    return invoke


class CppNodeGraphView:
    """Borrow a TcDocument and project the exact graph owned by a GraphController.

    Mount root_handle in the document or insert it into an existing widget.
    Call close() to remove the view. Its document keeps the bridge and
    callbacks alive until close() or native root or document destruction.
    """

    def __init__(
        self,
        document: TcDocument,
        controller: GraphController,
        *,
        node_palette: Callable[[Node], dict[str, _Color] | None] | None = None,
        socket_color: Callable[[Node, Socket, str], _Color | None] | None = None,
        socket_label: Callable[[Node, Socket, str], str | None] | None = None,
        parameter_editors: Callable[[Node], Iterable[dict] | None] | None = None,
        body_content_provider: NodeBodyContentProvider | None = None,
        on_graph_changed: Callable[[int], None] | None = None,
        on_param_changed: Callable[[Node, str, object], None] | None = None,
        on_context: Callable[[dict], None] | None = None,
        on_request_render: Callable[[], None] | None = None,
    ) -> None:
        self.document = document
        self.controller = controller
        callbacks = {}
        for name, callback in (
            ("node_palette", node_palette),
            ("parameter_editors", parameter_editors),
            ("parameter_changed", on_param_changed),
        ):
            if callback is not None:
                callbacks[name] = _node_callback(callback)
        for name, callback in (("socket_color", socket_color), ("socket_label", socket_label)):
            if callback is not None:
                callbacks[name] = _socket_callback(callback)
        for name, callback in (
            ("graph_changed", on_graph_changed),
            ("context", on_context),
            ("request_render", on_request_render),
        ):
            if callback is not None:
                callbacks[name] = callback
        if body_content_provider is not None:
            callbacks["body_content"] = _body_callback(body_content_provider)
        self._view = NativeNodeGraphView(document, controller.graph._native, callbacks)

    @property
    def closed(self) -> bool:
        return self._view.closed

    @property
    def root_handle(self) -> WidgetHandle:
        return self._view.root_handle

    def parameter_widget(self, node_id: str, name: str) -> WidgetRef | None:
        handle = self._view.parameter_handle(node_id, name)
        return self.document.ref(handle) if handle else None

    def body_widget(self, node_id: str) -> WidgetRef | None:
        handle = self._view.body_handle(node_id)
        return self.document.ref(handle) if handle else None

    def world_to_screen(self, x: float, y: float) -> tuple[float, float]:
        return self._view.world_to_screen(x, y)

    def screen_to_world(self, x: float, y: float) -> tuple[float, float]:
        return self._view.screen_to_world(x, y)

    def set_graph(self, graph: Graph) -> None:
        if not isinstance(graph, Graph):
            raise TypeError("replacement must be a nodegraph Graph")
        self._view.check_mutation()
        self.controller.replace_graph(graph)
        self._view.set_graph(graph._native)

    def rebuild(self) -> bool:
        return self._view.rebuild()

    def sync(self) -> bool:
        """Rebuild when the graph revision changed since the native projection."""
        return self._view.sync()

    def close(self) -> None:
        self._view.close()


__all__ = ["CppNodeGraphView", "NodeBodyContent", "NodeBodyContentProvider", "NodeBodyLayout"]
