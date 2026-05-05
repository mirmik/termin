import importlib.util
import sys
from pathlib import Path


repo_root = Path(__file__).resolve().parents[1]
module_path = repo_root / "termin/editor_core/__init__.py"
spec = importlib.util.spec_from_file_location(
    "editor_core_under_test",
    module_path,
    submodule_search_locations=[str(module_path.parent)],
)
assert spec is not None
assert spec.loader is not None
editor_core = importlib.util.module_from_spec(spec)
sys.modules["editor_core_under_test"] = editor_core
spec.loader.exec_module(editor_core)


def test_scene_name_from_file_path_uses_stem():
    assert editor_core.scene_name_from_file_path("/tmp/project/Scenes/MainLevel.tc_scene") == "MainLevel"
