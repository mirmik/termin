from tcbase import Key
from tcgui.widgets.events import KeyEvent
from tcgui.widgets.file_grid_widget import FileGridWidget
from tcgui.widgets.label import Label
from tcgui.widgets.menu import Menu, MenuItem
from tcgui.widgets.tree import TreeNode, TreeWidget

from termin.editor_tcgui.project_browser import ProjectBrowserTcgui, _get_file_subtitle
from termin.project.settings import ProjectSettings, ProjectSettingsManager


class _DummyUi:
    def __init__(self) -> None:
        self.clipboard_text = ""

    def set_clipboard_text(self, text: str) -> None:
        self.clipboard_text = text


class _DummyWidget:
    def __init__(self, ui) -> None:
        self._ui = ui


class _DummyProjectOps:
    def __init__(self) -> None:
        self.created_files = []
        self.deleted_paths = []

    def create_file(self, base_dir, on_refresh) -> None:
        self.created_files.append(base_dir)

    def delete_item(self, path, on_refresh) -> None:
        self.deleted_paths.append(path)


def test_project_browser_copy_absolute_path_uses_ui_clipboard(tmp_path):
    target = tmp_path / "assets" / "scene.scene"
    ui = _DummyUi()
    browser = ProjectBrowserTcgui.__new__(ProjectBrowserTcgui)
    browser._file_list = _DummyWidget(ui)
    browser._dir_tree = _DummyWidget(None)

    browser._copy_absolute_path(target)

    assert ui.clipboard_text == str(target.resolve(strict=False))


def test_project_browser_labels_stl_as_mesh(tmp_path):
    assert _get_file_subtitle(tmp_path / "piece.stl") == "Mesh"


def test_project_browser_labels_scene_as_scene(tmp_path):
    assert _get_file_subtitle(tmp_path / "scene.scene") == "Scene"


def test_project_browser_hides_project_ignored_paths(tmp_path, monkeypatch):
    manager = ProjectSettingsManager()
    manager._settings = ProjectSettings(ignored_resource_paths=["tests"])
    monkeypatch.setattr(ProjectSettingsManager, "_instance", manager)

    visible_path = tmp_path / "Scripts"
    visible_path.mkdir()
    ignored_path = tmp_path / "tests"
    ignored_path.mkdir()

    browser = ProjectBrowserTcgui.__new__(ProjectBrowserTcgui)
    browser._root_path = tmp_path

    assert browser._should_show_entry(visible_path)
    assert not browser._should_show_entry(ignored_path)


def test_file_grid_delete_key_dispatches_selected_item() -> None:
    grid = FileGridWidget()
    grid.layout(0.0, 0.0, 200.0, 120.0, 200.0, 120.0)
    grid.set_items([
        {"text": "one", "data": "one"},
        {"text": "two", "data": "two"},
    ])
    grid.selected_index = 1

    deleted = []
    grid.on_delete = lambda index, item: deleted.append((index, item["data"]))

    assert grid.focusable
    assert grid.on_key_down(KeyEvent(Key.DELETE))
    assert deleted == [(1, "two")]


def test_tree_delete_key_dispatches_selected_node() -> None:
    tree = TreeWidget()
    node = TreeNode(Label())
    tree.add_root(node)
    tree._rebuild_visible()
    tree._select_node(node)

    deleted = []
    tree.on_delete = lambda selected: deleted.append(selected)

    assert tree.on_key_down(KeyEvent(Key.DELETE))
    assert deleted == [node]


def test_menu_item_accepts_submenu_items() -> None:
    clicked = []
    submenu_items = [MenuItem("Child", on_click=lambda: clicked.append("child"))]
    item = MenuItem("Parent", submenu=submenu_items)
    menu = Menu()

    submenu = menu._submenu_for_item(item)

    assert isinstance(submenu, Menu)
    assert submenu.items == submenu_items


def test_submenu_dismiss_clears_parent_child_link() -> None:
    parent = Menu()
    child = Menu()
    parent._child_menu = child
    child._parent_menu = parent

    child._on_dismissed()

    assert parent._child_menu is None


def test_project_browser_delete_key_routes_selected_file(tmp_path):
    path = tmp_path / "asset.scene"
    ops = _DummyProjectOps()
    browser = ProjectBrowserTcgui.__new__(ProjectBrowserTcgui)
    browser._ops = ops

    browser._on_file_delete(0, {"data": path})

    assert ops.deleted_paths == [path]


def test_project_browser_create_file_uses_selected_directory(tmp_path):
    ops = _DummyProjectOps()
    browser = ProjectBrowserTcgui.__new__(ProjectBrowserTcgui)
    browser._ops = ops
    browser._selected_dir = tmp_path

    browser._create_file()
    browser._create_file_in(tmp_path / "assets")

    assert ops.created_files == [tmp_path, tmp_path / "assets"]
