"""Project browser file activation and selection dispatch."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from tcbase import log


SCENE_FILE_EXTENSIONS = {".scene", ".tc_scene"}


class ProjectFileActionController:
    def __init__(
        self,
        *,
        load_scene_from_file: Callable[[str], None],
        open_prefab: Callable[[str], None],
        get_inspector_controller: Callable[[], object | None],
        open_in_text_editor: Callable[[str], None] | None = None,
    ) -> None:
        self._load_scene_from_file = load_scene_from_file
        self._open_prefab = open_prefab
        self._get_inspector_controller = get_inspector_controller
        self._open_in_text_editor_callback = open_in_text_editor

    def activate_file(self, path: str) -> None:
        ext = Path(path).suffix.lower()
        if ext in SCENE_FILE_EXTENSIONS:
            self._load_scene_from_file(path)
            return
        if ext == ".tc_prefab":
            self._open_prefab(path)
            return
        self._open_in_text_editor(path)

    def select_file(self, path: str) -> None:
        inspector = self._get_inspector_controller()
        if inspector is None:
            return

        ext = Path(path).suffix.lower()
        if ext in (".tc_mat", ".material"):
            inspector.show_material_inspector_for_file(path)
            return
        if ext in (".pipeline", ".tc_pipeline", ".scene_pipeline"):
            inspector.show_pipeline_inspector_for_file(path)
            return
        if ext in (".png", ".jpg", ".jpeg", ".bmp", ".hdr", ".exr"):
            inspector.show_texture_inspector_for_file(path)
            return
        if ext in (".obj", ".stl"):
            inspector.show_mesh_inspector_for_file(path)
            return
        if ext in (".glb", ".gltf"):
            inspector.show_glb_inspector_for_file(path)
            return

    def _open_in_text_editor(self, path: str) -> None:
        try:
            if self._open_in_text_editor_callback is not None:
                self._open_in_text_editor_callback(path)
                return
            from termin.editor_core.external_editor import open_in_text_editor

            open_in_text_editor(path)
        except Exception as e:
            log.error(f"[ProjectFileActionController] failed to open file in text editor: {e}")
