"""ProjectBrowserTcgui — file browser panel for the tcgui editor.

Shows a directory tree on the left and file list on the right.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from tcbase import log


# File extensions that are recognized as known asset types
_KNOWN_EXTENSIONS = {
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
        on_file_activated: Callable[[str], None] | None = None,
        on_file_selected: Callable[[str], None] | None = None,
    ) -> None:
        from tcgui.widgets.tree import TreeWidget, TreeNode
        from tcgui.widgets.list_widget import ListWidget

        self._dir_tree: TreeWidget = dir_tree
        self._file_list: ListWidget = file_list
        self.on_file_activated: Callable[[str], None] | None = on_file_activated
        self.on_file_selected: Callable[[str], None] | None = on_file_selected

        self._root_path: Path | None = None
        self._selected_dir: Path | None = None

        # Wire up callbacks
        self._dir_tree.on_select = self._on_dir_selected
        self._file_list.on_select = self._on_file_selected
        self._file_list.on_activate = self._on_file_activated

    @property
    def root_path(self) -> Path | None:
        return self._root_path

    def set_root(self, path: str | Path) -> None:
        """Set project root directory and populate the tree."""
        root = Path(path)
        if not root.is_dir():
            log.error(f"[ProjectBrowserTcgui] set_root: not a directory: {path}")
            return

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
        try:
            entries = sorted(
                (e for e in directory.iterdir() if e.is_file() and not e.name.startswith(".")),
                key=lambda e: e.name.lower(),
            )
        except PermissionError:
            self._file_list.set_items([])
            return

        items = []
        for entry in entries:
            items.append({
                "text": entry.name,
                "subtitle": _get_file_subtitle(entry),
                "data": entry,
            })

        self._file_list.set_items(items)

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
        if path is None:
            return
        if self.on_file_selected is not None:
            self.on_file_selected(str(path))

    def _on_file_activated(self, index: int, item: dict) -> None:
        path: Path | None = item.get("data")
        if path is None:
            return
        if self.on_file_activated is not None:
            self.on_file_activated(str(path))
