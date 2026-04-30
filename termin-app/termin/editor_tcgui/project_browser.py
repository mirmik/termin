"""ProjectBrowserTcgui — file browser panel for the tcgui editor.

Shows a directory tree on the left and file list on the right.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable
import subprocess
import platform

from tcbase import log
from tcgui.widgets.icon_theme import FileIconProvider
from tcgui.widgets.menu import Menu, MenuItem

from termin.editor_core.project_operations import ProjectOperations, sync_stdlib


# File extensions that are recognized as known asset types
_KNOWN_EXTENSIONS = {
    ".material": "Material",
    ".pipeline": "Pipeline",
    ".prefab": "Prefab",
    ".shader": "Shader",
    ".py": "Python",
    ".tc_scene": "Scene",
    ".tc_mat": "Material",
    ".tc_pipeline": "Pipeline",
    ".tc_component": "Component",
    ".glb": "GLB",
    ".gltf": "GLTF",
    ".glsl": "GLSL",
    ".png": "Texture",
    ".jpg": "Texture",
    ".jpeg": "Texture",
    ".bmp": "Texture",
    ".hdr": "HDR",
    ".exr": "EXR",
    ".obj": "Mesh",
    ".fbx": "Mesh",
    ".wav": "Audio",
    ".ogg": "Audio",
    ".mp3": "Audio",
    ".tc_prefab": "Prefab",
    ".tc_navmesh": "NavMesh",
    ".terminproj": "Project",
}


def _get_file_subtitle(path: Path) -> str:
    """Return asset type label for a file, or its extension."""
    ext = path.suffix.lower()
    return _KNOWN_EXTENSIONS.get(ext, ext.lstrip(".").upper() if ext else "File")


class ProjectBrowserTcgui:
    """Project browser panel: directory tree + file list.

    Usage::

        browser = ProjectBrowserTcgui(
            dir_tree=tree_widget,
            file_list=list_widget,
            on_file_activated=lambda path: ...,
        )
        browser.set_root("/path/to/project")
    """

    def __init__(
        self,
        dir_tree,
        file_list,
        breadcrumb,
        dialog_service,
        on_file_activated: Callable[[str], None] | None = None,
        on_file_selected: Callable[[str], None] | None = None,
    ) -> None:
        from tcgui.widgets.tree import TreeWidget, TreeNode
        from tcgui.widgets.file_grid_widget import FileGridWidget
        from tcgui.widgets.hstack import HStack

        self._dir_tree: TreeWidget = dir_tree
        self._file_list: FileGridWidget = file_list
        self._breadcrumb: HStack = breadcrumb
        self.on_file_activated: Callable[[str], None] | None = on_file_activated
        self.on_file_selected: Callable[[str], None] | None = on_file_selected

        self._root_path: Path | None = None
        self._selected_dir: Path | None = None
        self._ops = ProjectOperations(dialog_service)
        self._icons = FileIconProvider(size=40)
        self._file_list.icon_provider = self._icons

        # Wire up callbacks
        self._dir_tree.on_select = self._on_dir_selected
        self._dir_tree.on_context_menu = self._on_dir_context_menu
        self._file_list.on_select = self._on_file_selected
        self._file_list.on_activate = self._on_file_activated
        self._file_list.on_context_menu = self._on_file_context_menu

    @property
    def root_path(self) -> Path | None:
        return self._root_path

    def set_root(self, path: str | Path) -> None:
        """Set project root directory and populate the tree."""
        root = Path(path)
        if not root.is_dir():
            log.error(f"[ProjectBrowserTcgui] set_root: not a directory: {path}")
            return

        sync_stdlib(root)

        self._root_path = root
        self._selected_dir = root
        self._rebuild_tree()
        self._show_files(root)

    def refresh(self) -> None:
        """Refresh tree and file list from disk."""
        if self._root_path is None:
            return
        self._rebuild_tree()
        if self._selected_dir is not None and self._selected_dir.is_dir():
            self._show_files(self._selected_dir)
        else:
            self._show_files(self._root_path)

    # ------------------------------------------------------------------
    # Internal: tree population
    # ------------------------------------------------------------------

    def _make_dir_node(self, name: str, directory: Path) -> object:
        from tcgui.widgets.tree import TreeNode
        from tcgui.widgets.label import Label

        lbl = Label()
        lbl.text = name
        node = TreeNode(lbl)
        node.data = directory
        return node

    def _rebuild_tree(self) -> None:
        # Clear existing tree
        self._dir_tree.clear()
        # Wire up lazy expand callback
        self._dir_tree.on_expand = self._on_node_expanded

        if self._root_path is None:
            return

        root_node = self._make_dir_node(self._root_path.name, self._root_path)
        root_node.expanded = True
        self._dir_tree.add_root(root_node)

        self._populate_dir_node(root_node, self._root_path)

    def _populate_dir_node(self, node, directory: Path) -> None:
        try:
            entries = sorted(
                (e for e in directory.iterdir() if e.is_dir() and not e.name.startswith(".")),
                key=lambda e: e.name.lower(),
            )
        except PermissionError:
            return

        for entry in entries:
            child = self._make_dir_node(entry.name, entry)
            node.add_node(child)
            # Add placeholder so the expand arrow appears for dirs with subdirs
            if self._has_subdirs(entry):
                from tcgui.widgets.tree import TreeNode
                from tcgui.widgets.label import Label
                placeholder_lbl = Label()
                placeholder_lbl.text = "..."
                placeholder = TreeNode(placeholder_lbl)
                placeholder.data = None
                child.add_node(placeholder)

    def _has_subdirs(self, directory: Path) -> bool:
        try:
            for e in directory.iterdir():
                if e.is_dir() and not e.name.startswith("."):
                    return True
        except PermissionError:
            pass
        return False

    def _on_node_expanded(self, node) -> None:
        """Lazy-load children when a dir node is expanded."""
        directory = node.data
        if directory is None or not isinstance(directory, Path):
            return

        # If only has a placeholder, replace with real children
        if (len(node.subnodes) == 1 and node.subnodes[0].data is None):
            node.remove_node(node.subnodes[0])
            self._populate_dir_node(node, directory)
            self._dir_tree._dirty = True

    # ------------------------------------------------------------------
    # Internal: file list
    # ------------------------------------------------------------------

    def _show_files(self, directory: Path) -> None:
        self._selected_dir = directory
        self._rebuild_breadcrumb()
        try:
            entries = sorted(
                (e for e in directory.iterdir() if not e.name.startswith(".")),
                key=lambda e: (not e.is_dir(), e.name.lower()),
            )
        except PermissionError:
            self._file_list.set_items([])
            return

        items = []
        for entry in entries:
            if entry.is_dir():
                items.append({
                    "text": entry.name,
                    "subtitle": "Folder",
                    "icon_type": self._icons.icon_type_for_directory(),
                    "data": entry,
                })
                continue
            if not entry.is_file():
                continue
            items.append({
                "text": entry.name,
                "subtitle": _get_file_subtitle(entry),
                "icon_type": self._icons.icon_type_for_file(entry.name),
                "data": entry,
            })

        self._file_list.set_items(items)
        if self._file_list._ui is not None:
            self._file_list._ui.request_layout()

    def _rebuild_breadcrumb(self) -> None:
        from tcgui.widgets.button import Button
        from tcgui.widgets.label import Label
        from tcgui.widgets.theme import current_theme as t

        for child in self._breadcrumb.children[:]:
            self._breadcrumb.remove_child(child)
        if self._root_path is None or self._selected_dir is None:
            return

        paths: list[tuple[str, Path]] = [(self._root_path.name or str(self._root_path), self._root_path)]
        try:
            rel = self._selected_dir.relative_to(self._root_path)
            for part in rel.parts:
                paths.append((part, paths[-1][1] / part))
        except ValueError:
            paths = [(self._selected_dir.name or str(self._selected_dir), self._selected_dir)]

        for idx, (label, path) in enumerate(paths):
            if idx > 0:
                sep = Label()
                sep.text = ">"
                sep.font_size = 12
                sep.color = t.text_muted
                self._breadcrumb.add_child(sep)

            btn = Button()
            btn.text = label
            btn.font_size = 12
            btn.padding = 4
            btn.border_radius = 3
            btn.background_color = (0.0, 0.0, 0.0, 0.0)
            btn.hover_color = t.hover_subtle
            btn.pressed_color = t.pressed
            btn.text_color = t.text_secondary if idx < len(paths) - 1 else t.text_primary
            btn.on_click = lambda p=path: self._show_files(p)
            self._breadcrumb.add_child(btn)

        if self._breadcrumb._ui is not None:
            self._breadcrumb._ui.request_layout()

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_dir_selected(self, node) -> None:
        directory = node.data
        if directory is None or not isinstance(directory, Path):
            return
        self._show_files(directory)

    def _on_file_selected(self, index: int, item: dict) -> None:
        path: Path | None = item.get("data")
        if path is None or path.is_dir():
            return
        if self.on_file_selected is not None:
            self.on_file_selected(str(path))

    def _on_file_activated(self, index: int, item: dict) -> None:
        path: Path | None = item.get("data")
        if path is None:
            return
        if path.is_dir():
            self._show_files(path)
            return
        if self.on_file_activated is not None:
            self.on_file_activated(str(path))

    def _on_file_context_menu(self, index: int, item: dict, x: float, y: float) -> None:
        if self._root_path is None or self._selected_dir is None:
            return
        ui = self._file_list._ui
        if ui is None:
            return

        path: Path | None = item.get("data")
        has_file = path is not None and path.is_file()
        has_dir = path is not None and path.is_dir()

        menu = Menu()
        items: list[MenuItem] = []

        if self._can_go_up():
            items.append(MenuItem("Go Up", on_click=self._go_up))
            items.append(MenuItem("Go to Root", on_click=self._go_to_root))
            items.append(MenuItem.sep())

        if has_file and path is not None:
            items.append(MenuItem("Open", on_click=lambda p=path: self._open_file(p)))
            if path.suffix.lower() == ".fbx":
                items.append(MenuItem("Extract FBX...", on_click=lambda p=path: self._extract_fbx(p)))
            if path.suffix.lower() == ".glb":
                items.append(MenuItem("Extract GLB...", on_click=lambda p=path: self._extract_glb(p)))
            items.append(MenuItem.sep())
            items.append(MenuItem("Show in Explorer", on_click=lambda p=path: self._reveal_in_explorer(p)))
            items.append(MenuItem("Delete", on_click=lambda p=path: self._delete_item(p)))
            items.append(MenuItem.sep())
        elif has_dir and path is not None:
            items.append(MenuItem("Open", on_click=lambda p=path: self._show_files(p)))
            items.append(MenuItem.sep())
            items.append(MenuItem("Show in Explorer", on_click=lambda p=path: self._reveal_in_explorer(p)))
            items.append(MenuItem("Delete", on_click=lambda p=path: self._delete_item(p)))
            items.append(MenuItem.sep())

        items.append(MenuItem("Create: Directory...", on_click=self._create_directory))
        items.append(MenuItem("Create: Material...", on_click=self._create_material))
        items.append(MenuItem("Create: Shader...", on_click=self._create_shader))
        items.append(MenuItem("Create: Component...", on_click=self._create_component))
        items.append(MenuItem("Create: Render Pipeline...", on_click=self._create_pipeline))
        items.append(MenuItem("Create: Prefab...", on_click=self._create_prefab))
        items.append(MenuItem.sep())
        items.append(MenuItem("Refresh", on_click=self.refresh))

        menu.items = items
        menu.show(ui, x, y)

    def _on_dir_context_menu(self, node, x: float, y: float) -> None:
        if self._root_path is None:
            return
        ui = self._dir_tree._ui
        if ui is None:
            return

        directory = self._root_path
        if node is not None and isinstance(node.data, Path):
            directory = node.data

        menu = Menu()
        items: list[MenuItem] = []
        if self._can_go_up():
            items.append(MenuItem("Go Up", on_click=self._go_up))
            items.append(MenuItem("Go to Root", on_click=self._go_to_root))
            items.append(MenuItem.sep())
        items.append(MenuItem("Show in Explorer", on_click=lambda p=directory: self._reveal_in_explorer(p)))
        items.append(MenuItem("Create: Directory...", on_click=lambda d=directory: self._create_directory_in(d)))
        items.append(MenuItem("Refresh", on_click=self.refresh))
        menu.items = items
        menu.show(ui, x, y)

    def _can_go_up(self) -> bool:
        if self._root_path is None or self._selected_dir is None:
            return False
        return self._selected_dir != self._root_path

    def _go_up(self) -> None:
        if not self._can_go_up() or self._selected_dir is None:
            return
        parent = self._selected_dir.parent
        self._show_files(parent)

    def _go_to_root(self) -> None:
        if self._root_path is None:
            return
        self._show_files(self._root_path)

    def _open_file(self, file_path: Path) -> None:
        if self.on_file_activated is not None:
            self.on_file_activated(str(file_path))

    def _reveal_in_explorer(self, path: Path) -> None:
        try:
            if platform.system() == "Windows":
                if path.is_file():
                    subprocess.run(["explorer", "/select,", str(path)])
                else:
                    subprocess.run(["explorer", str(path)])
            elif platform.system() == "Darwin":
                subprocess.run(["open", "-R", str(path)])
            else:
                subprocess.run(["xdg-open", str(path.parent if path.is_file() else path)])
        except Exception as e:
            log.error(f"[ProjectBrowserTcgui] reveal failed: {e}")

    def _create_directory(self) -> None:
        self._ops.create_directory(self._selected_dir, self.refresh)

    def _delete_item(self, path: Path) -> None:
        self._ops.delete_item(path, self.refresh)

    def _extract_fbx(self, fbx_path: Path) -> None:
        self._ops.extract_fbx(fbx_path, self.refresh)

    def _extract_glb(self, glb_path: Path) -> None:
        self._ops.extract_glb(glb_path, self.refresh)

    def _create_material(self) -> None:
        self._ops.create_material(self._selected_dir, self.refresh)

    def _create_shader(self) -> None:
        self._ops.create_shader(self._selected_dir, self.refresh)

    def _create_component(self) -> None:
        self._ops.create_component(self._selected_dir, self.refresh)

    def _create_pipeline(self) -> None:
        self._ops.create_pipeline(self._selected_dir, self.refresh)

    def _create_prefab(self) -> None:
        self._ops.create_prefab(self._selected_dir, self.refresh)
