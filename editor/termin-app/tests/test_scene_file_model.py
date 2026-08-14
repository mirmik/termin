from termin.editor_core import scene_name_from_file_path


def test_scene_name_from_file_path_uses_stem():
    assert scene_name_from_file_path("/tmp/project/Scenes/MainLevel.scene") == "MainLevel"
