from __future__ import annotations

import json

from termin.editor_core.editor_state_io import EditorStateIO
from termin.editor_core.editor_scene_attachment import EditorSceneAttachment


def test_extract_prefers_canonical_camera_over_legacy_scene_metadata(tmp_path) -> None:
    canonical = {"position": [1, 2, 3], "rotation": [0, 0, 0, 1]}
    legacy = {"position": [9, 8, 7], "rotation": [0, 0, 1, 0]}
    path = tmp_path / "canonical.scene"
    path.write_text(
        json.dumps(
            {
                "scene": {
                    "metadata": {
                        "termin": {"editor": {"entities_data": legacy}}
                    }
                },
                "editor": {"camera": canonical},
            }
        ),
        encoding="utf-8",
    )

    assert EditorStateIO.extract_from_file(str(path))["camera"] == canonical


def test_extract_migrates_legacy_camera_from_scene_metadata(tmp_path) -> None:
    legacy = {
        "position": [9, 8, 7],
        "rotation": [0, 0, 1, 0],
        "editor_entities": {"camera": []},
    }
    path = tmp_path / "legacy.scene"
    path.write_text(
        json.dumps(
            {
                "scene": {
                    "metadata": {
                        "termin": {"editor": {"entities_data": legacy}}
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    assert EditorStateIO.extract_from_file(str(path))["camera"] == legacy


def test_collect_keeps_camera_only_in_canonical_editor_state() -> None:
    camera = {
        "position": [1, 2, 3],
        "rotation": [0, 0, 0, 1],
        "editor_entities": {
            "camera": [
                {
                    "source_id": "stable-camera",
                    "type": "CameraComponent",
                    "data": {},
                }
            ]
        },
    }

    class Attachment:
        def get_camera_data(self):
            return camera

    state_io = EditorStateIO(Attachment())

    assert state_io.collect() == {"camera": camera}


def test_attachment_caches_camera_without_writing_scene_metadata() -> None:
    camera = {"position": [1, 2, 3], "rotation": [0, 0, 0, 1]}

    class Handle:
        index = 7
        generation = 11

    class Scene:
        def scene_handle(self):
            return Handle()

        def set_metadata_value(self, *_args):
            raise AssertionError("editor camera must not be written to scene metadata")

    class CameraManager:
        def get_camera_data(self):
            return camera

    attachment = object.__new__(EditorSceneAttachment)
    attachment._attached_scene = Scene()
    attachment._camera_manager = CameraManager()
    attachment._camera_state_by_scene = {}

    attachment.save_state()

    assert attachment._camera_state_by_scene == {(7, 11): camera}


def test_attachment_takes_and_clears_legacy_scene_camera() -> None:
    legacy = {"position": [4, 5, 6], "rotation": [0, 0, 0, 1]}

    class Scene:
        def __init__(self) -> None:
            self.cleared = []

        def get_metadata_value(self, path: str):
            assert path == "termin.editor.entities_data"
            return legacy

        def clear_metadata_value(self, path: str) -> None:
            self.cleared.append(path)

    scene = Scene()

    assert EditorSceneAttachment._take_legacy_camera_data(scene) == legacy
    assert scene.cleared == ["termin.editor.entities_data"]
