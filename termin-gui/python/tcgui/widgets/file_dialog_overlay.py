"""File dialogs implemented in tcgui overlay layer."""

from __future__ import annotations

import fnmatch
import os
from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence

from tcbase import log
from tcgui.widgets.button import Button
from tcgui.widgets.combo_box import ComboBox
from tcgui.widgets.dialog import Dialog
from tcgui.widgets.hstack import HStack
from tcgui.widgets.icon_theme import FileIconProvider
from tcgui.widgets.label import Label
from tcgui.widgets.list_widget import ListWidget
from tcgui.widgets.panel import Panel
from tcgui.widgets.text_input import TextInput
from tcgui.widgets.units import px
from tcgui.widgets.vstack import VStack

FilterSpec = tuple[str, str]


def parse_filter_string(filter_str: str) -> list[FilterSpec]:
    """Parse ``'Label | *.ext;;Label2 | *.x *.y'`` to filter list."""
    if not filter_str:
        return [("All files", "*.*")]

    result: list[FilterSpec] = []
    for raw_part in filter_str.split(";;"):
        part = raw_part.strip()
        if not part:
            continue
        if "|" in part:
            label, exts = part.split("|", 1)
            result.append((label.strip() or "Files", exts.strip() or "*.*"))
        else:
            result.append((part, "*.*"))

    return result or [("All files", "*.*")]


class _OverlayFileDialog:
    def __init__(
        self,
        *,
        mode: str,
        title: str,
        directory: str,
        filter_str: str,
        filetypes: Sequence[FilterSpec] | None,
        on_result: Callable[[str | None], None],
    ):
        self._mode = mode
        self._on_result = on_result
        self._filters = parse_filter_string(filter_str) if filetypes is None else list(filetypes)
        self._current_dir = self._normalize_start_dir(directory)
        self._selected_path: Path | None = None
        self._back_stack: list[Path] = []
        self._forward_stack: list[Path] = []
        self._places: list[tuple[str, Path]] = self._build_places()
        self._icons = FileIconProvider(size=20)

        self._dialog = Dialog()
        self._dialog.title = title
        self._dialog.min_width = 1020
        self._dialog.title_height = 42
        self._dialog.padding = 14
        self._dialog.button_bar_height = 50
        self._dialog.background_color = (0.12, 0.13, 0.15, 1.0)
        self._dialog.title_background_color = (0.08, 0.09, 0.11, 1.0)
        self._dialog.border_radius = 8

        self._back_button = self._make_nav_button("←", self._go_back)
        self._forward_button = self._make_nav_button("→", self._go_forward)
        self._up_button = self._make_nav_button("↑", self._go_up)
        self._home_button = self._make_nav_button("⌂", self._go_home)

        self._path_input = TextInput()
        self._path_input.stretch = True
        self._path_input.font_size = 13
        self._path_input.on_submit = lambda text: self._open_path(text.strip())

        self._go_button = Button()
        self._go_button.text = "Go"
        self._go_button.preferred_width = px(56)
        self._go_button.preferred_height = px(30)
        self._go_button.on_click = lambda: self._open_path(self._path_input.text.strip())

        self._new_folder_button = Button()
        self._new_folder_button.text = "New Folder"
        self._new_folder_button.preferred_width = px(110)
        self._new_folder_button.preferred_height = px(30)
        self._new_folder_button.on_click = self._create_new_folder

        self._places_list = ListWidget()
        self._places_list.preferred_height = px(380)
        self._places_list.item_height = 34
        self._places_list.font_size = 13
        self._places_list.subtitle_font_size = 11
        self._places_list.on_select = self._on_place_select
        self._places_list.on_activate = self._on_place_select
        self._places_list.item_background = (0.17, 0.18, 0.22, 0.6)
        self._places_list.icon_provider = self._icons
        self._places_list.icon_size = 18

        self._list = ListWidget()
        self._list.preferred_height = px(380)
        self._list.item_height = 40
        self._list.font_size = 13
        self._list.subtitle_font_size = 11
        self._list.on_select = self._on_select
        self._list.on_activate = self._on_activate
        self._list.item_background = (0.17, 0.18, 0.22, 0.5)
        self._list.selected_background = (0.22, 0.43, 0.74, 0.95)
        self._list.icon_provider = self._icons
        self._list.icon_size = 20

        self._selection_label = Label()
        self._selection_label.font_size = 12
        self._selection_label.color = (0.7, 0.73, 0.79, 1.0)
        self._selection_label.text = "Selection: none"

        self._name_input = TextInput()
        self._name_input.stretch = True
        self._name_input.placeholder = "File name"
        self._name_input.on_submit = lambda _text: self._confirm()

        self._filter_combo = ComboBox()
        self._filter_combo.preferred_width = px(300)
        self._filter_combo.items = [f"{label} ({patterns})" for label, patterns in self._filters]
        self._filter_combo.selected_index = 0 if self._filter_combo.items else -1
        self._filter_combo.on_changed = self._on_filter_changed

        self._error_label = Label()
        self._error_label.font_size = 12
        self._error_label.color = (0.94, 0.47, 0.44, 1.0)
        self._error_label.text = ""

        self._dialog.content = self._build_content()
        self._configure_dialog_buttons()
        self._dialog.on_result = self._on_dialog_result

        self._refresh_places()
        self._refresh_list()
        self._update_nav_buttons()

    def show(self, ui, *, windowed: bool = False) -> None:
        self._dialog.show(ui, windowed=windowed)

    def _configure_dialog_buttons(self) -> None:
        if self._mode == "open_file":
            self._dialog.buttons = ["Open", "Cancel"]
            self._dialog.default_button = "Open"
        elif self._mode == "save_file":
            self._dialog.buttons = ["Save", "Cancel"]
            self._dialog.default_button = "Save"
        else:
            self._dialog.buttons = ["Select", "Cancel"]
            self._dialog.default_button = "Select"
        self._dialog.cancel_button = "Cancel"

    def _build_content(self) -> VStack:
        root = VStack()
        root.spacing = 10

        nav_row = HStack()
        nav_row.spacing = 6
        nav_row.add_child(self._back_button)
        nav_row.add_child(self._forward_button)
        nav_row.add_child(self._up_button)
        nav_row.add_child(self._home_button)
        nav_row.add_child(self._path_input)
        nav_row.add_child(self._go_button)
        nav_row.add_child(self._new_folder_button)

        places_title = Label()
        places_title.text = "Places"
        places_title.font_size = 12
        places_title.color = (0.75, 0.79, 0.86, 1.0)

        places_column = VStack()
        places_column.spacing = 8
        places_column.add_child(places_title)
        places_column.add_child(self._places_list)

        places_panel = Panel()
        places_panel.preferred_width = px(260)
        places_panel.padding = 10
        places_panel.border_radius = 6
        places_panel.background_color = (0.14, 0.15, 0.18, 0.95)
        places_panel.add_child(places_column)

        files_title = Label()
        files_title.text = "Directory contents"
        files_title.font_size = 12
        files_title.color = (0.75, 0.79, 0.86, 1.0)

        files_column = VStack()
        files_column.spacing = 8
        files_column.add_child(files_title)
        files_column.add_child(self._list)
        files_column.add_child(self._selection_label)

        files_panel = Panel()
        files_panel.padding = 10
        files_panel.border_radius = 6
        files_panel.background_color = (0.15, 0.16, 0.2, 0.95)
        files_panel.add_child(files_column)

        body_row = HStack()
        body_row.spacing = 10
        files_panel.stretch = True
        body_row.add_child(places_panel)
        body_row.add_child(files_panel)

        root.add_child(nav_row)
        root.add_child(body_row)

        if self._mode == "save_file":
            name_row = HStack()
            name_row.spacing = 8
            name_label = Label()
            name_label.text = "File name:"
            name_label.preferred_width = px(80)
            name_label.font_size = 12
            name_label.color = (0.75, 0.79, 0.86, 1.0)
            name_row.add_child(name_label)
            name_row.add_child(self._name_input)
            root.add_child(name_row)

        if self._mode != "open_directory":
            filter_row = HStack()
            filter_row.spacing = 8
            filter_label = Label()
            filter_label.text = "File type:"
            filter_label.preferred_width = px(80)
            filter_label.font_size = 12
            filter_label.color = (0.75, 0.79, 0.86, 1.0)
            filter_row.add_child(filter_label)
            filter_row.add_child(self._filter_combo)
            root.add_child(filter_row)

        root.add_child(self._error_label)
        return root

    def _make_nav_button(self, text: str, callback: Callable[[], None]) -> Button:
        btn = Button()
        btn.text = text
        btn.preferred_width = px(30)
        btn.preferred_height = px(30)
        btn.font_size = 14
        btn.border_radius = 4
        btn.on_click = callback
        return btn

    def _normalize_start_dir(self, directory: str) -> Path:
        if directory:
            p = Path(directory).expanduser()
            if p.exists() and p.is_dir():
                return p.resolve()
        return Path.cwd()

    def _build_places(self) -> list[tuple[str, Path]]:
        places: list[tuple[str, Path]] = []

        def add_place(label: str, path: Path) -> None:
            try:
                resolved = path.expanduser().resolve()
            except Exception:
                resolved = path
            if resolved.exists() and resolved.is_dir():
                if all(existing != resolved for _, existing in places):
                    places.append((label, resolved))

        home = Path.home()
        add_place("Home", home)
        add_place("Project", Path.cwd())
        add_place("Root", Path("/"))
        add_place("Temp", Path("/tmp"))

        for folder in ("Desktop", "Documents", "Downloads", "Pictures"):
            add_place(folder, home / folder)

        for mount_root in (Path("/media"), Path("/mnt")):
            if not mount_root.exists() or not mount_root.is_dir():
                continue
            try:
                for entry in sorted(mount_root.iterdir(), key=lambda p: p.name.lower()):
                    if entry.is_dir():
                        add_place(entry.name, entry)
            except Exception:
                continue

        return places

    def _refresh_places(self) -> None:
        items = []
        for label, path in self._places:
            items.append({
                "text": label,
                "subtitle": str(path),
                "icon_type": self._icons.icon_type_for_directory(),
                "data": {"path": str(path)},
            })
        self._places_list.set_items(items)

    def _go_home(self) -> None:
        self._navigate_to(Path.home(), push_history=True)

    def _go_up(self) -> None:
        parent = self._current_dir.parent
        if parent != self._current_dir and parent.exists():
            self._navigate_to(parent, push_history=True)

    def _go_back(self) -> None:
        if not self._back_stack:
            return
        target = self._back_stack.pop()
        self._forward_stack.append(self._current_dir)
        self._navigate_to(target, push_history=False)

    def _go_forward(self) -> None:
        if not self._forward_stack:
            return
        target = self._forward_stack.pop()
        self._back_stack.append(self._current_dir)
        self._navigate_to(target, push_history=False)

    def _open_path(self, text: str) -> None:
        if not text:
            return
        candidate = Path(text).expanduser()
        if not candidate.is_absolute():
            candidate = (self._current_dir / candidate).resolve()
        self._navigate_to(candidate, push_history=True, allow_select_file=(self._mode == "open_file"))

    def _navigate_to(self, path: Path, *, push_history: bool, allow_select_file: bool = False) -> None:
        try:
            resolved = path.resolve()
        except Exception:
            self._set_error(f"Cannot resolve path: {path}")
            return

        if resolved.exists() and resolved.is_dir():
            if push_history and resolved != self._current_dir:
                self._back_stack.append(self._current_dir)
                self._forward_stack.clear()
            self._current_dir = resolved
            self._selected_path = None
            self._set_error("")
            self._refresh_list()
            self._update_nav_buttons()
            return

        if resolved.exists() and resolved.is_file() and allow_select_file:
            self._selected_path = resolved
            self._resolve_and_close(str(resolved))
            return

        self._set_error(f"Path not available: {path}")

    def _refresh_list(self) -> None:
        self._path_input.text = str(self._current_dir)
        self._path_input.cursor_pos = len(self._path_input.text)
        self._selection_label.text = "Selection: none"
        items: list[dict] = []

        try:
            entries = list(os.scandir(self._current_dir))
        except Exception as exc:
            self._set_error(f"Failed to open {self._current_dir}: {exc}")
            self._list.set_items([])
            return

        self._set_error("")

        dirs = sorted((e for e in entries if e.is_dir(follow_symlinks=False)), key=lambda e: e.name.lower())
        files = sorted((e for e in entries if e.is_file(follow_symlinks=False)), key=lambda e: e.name.lower())

        for entry in dirs:
            suffix = self._safe_subtitle(entry.path, is_dir=True)
            subtitle = f"Folder   {suffix}" if suffix else "Folder"
            items.append({
                "text": entry.name,
                "subtitle": subtitle,
                "icon_type": self._icons.icon_type_for_directory(),
                "data": {"path": entry.path, "is_dir": True},
            })

        if self._mode != "open_directory":
            for entry in files:
                if not self._accept_file(entry.name):
                    continue
                subtitle = self._safe_subtitle(entry.path, is_dir=False)
                items.append({
                    "text": entry.name,
                    "subtitle": subtitle,
                    "icon_type": self._icons.icon_type_for_file(entry.name),
                    "data": {"path": entry.path, "is_dir": False},
                })

        self._list.set_items(items)

    def _safe_subtitle(self, path: str, *, is_dir: bool) -> str:
        try:
            st = os.stat(path)
            stamp = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
            if is_dir:
                return f"Modified: {stamp}"
            return f"{self._format_size(st.st_size)}  Modified: {stamp}"
        except Exception:
            return ""

    def _format_size(self, size: int) -> str:
        value = float(size)
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024.0:
                return f"{int(value)} B" if unit == "B" else f"{value:.1f} {unit}"
            value /= 1024.0
        return f"{value:.1f} TB"

    def _active_patterns(self) -> list[str]:
        if not self._filters:
            return ["*"]
        idx = self._filter_combo.selected_index
        if idx < 0 or idx >= len(self._filters):
            idx = 0
        patterns = self._filters[idx][1].split()
        return patterns or ["*"]

    def _accept_file(self, name: str) -> bool:
        lower_name = name.lower()
        for pattern in self._active_patterns():
            p = pattern.strip()
            if not p:
                continue
            if p in ("*", "*.*"):
                return True
            if fnmatch.fnmatch(lower_name, p.lower()):
                return True
        return False

    def _on_filter_changed(self, _index: int, _text: str) -> None:
        self._refresh_list()

    def _on_place_select(self, _index: int, item: dict) -> None:
        data = item.get("data") or {}
        path = data.get("path")
        if path:
            self._navigate_to(Path(path), push_history=True)

    def _on_select(self, _index: int, item: dict) -> None:
        data = item.get("data") or {}
        path = data.get("path")
        if not path:
            return
        self._selected_path = Path(path)
        self._selection_label.text = f"Selection: {self._selected_path}"
        if self._mode == "save_file" and not data.get("is_dir"):
            self._name_input.text = self._selected_path.name
            self._name_input.cursor_pos = len(self._name_input.text)

    def _on_activate(self, _index: int, item: dict) -> None:
        data = item.get("data") or {}
        path = data.get("path")
        if not path:
            return
        p = Path(path)
        is_dir = bool(data.get("is_dir"))

        if is_dir:
            self._navigate_to(p, push_history=True)
            return

        self._selected_path = p
        self._selection_label.text = f"Selection: {p}"
        if self._mode == "open_file":
            self._resolve_and_close(str(p))
        elif self._mode == "save_file":
            self._name_input.text = p.name
            self._name_input.cursor_pos = len(self._name_input.text)

    def _on_dialog_result(self, button: str) -> None:
        if button in ("Cancel", ""):
            self._resolve_and_close(None)
            return
        self._confirm()

    def _confirm(self) -> None:
        if self._mode == "open_file":
            if self._selected_path is None or self._selected_path.is_dir():
                self._set_error("Select a file to open.")
                return
            self._resolve_and_close(str(self._selected_path))
            return

        if self._mode == "open_directory":
            if self._selected_path is not None and self._selected_path.is_dir():
                self._resolve_and_close(str(self._selected_path))
            else:
                self._resolve_and_close(str(self._current_dir))
            return

        # save_file
        name = self._name_input.text.strip()
        if not name:
            if self._selected_path is not None and not self._selected_path.is_dir():
                name = self._selected_path.name
            else:
                self._set_error("Enter file name.")
                return
        out = self._current_dir / name
        self._resolve_and_close(str(out))

    def _create_new_folder(self) -> None:
        base = "New Folder"
        candidate = self._current_dir / base
        suffix = 2
        while candidate.exists():
            candidate = self._current_dir / f"{base} {suffix}"
            suffix += 1
        try:
            candidate.mkdir(parents=False, exist_ok=False)
        except Exception as exc:
            self._set_error(f"Cannot create folder: {exc}")
            return
        self._navigate_to(candidate, push_history=True)

    def _set_error(self, message: str) -> None:
        self._error_label.text = message
        if message:
            log.error(f"[file_dialog_overlay] {message}")

    def _update_nav_buttons(self) -> None:
        self._back_button.enabled = len(self._back_stack) > 0
        self._forward_button.enabled = len(self._forward_stack) > 0
        self._up_button.enabled = self._current_dir.parent != self._current_dir

    def _resolve_and_close(self, path: str | None) -> None:
        try:
            self._on_result(path)
        finally:
            self._dialog.close()


def show_open_file_dialog(
    ui,
    on_result: Callable[[str | None], None],
    *,
    title: str = "Open File",
    directory: str = "",
    filter_str: str = "",
    filetypes: Sequence[FilterSpec] | None = None,
    windowed: bool = False,
) -> None:
    """Show open-file dialog. Result is delivered via callback."""
    dlg = _OverlayFileDialog(
        mode="open_file",
        title=title,
        directory=directory,
        filter_str=filter_str,
        filetypes=filetypes,
        on_result=on_result,
    )
    dlg.show(ui, windowed=windowed)


def show_save_file_dialog(
    ui,
    on_result: Callable[[str | None], None],
    *,
    title: str = "Save File",
    directory: str = "",
    filter_str: str = "",
    filetypes: Sequence[FilterSpec] | None = None,
    windowed: bool = False,
) -> None:
    """Show save-file dialog. Result is delivered via callback."""
    dlg = _OverlayFileDialog(
        mode="save_file",
        title=title,
        directory=directory,
        filter_str=filter_str,
        filetypes=filetypes,
        on_result=on_result,
    )
    dlg.show(ui, windowed=windowed)


def show_open_directory_dialog(
    ui,
    on_result: Callable[[str | None], None],
    *,
    title: str = "Open Directory",
    directory: str = "",
    windowed: bool = False,
) -> None:
    """Show open-directory dialog. Result is delivered via callback."""
    dlg = _OverlayFileDialog(
        mode="open_directory",
        title=title,
        directory=directory,
        filter_str="",
        filetypes=None,
        on_result=on_result,
    )
    dlg.show(ui, windowed=windowed)
