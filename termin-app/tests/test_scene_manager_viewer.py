import importlib.util
import os
from pathlib import Path


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_scene_manager_viewers_format_scene_handle_object():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    repo_root = Path(__file__).resolve().parents[2]
    qt_viewer = _load_module(
        "scene_manager_viewer_under_test",
        repo_root / "termin-app/termin/editor/scene_manager_viewer.py",
    )
    tcgui_viewer = _load_module(
        "tcgui_scene_manager_viewer_under_test",
        repo_root / "termin-app/termin/editor_tcgui/dialogs/scene_manager_viewer.py",
    )

    from termin.editor.scene_manager import SceneManager
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    scene_manager = SceneManager()
    scene = scene_manager.create_scene("ViewerHandle", [])
    assert scene is not None

    try:
        handle = scene.scene_handle()
        expected = f"{handle.index}:{handle.generation}"

        assert qt_viewer._format_scene_handle(handle) == expected
        assert tcgui_viewer._format_scene_handle(handle) == expected

        viewer = qt_viewer.SceneManagerViewer(scene_manager)
        viewer.refresh()
        viewer.close()
    finally:
        scene_manager.close_all_scenes()
