"""Frame pass graph metadata helpers for editor frontends."""

from __future__ import annotations

from tcbase import log


def _metadata_graph(class_name: str) -> dict:
    try:
        from termin._native.inspect import InspectRegistry

        registry = InspectRegistry.instance()
        metadata = registry.get_type_metadata(class_name)
        if isinstance(metadata, dict):
            graph = metadata.get("graph", {})
            if isinstance(graph, dict):
                return graph
    except Exception as e:
        log.warn(f"[pipeline_pass_registry] get graph metadata for '{class_name}' failed: {e}")
    return {}


def _metadata_pairs(graph: dict, key: str) -> list[tuple[str, str]]:
    values = graph.get(key, [])
    if not isinstance(values, list):
        return []

    result: list[tuple[str, str]] = []
    for item in values:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            result.append((str(item[0]), str(item[1])))
    return result


def get_pass_sockets(class_name: str) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Return graph input/output socket metadata for a frame pass class."""
    graph = _metadata_graph(class_name)
    metadata_inputs = _metadata_pairs(graph, "node_inputs")
    metadata_outputs = _metadata_pairs(graph, "node_outputs")
    return metadata_inputs, metadata_outputs


def get_pass_inplace_pairs(class_name: str) -> list[tuple[str, str]]:
    """Return graph inplace input/output pairs for a frame pass class."""
    graph = _metadata_graph(class_name)
    return _metadata_pairs(graph, "node_inplace_pairs")
