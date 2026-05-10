"""Helpers for finding asset dependencies in pipeline graph JSON."""

from __future__ import annotations

from typing import Iterable


def material_pass_materials(graph_data: dict | None) -> set[str]:
    """Return material asset names referenced by MaterialPass nodes/passes."""
    if graph_data is None:
        return set()

    result: set[str] = set()

    nodes = graph_data.get("nodes", [])
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_type = str(node.get("type", ""))
            pass_class = str(node.get("pass_class", ""))
            graph_type = str(node.get("graph_type", ""))
            if node_type != "MaterialPass" and pass_class != "MaterialPass" and graph_type != "MaterialPass":
                continue
            params = node.get("params", {})
            if not isinstance(params, dict):
                continue
            material_name = params.get("material")
            if isinstance(material_name, str) and material_name:
                result.add(material_name)

    passes = graph_data.get("passes", [])
    if isinstance(passes, list):
        for pass_data in passes:
            if not isinstance(pass_data, dict):
                continue
            pass_type = str(pass_data.get("type", ""))
            pass_class = str(pass_data.get("pass_class", ""))
            if pass_type != "MaterialPass" and pass_class != "MaterialPass":
                continue

            for field_name in ("params", "data"):
                field_data = pass_data.get(field_name, {})
                if not isinstance(field_data, dict):
                    continue
                material_name = field_data.get("material")
                if isinstance(material_name, str) and material_name:
                    result.add(material_name)

    return result


def uses_material_names(graph_data: dict | None, material_names: Iterable[str]) -> bool:
    """Return true if graph_data references any material in material_names."""
    names = set(material_names)
    if not names:
        return False
    return bool(material_pass_materials(graph_data) & names)
