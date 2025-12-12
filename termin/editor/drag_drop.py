"""Centralized drag-drop support for the editor.

Defines MIME types and helper functions for drag-drop operations
across different editor widgets (SceneTree, ProjectBrowser, Viewport, Inspector).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import QMimeData

if TYPE_CHECKING:
    from termin.visualization.core.entity import Entity


class EditorMimeTypes:
    """MIME types used in the editor for drag-drop operations."""

    # Entity from SceneTree (stores entity name for lookup)
    ENTITY = "application/x-termin-entity"

    # Asset path from ProjectBrowser
    ASSET_PATH = "application/x-termin-asset-path"

    # Resource references (mesh, material, texture names)
    MESH_REF = "application/x-termin-mesh-ref"
    MATERIAL_REF = "application/x-termin-material-ref"
    TEXTURE_REF = "application/x-termin-texture-ref"


def create_entity_mime_data(entity: "Entity") -> QMimeData:
    """
    Create QMimeData for dragging an Entity.

    Stores entity name as JSON for lookup on drop.
    """
    mime = QMimeData()
    data = {
        "entity_name": entity.name,
    }
    mime.setData(EditorMimeTypes.ENTITY, json.dumps(data).encode("utf-8"))
    return mime


def parse_entity_mime_data(mime: QMimeData) -> dict | None:
    """
    Parse entity data from QMimeData.

    Returns dict with 'entity_name' or None if not valid.
    """
    if not mime.hasFormat(EditorMimeTypes.ENTITY):
        return None
    try:
        raw = mime.data(EditorMimeTypes.ENTITY).data()
        return json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def create_asset_path_mime_data(path: str) -> QMimeData:
    """
    Create QMimeData for dragging an asset from ProjectBrowser.
    """
    mime = QMimeData()
    data = {"path": path}
    mime.setData(EditorMimeTypes.ASSET_PATH, json.dumps(data).encode("utf-8"))
    # Also set as URL for compatibility with external apps
    mime.setText(path)
    return mime


def parse_asset_path_mime_data(mime: QMimeData) -> str | None:
    """
    Parse asset path from QMimeData.

    Returns path string or None if not valid.
    """
    if not mime.hasFormat(EditorMimeTypes.ASSET_PATH):
        return None
    try:
        raw = mime.data(EditorMimeTypes.ASSET_PATH).data()
        data = json.loads(raw.decode("utf-8"))
        return data.get("path")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def create_resource_ref_mime_data(
    resource_name: str,
    resource_type: str,
) -> QMimeData:
    """
    Create QMimeData for dragging a resource reference (mesh, material, texture).

    Args:
        resource_name: Name of the resource in ResourceManager
        resource_type: One of 'mesh', 'material', 'texture'
    """
    mime = QMimeData()
    data = {"name": resource_name, "type": resource_type}

    mime_type = {
        "mesh": EditorMimeTypes.MESH_REF,
        "material": EditorMimeTypes.MATERIAL_REF,
        "texture": EditorMimeTypes.TEXTURE_REF,
    }.get(resource_type, EditorMimeTypes.MESH_REF)

    mime.setData(mime_type, json.dumps(data).encode("utf-8"))
    return mime


def parse_resource_ref_mime_data(
    mime: QMimeData,
    resource_type: str,
) -> str | None:
    """
    Parse resource reference name from QMimeData.

    Args:
        mime: The mime data
        resource_type: One of 'mesh', 'material', 'texture'

    Returns:
        Resource name or None if not valid.
    """
    mime_type = {
        "mesh": EditorMimeTypes.MESH_REF,
        "material": EditorMimeTypes.MATERIAL_REF,
        "texture": EditorMimeTypes.TEXTURE_REF,
    }.get(resource_type)

    if mime_type is None or not mime.hasFormat(mime_type):
        return None

    try:
        raw = mime.data(mime_type).data()
        data = json.loads(raw.decode("utf-8"))
        return data.get("name")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
