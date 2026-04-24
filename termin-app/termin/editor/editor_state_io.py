"""
EditorStateIO — UI-independent editor state save/restore.

Handles collecting, applying, and extracting editor state
(camera position, selection, expanded entities, displays)
from scene files. Used by both Qt and tcgui editors.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from tcbase import log

if TYPE_CHECKING:
    from termin.editor.editor_scene_attachment import EditorSceneAttachment
    from termin.visualization.core.entity import Entity


class EditorStateIO:
    """UI-independent editor state serialization.

    Collects/applies: camera, selection, expanded entities, displays.
    File format matches ``data["editor"]`` section of ``.tc_scene`` files.

    Usage::

        state_io = EditorStateIO(attachment, interaction_system)
        state_io.get_scene = lambda: my_scene
        state_io.get_expanded_entity_uuids = tree.get_expanded_entity_uuids

        # Save
        editor_data = state_io.collect()
        scene_manager.save_scene(name, path, editor_data)

        # Load
        editor_data = EditorStateIO.extract_from_file(path)
        attachment.attach(scene, restore_state=False)
        state_io.apply(editor_data)
    """

    def __init__(
        self,
        attachment: "EditorSceneAttachment | None",
        interaction_system=None,
    ) -> None:
        self._attachment = attachment
        self._interaction = interaction_system

        # Optional callbacks — wire from UI layer
        self.get_scene: Callable[[], object | None] | None = None
        self.get_expanded_entity_uuids: Callable[[], list[str] | None] | None = None
        self.set_expanded_entity_uuids: Callable[[list[str]], None] | None = None
        self.get_displays_data: Callable[[], list | None] | None = None
        self.set_displays_data: Callable[[list | None], None] | None = None
        self.on_entity_selected: Callable[["Entity"], None] | None = None

    # ------------------------------------------------------------------
    # Collect
    # ------------------------------------------------------------------

    def collect(self) -> dict:
        """Collect current editor state for saving.

        Returns dict with keys: camera, selected_entity, displays, expanded_entities.
        """
        editor_data: dict = {}

        # Camera
        if self._attachment is not None:
            self._attachment.save_state()
            camera_data = self._attachment.get_camera_data()
            if camera_data is not None:
                editor_data["camera"] = camera_data

        # Selection
        if self._interaction is not None:
            selected = self._interaction.selection.selected
            if selected is not None and selected.valid():
                editor_data["selected_entity"] = selected.uuid

        # Displays
        if self.get_displays_data is not None:
            displays = self.get_displays_data()
            if displays is not None:
                editor_data["displays"] = displays

        # Expanded entities
        if self.get_expanded_entity_uuids is not None:
            expanded = self.get_expanded_entity_uuids()
            if expanded:
                editor_data["expanded_entities"] = expanded

        return editor_data

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------

    def apply(self, editor_data: dict) -> None:
        """Apply editor state loaded from file."""
        # Camera
        camera_data = editor_data.get("camera")
        if camera_data is not None and self._attachment is not None:
            self._attachment.set_camera_data(camera_data)

        # Selection
        selected_uuid = editor_data.get("selected_entity")
        if selected_uuid and self.get_scene is not None:
            scene = self.get_scene()
            if scene is not None:
                entity = scene.get_entity(selected_uuid)
                if entity is not None and entity.selectable:
                    if self._interaction is not None:
                        self._interaction.selection.select(entity)
                    if self.on_entity_selected is not None:
                        self.on_entity_selected(entity)

        # Displays (always call — may need to attach viewport_configs)
        if self.set_displays_data is not None:
            self.set_displays_data(editor_data.get("displays"))

        # Expanded entities
        expanded = editor_data.get("expanded_entities")
        if expanded is not None and self.set_expanded_entity_uuids is not None:
            self.set_expanded_entity_uuids(expanded)

    # ------------------------------------------------------------------
    # Extract from file
    # ------------------------------------------------------------------

    @staticmethod
    def extract_from_file(file_path: str) -> dict:
        """Extract editor data from a scene file.

        Reads the JSON file and returns the ``editor`` section.
        Handles backward compatibility with older scene formats.
        """
        import json

        try:
            with open(file_path, "r") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            log.error(f"EditorStateIO.extract_from_file: {e}")
            return {}

        editor_data = data.get("editor", {})
        scene_data = data.get("scene")
        if scene_data is None:
            scenes = data.get("scenes")
            if scenes and len(scenes) > 0:
                scene_data = scenes[0]
            else:
                scene_data = {}

        result: dict = {}

        # Camera (check both locations for backwards compatibility)
        camera_data = editor_data.get("camera")
        if camera_data is None and scene_data:
            camera_data = scene_data.get("editor_camera")
        if camera_data is not None:
            result["camera"] = camera_data

        # Selection
        selected = editor_data.get("selected_entity")
        if selected is None:
            editor_state = data.get("editor_state", {})
            selected = editor_state.get("selected_entity_name")
        if selected:
            result["selected_entity"] = selected

        # Displays
        displays = editor_data.get("displays")
        if displays is not None:
            result["displays"] = displays

        # Expanded entities
        expanded = editor_data.get("expanded_entities")
        if expanded is not None:
            result["expanded_entities"] = expanded

        return result
