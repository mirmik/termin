"""Toolkit-neutral project file activation and inspector routing."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from tcbase import log

from termin.editor_core.inspector_model import InspectorModel


SCENE_FILE_EXTENSIONS = frozenset({".scene"})
PIPELINE_FILE_EXTENSIONS = frozenset({".pipeline", ".scene_pipeline"})
TEXTURE_FILE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".bmp", ".hdr", ".exr"})
MESH_FILE_EXTENSIONS = frozenset({".obj", ".stl"})
GLB_FILE_EXTENSIONS = frozenset({".glb", ".gltf"})


class ProjectFileActionController:
    """Dispatch project files without depending on a frontend widget toolkit."""

    def __init__(
        self,
        *,
        load_scene_from_file: Callable[[str], None],
        open_prefab: Callable[[str], None],
        get_inspector_model: Callable[[], InspectorModel | None],
        open_in_text_editor: Callable[[str], None] | None = None,
    ) -> None:
        self._load_scene_from_file = load_scene_from_file
        self._open_prefab = open_prefab
        self._get_inspector_model = get_inspector_model
        self._open_in_text_editor_callback = open_in_text_editor

    def activate_file(self, path: str | Path) -> None:
        file_path = str(path)
        ext = Path(file_path).suffix.lower()
        if ext in SCENE_FILE_EXTENSIONS:
            self._load_scene_from_file(file_path)
            return
        if ext == ".prefab":
            self._open_prefab(file_path)
            return
        self._open_in_text_editor(file_path)

    def select_file(self, path: str | Path) -> None:
        inspector = self._get_inspector_model()
        if inspector is None:
            return

        file_path = str(path)
        ext = Path(file_path).suffix.lower()
        if ext == ".material":
            inspector.show_material_for_file(file_path)
        elif ext in PIPELINE_FILE_EXTENSIONS:
            inspector.show_pipeline_for_file(file_path)
        elif ext in TEXTURE_FILE_EXTENSIONS:
            inspector.show_texture_for_file(file_path)
        elif ext in MESH_FILE_EXTENSIONS:
            inspector.show_mesh_for_file(file_path)
        elif ext in GLB_FILE_EXTENSIONS:
            inspector.show_glb_for_file(file_path)

    def _open_in_text_editor(self, path: str) -> None:
        try:
            if self._open_in_text_editor_callback is not None:
                self._open_in_text_editor_callback(path)
                return
            from termin.editor_core.external_editor import open_in_text_editor

            open_in_text_editor(path)
        except Exception as exc:
            log.error(f"[ProjectFileActionController] failed to open file in text editor: {exc}")


__all__ = [
    "GLB_FILE_EXTENSIONS",
    "MESH_FILE_EXTENSIONS",
    "PIPELINE_FILE_EXTENSIONS",
    "ProjectFileActionController",
    "SCENE_FILE_EXTENSIONS",
    "TEXTURE_FILE_EXTENSIONS",
]
