"""
Import/export rfmeas positioner models.

rfmeas uses a flat JSON format:
  {"axis_mapping": {...}, "entities": [...]}

The editor uses:
  {"version": "1.0", "scene": {"entities": [...]}, "editor": {...}}

Entity/component structure is identical in both formats.
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QWidget, QFileDialog, QMessageBox

from tcbase import log

if TYPE_CHECKING:
    from termin.editor.scene_manager import SceneManager


# Module-level state: remembered axis_mapping and source path
_rfmeas_axis_mapping: dict[str, str] | None = None
_rfmeas_source_path: str | None = None


def import_rfmeas_model(
    parent: QWidget,
    scene_manager: SceneManager,
    scene_name: str,
    load_scene_from_file_fn,
) -> bool:
    """Show file dialog and import rfmeas model into editor scene."""
    global _rfmeas_axis_mapping, _rfmeas_source_path

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

    # Wrap into termin scene format
    termin_data = {
        "version": "1.0",
        "scene": {
            "entities": entities,
        },
    }

    # Write to temp file, load via standard path
    fd, tmp_path = tempfile.mkstemp(suffix=".scene")
    try:
        os.close(fd)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(termin_data, f)

        ok = load_scene_from_file_fn(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    if ok:
        _rfmeas_axis_mapping = axis_mapping
        _rfmeas_source_path = file_path
        log.info(f"Imported rfmeas model: {file_path} (axes: {list(axis_mapping.keys())})")

    return ok


def export_rfmeas_model(
    parent: QWidget,
    scene_manager: SceneManager,
    scene_name: str,
    collect_editor_data_fn=None,
) -> bool:
    """Save current scene as rfmeas model JSON."""
    global _rfmeas_axis_mapping, _rfmeas_source_path

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

    # Save scene to temp file via SceneManager, then extract entities
    fd, tmp_path = tempfile.mkstemp(suffix=".scene")
    try:
        os.close(fd)

        editor_data = None
        if collect_editor_data_fn is not None:
            editor_data = collect_editor_data_fn()

        ok = scene_manager.save_scene(scene_name, tmp_path, editor_data)
        if not ok:
            QMessageBox.critical(parent, "Export Error", "SceneManager.save_scene failed.")
            return False

        with open(tmp_path, "r", encoding="utf-8") as f:
            termin_data = json.load(f)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    scene_data = termin_data.get("scene", {})
    entities = scene_data.get("entities", [])

    axis_mapping = _rfmeas_axis_mapping if _rfmeas_axis_mapping is not None else {}

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
