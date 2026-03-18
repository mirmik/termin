"""
Import/export rfmeas positioner models.

rfmeas uses a flat JSON format:
  {"axis_mapping": {...}, "entities": [...]}

The editor uses:
  {"version": "1.0", "scene": {"entities": [...]}, "editor": {...}}

Entity/component structure is identical in both formats.
axis_mapping is stored via RfmeasAxisBinding components on individual entities.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QWidget, QFileDialog, QMessageBox

from tcbase import log

if TYPE_CHECKING:
    from termin.editor.scene_manager import SceneManager


_BINDING_TYPE = "RfmeasAxisBinding"

# Remembered source path for re-export default
_rfmeas_source_path: str | None = None


def _invert_axis_mapping(axis_mapping: dict[str, str]) -> dict[str, str]:
    """Invert axis_mapping from {axis_name: entity_name} to {entity_name: axis_name}."""
    return {entity_name: axis_name for axis_name, entity_name in axis_mapping.items()}


def _inject_bindings(entities: list[dict], entity_to_axis: dict[str, str]) -> None:
    """Recursively inject RfmeasAxisBinding components into entity JSON."""
    for ent in entities:
        name = ent.get("name", "")
        if name in entity_to_axis:
            binding = {
                "type": _BINDING_TYPE,
                "data": {"axis_name": entity_to_axis[name]},
            }
            ent.setdefault("components", []).append(binding)
        children = ent.get("children")
        if children:
            _inject_bindings(children, entity_to_axis)


def _collect_bindings(entities: list[dict]) -> dict[str, str]:
    """Recursively collect axis_mapping and remove RfmeasAxisBinding components from JSON."""
    axis_mapping: dict[str, str] = {}
    for ent in entities:
        name = ent.get("name", "")
        components = ent.get("components", [])
        remaining = []
        for comp in components:
            if comp.get("type") == _BINDING_TYPE:
                axis_name = comp.get("data", {}).get("axis_name", "")
                if axis_name and name:
                    axis_mapping[axis_name] = name
            else:
                remaining.append(comp)
        ent["components"] = remaining
        children = ent.get("children")
        if children:
            axis_mapping.update(_collect_bindings(children))
    return axis_mapping


def import_rfmeas_model(
    parent: QWidget,
    scene_manager: SceneManager,
    scene_name: str,
) -> bool:
    """Show file dialog and import rfmeas model into current scene."""
    global _rfmeas_source_path

    # Ensure RfmeasAxisBinding is registered before loading data
    import termin.editor.rfmeas_axis_binding  # noqa: F401

    scene = scene_manager.get_scene(scene_name)
    if scene is None:
        QMessageBox.critical(parent, "Import Error", "No active scene.")
        return False

    file_path, _ = QFileDialog.getOpenFileName(
        parent,
        "Import rfmeas model",
        "",
        "rfmeas scene (*.json);;All Files (*)",
        options=QFileDialog.Option.DontUseNativeDialog,
    )
    if not file_path:
        return False

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            rfmeas_data = json.load(f)
    except Exception as e:
        QMessageBox.critical(parent, "Import Error", f"Failed to read file:\n{file_path}\n\n{e}")
        return False

    if "entities" not in rfmeas_data:
        QMessageBox.critical(parent, "Import Error", "Not a valid rfmeas scene: missing 'entities' key.")
        return False

    axis_mapping = rfmeas_data.get("axis_mapping", {})
    entities = rfmeas_data["entities"]

    # Inject RfmeasAxisBinding components based on axis_mapping
    entity_to_axis = _invert_axis_mapping(axis_mapping)
    _inject_bindings(entities, entity_to_axis)

    # Load entities into current scene
    scene_data = {"entities": entities}
    scene.load_from_data(scene_data, context=None, update_settings=False)

    _rfmeas_source_path = file_path
    log.info(f"Imported rfmeas model: {file_path} (axes: {list(axis_mapping.keys())})")
    return True


def export_rfmeas_model(
    parent: QWidget,
    scene_manager: SceneManager,
    scene_name: str,
) -> bool:
    """Export current scene as rfmeas model JSON."""
    global _rfmeas_source_path

    scene = scene_manager.get_scene(scene_name)
    if scene is None:
        QMessageBox.critical(parent, "Export Error", "No active scene.")
        return False

    default_path = _rfmeas_source_path or ""
    file_path, _ = QFileDialog.getSaveFileName(
        parent,
        "Export rfmeas model",
        default_path,
        "rfmeas scene (*.json);;All Files (*)",
        options=QFileDialog.Option.DontUseNativeDialog,
    )
    if not file_path:
        return False

    if not file_path.endswith(".json"):
        file_path += ".json"

    # Serialize scene in memory
    scene_data = scene.serialize()
    entities = scene_data.get("entities", [])

    # Collect axis_mapping from RfmeasAxisBinding components and strip them
    axis_mapping = _collect_bindings(entities)

    rfmeas_data = {
        "axis_mapping": axis_mapping,
        "entities": entities,
    }

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(rfmeas_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        QMessageBox.critical(parent, "Export Error", f"Failed to write file:\n{file_path}\n\n{e}")
        return False

    _rfmeas_source_path = file_path
    log.info(f"Exported rfmeas model: {file_path}")
    return True
