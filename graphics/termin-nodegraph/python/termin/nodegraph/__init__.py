"""termin-nodegraph public API."""

import logging

from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("termin_base", "termin_nodegraph_core")

from termin.nodegraph.controller import ConnectResult, GraphController  # noqa: E402
from termin.nodegraph.io import graph_from_dict, graph_to_dict, load_graph_json, save_graph_json  # noqa: E402
from termin.nodegraph.model import Edge, Graph, Group, Node, Socket  # noqa: E402
from termin.nodegraph.schema import (  # noqa: E402
    ConnectionValidator,
    DictSchemaProvider,
    DefaultConnectionValidator,
    NodeSchemaProvider,
    NodeTemplate,
)

try:
    from termin.nodegraph.native_view import (
        NativeNodeGraphView,
        NodeBodyContent,
        NodeBodyContentProvider,
        NodeBodyLayout,
        build_native_node_graph_view,
    )
except ImportError as e:
    logging.getLogger(__name__).debug(
        "Optional import termin.nodegraph.native_view failed: %s — native GUI features unavailable",
        e,
    )
    NativeNodeGraphView = None
    NodeBodyContent = None
    NodeBodyContentProvider = None
    NodeBodyLayout = None
    build_native_node_graph_view = None

__all__ = [
    "Socket",
    "Node",
    "Edge",
    "Group",
    "Graph",
    "NodeTemplate",
    "NodeSchemaProvider",
    "DictSchemaProvider",
    "ConnectionValidator",
    "DefaultConnectionValidator",
    "ConnectResult",
    "GraphController",
    "graph_to_dict",
    "graph_from_dict",
    "save_graph_json",
    "load_graph_json",
    "NativeNodeGraphView",
    "NodeBodyContent",
    "NodeBodyContentProvider",
    "NodeBodyLayout",
    "build_native_node_graph_view",
]
