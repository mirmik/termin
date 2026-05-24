import importlib.util
from pathlib import Path


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_scene_manager_viewers_format_scene_handle_object():
    repo_root = Path(__file__).resolve().parents[2]
    tcgui_viewer = _load_module(
        "tcgui_scene_manager_viewer_under_test",
        repo_root / "termin-app/termin/editor_tcgui/dialogs/scene_manager_viewer.py",
    )

    from termin.engine import SceneManager

    scene_manager = SceneManager()
    scene = scene_manager.create_scene("ViewerHandle", [])
    assert scene is not None

    try:
        handle = scene.scene_handle()
        expected = f"{handle.index}:{handle.generation}"

        assert tcgui_viewer._format_scene_handle(handle) == expected
    finally:
        scene_manager.close_all_scenes()
