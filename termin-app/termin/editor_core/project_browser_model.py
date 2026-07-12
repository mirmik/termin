"""Toolkit-neutral project directory and file collection controller."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
import mimetypes
from pathlib import Path

from termin.project.ignored_paths import is_path_ignored, project_ignored_roots

from .project_operations import ProjectOperations


_logger = logging.getLogger(__name__)

_KNOWN_EXTENSIONS = {
    ".material": "Material",
    ".pipeline": "Pipeline",
    ".prefab": "Prefab",
    ".scene": "Scene",
    ".shader": "Shader",
    ".py": "Python",
    ".glb": "GLB",
    ".gltf": "GLTF",
    ".glsl": "GLSL",
    ".png": "Texture",
    ".jpg": "Texture",
    ".jpeg": "Texture",
    ".bmp": "Texture",
    ".hdr": "HDR",
    ".exr": "EXR",
    ".stl": "Mesh",
    ".obj": "Mesh",
    ".wav": "Audio",
    ".ogg": "Audio",
    ".mp3": "Audio",
    ".terminproj": "Project",
}

_EXACT_ICON_MIME_TYPES = {
    "application/pdf": "pdf",
    "application/zip": "archive",
    "application/gzip": "archive",
    "application/x-tar": "archive",
    "application/x-7z-compressed": "archive",
    "application/x-rar-compressed": "archive",
    "application/x-bzip2": "archive",
    "application/x-xz": "archive",
    "application/vnd.debian.binary-package": "archive",
    "application/vnd.ms-excel": "spreadsheet",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "spreadsheet",
    "application/vnd.oasis.opendocument.spreadsheet": "spreadsheet",
    "application/javascript": "code",
    "application/json": "code",
    "application/xml": "code",
    "application/x-httpd-php": "code",
    "text/html": "code",
    "text/css": "code",
    "text/xml": "code",
}

_CODE_TEXT_SUBTYPES = frozenset({
    "x-python", "x-csrc", "x-c++src", "x-java-source", "x-ruby", "x-sh",
    "x-shellscript", "x-makefile", "x-cmake", "rust", "x-rust", "x-go",
    "x-typescript", "x-kotlin", "x-lua",
})

_EXEC_SUBTYPES = frozenset({
    "x-executable", "x-sharedlib", "x-elf", "x-msdos-program", "x-msdownload",
})

_ARCHIVE_EXTENSIONS = frozenset({
    ".7z", ".bz2", ".gz", ".rar", ".tar", ".xz", ".zip",
})


def file_subtitle(path: Path) -> str:
    extension = path.suffix.lower()
    return _KNOWN_EXTENSIONS.get(
        extension,
        extension.lstrip(".").upper() if extension else "File",
    )


def file_icon_kind(path: Path) -> str:
    """Return the portable visual category used by project browser frontends.

    This is deliberately a semantic label rather than a frontend texture handle: the legacy
    and native editors may render it differently while retaining the same file classification.
    """

    if path.suffix.lower() in _ARCHIVE_EXTENSIONS:
        return "archive"

    mime_type, _encoding = mimetypes.guess_type(path.name)
    if mime_type is None:
        return "file"
    main_type, _separator, subtype = mime_type.partition("/")
    if main_type == "image":
        return "image"
    if main_type == "audio":
        return "audio"
    if main_type == "video":
        return "video"
    exact = _EXACT_ICON_MIME_TYPES.get(mime_type)
    if exact is not None:
        return exact
    if main_type == "text":
        return "code" if subtype in _CODE_TEXT_SUBTYPES else "file"
    if main_type == "application" and subtype in _EXEC_SUBTYPES:
        return "exec"
    return "file"


@dataclass(frozen=True)
class ProjectBrowserEntry:
    stable_id: str
    path: Path
    name: str
    subtitle: str
    is_directory: bool
    icon_kind: str


@dataclass(frozen=True)
class ProjectBrowserSnapshot:
    root_path: Path | None
    selected_directory: Path | None
    entries: tuple[ProjectBrowserEntry, ...]
    breadcrumb: tuple[tuple[str, Path], ...]
    revision: int

    @property
    def status(self) -> str:
        if self.selected_directory is None:
            return "No project is open"
        directories = sum(entry.is_directory for entry in self.entries)
        files = len(self.entries) - directories
        return f"{directories} directories | {files} files"


@dataclass(frozen=True)
class ProjectBrowserAction:
    stable_id: str
    label: str
    enabled: bool = True


class ProjectBrowserController:
    def __init__(
        self,
        *,
        on_file_selected: Callable[[Path], None] | None = None,
        on_file_activated: Callable[[Path], None] | None = None,
        copy_text: Callable[[str], None] | None = None,
        reveal_path: Callable[[Path], None] | None = None,
        delete_path: Callable[[Path, Callable[[], None]], None] | None = None,
        operations: ProjectOperations | None = None,
    ) -> None:
        self._on_file_selected = on_file_selected
        self._on_file_activated = on_file_activated
        self._copy_text = copy_text
        self._reveal_path = reveal_path
        self._delete_path = delete_path
        self._operations = operations
        self._mutation_refresh: Callable[[], None] = self.refresh
        self._mutation_navigate: Callable[[Path], None] = self.navigate
        self._root_path: Path | None = None
        self._selected_directory: Path | None = None
        self._entries: tuple[ProjectBrowserEntry, ...] = ()
        self._revision = 0

    @property
    def root_path(self) -> Path | None:
        return self._root_path

    @property
    def selected_directory(self) -> Path | None:
        return self._selected_directory

    def set_mutation_refresh(self, callback: Callable[[], None]) -> None:
        """Set the projection refresh invoked after asynchronous mutations."""
        self._mutation_refresh = callback

    def set_mutation_navigation(self, callback: Callable[[Path], None]) -> None:
        self._mutation_navigate = callback

    def set_root(self, path: str | Path) -> ProjectBrowserSnapshot:
        root = Path(path).resolve()
        if not root.is_dir():
            _logger.error("Project browser root is not a directory: %s", root)
            raise NotADirectoryError(root)
        self._root_path = root
        self._selected_directory = root
        return self.refresh()

    def refresh(self) -> ProjectBrowserSnapshot:
        if self._root_path is None:
            self._entries = ()
            self._revision += 1
            return self.snapshot()
        directory = self._selected_directory
        if directory is None or not directory.is_dir() or not self._is_visible_directory(directory):
            directory = self._root_path
            self._selected_directory = directory
        self._entries = self._scan_entries(directory)
        self._revision += 1
        return self.snapshot()

    def navigate(self, directory: str | Path) -> ProjectBrowserSnapshot:
        path = Path(directory).resolve()
        if not path.is_dir() or not self._is_visible_directory(path):
            _logger.error("Project browser rejected directory outside visible root: %s", path)
            raise ValueError(f"directory is outside the visible project root: {path}")
        self._selected_directory = path
        return self.refresh()

    def go_up(self) -> ProjectBrowserSnapshot:
        if self._root_path is None or self._selected_directory is None:
            return self.snapshot()
        if self._selected_directory == self._root_path:
            return self.snapshot()
        return self.navigate(self._selected_directory.parent)

    def go_to_root(self) -> ProjectBrowserSnapshot:
        return self.navigate(self._root_path) if self._root_path is not None else self.snapshot()

    def select_entry(self, index: int) -> ProjectBrowserSnapshot:
        entry = self._entry(index)
        if entry is not None and not entry.is_directory and self._on_file_selected is not None:
            self._on_file_selected(entry.path)
        return self.snapshot()

    def activate_entry(self, index: int) -> ProjectBrowserSnapshot:
        entry = self._entry(index)
        if entry is None:
            return self.snapshot()
        if entry.is_directory:
            return self.navigate(entry.path)
        if self._on_file_activated is not None:
            self._on_file_activated(entry.path)
        return self.snapshot()

    def drag_payload(self, index: int) -> dict[str, str] | None:
        entry = self._entry(index)
        if entry is None or entry.is_directory:
            return None
        return {
            "path": str(entry.path),
            "extension": entry.path.suffix.lower(),
            "name": entry.name,
        }

    def directory_children(self, directory: str | Path) -> tuple[Path, ...]:
        path = Path(directory).resolve()
        if not self._is_visible_directory(path):
            return ()
        return tuple(entry.path for entry in self._scan_entries(path) if entry.is_directory)

    def has_directory_children(self, directory: str | Path) -> bool:
        return bool(self.directory_children(directory))

    def context_actions(self, index: int) -> tuple[ProjectBrowserAction, ...]:
        entry = self._entry(index)
        operations = self._operations is not None
        can_go_up = (
            self._root_path is not None
            and self._selected_directory is not None
            and self._selected_directory != self._root_path
        )
        return (
            ProjectBrowserAction("open", "Open", entry is not None),
            ProjectBrowserAction("go-up", "Go Up", can_go_up),
            ProjectBrowserAction("go-root", "Go to Root", self._root_path is not None),
            ProjectBrowserAction("copy-path", "Copy Absolute Path", entry is not None and self._copy_text is not None),
            ProjectBrowserAction("reveal", "Show in Explorer", entry is not None and self._reveal_path is not None),
            ProjectBrowserAction("rename", "Rename...", entry is not None and operations),
            ProjectBrowserAction(
                "extract-glb",
                "Extract GLB...",
                entry is not None and operations and entry.path.suffix.lower() == ".glb",
            ),
            ProjectBrowserAction(
                "delete",
                "Delete",
                entry is not None and (self._delete_path is not None or operations),
            ),
            *self._creation_actions(),
            ProjectBrowserAction("refresh", "Refresh"),
        )

    def execute_context_action(self, action_id: str, index: int) -> ProjectBrowserSnapshot:
        entry = self._entry(index)
        if action_id == "open":
            return self.activate_entry(index)
        if action_id == "go-up":
            return self.go_up()
        if action_id == "go-root":
            return self.go_to_root()
        if action_id == "refresh":
            return self.refresh()
        if self._execute_creation_action(action_id, self._selected_directory):
            return self.snapshot()
        if entry is None:
            _logger.error("Project browser action %s requires an entry", action_id)
            raise IndexError("project browser action requires an entry")
        if action_id == "copy-path" and self._copy_text is not None:
            self._copy_text(str(entry.path.resolve(strict=False)))
        elif action_id == "reveal" and self._reveal_path is not None:
            self._reveal_path(entry.path)
        elif action_id == "delete" and self._delete_path is not None:
            self._delete_path(entry.path, self.refresh)
        elif action_id == "rename" and self._operations is not None:
            self._operations.rename_item(entry.path, self._mutation_refresh)
        elif action_id == "extract-glb" and self._operations is not None:
            self._operations.extract_glb(
                entry.path,
                self._mutation_refresh,
                self._mutation_navigate,
            )
        elif action_id == "delete" and self._operations is not None:
            self._operations.delete_item(entry.path, self._mutation_refresh)
        else:
            _logger.error("Unavailable project browser action: %s", action_id)
            raise RuntimeError(f"unavailable project browser action: {action_id}")
        return self.snapshot()

    def directory_context_actions(self, directory: str | Path) -> tuple[ProjectBrowserAction, ...]:
        path = Path(directory).resolve()
        visible = self._is_visible_directory(path)
        return (
            ProjectBrowserAction("open-directory", "Open", visible),
            ProjectBrowserAction(
                "copy-directory-path",
                "Copy Absolute Path",
                visible and self._copy_text is not None,
            ),
            ProjectBrowserAction(
                "reveal-directory",
                "Show in Explorer",
                visible and self._reveal_path is not None,
            ),
            *self._creation_actions(),
            ProjectBrowserAction("refresh", "Refresh", self._root_path is not None),
        )

    def execute_directory_context_action(
        self,
        action_id: str,
        directory: str | Path,
    ) -> ProjectBrowserSnapshot:
        path = Path(directory).resolve()
        if not self._is_visible_directory(path):
            _logger.error("Project browser directory action rejected path: %s", path)
            raise ValueError(f"directory is outside the visible project root: {path}")
        if action_id == "open-directory":
            return self.navigate(path)
        if action_id == "refresh":
            return self.refresh()
        if action_id == "copy-directory-path" and self._copy_text is not None:
            self._copy_text(str(path))
        elif action_id == "reveal-directory" and self._reveal_path is not None:
            self._reveal_path(path)
        elif self._execute_creation_action(action_id, path):
            pass
        else:
            _logger.error("Unavailable project browser directory action: %s", action_id)
            raise RuntimeError(f"unavailable project browser directory action: {action_id}")
        return self.snapshot()

    def _creation_actions(self) -> tuple[ProjectBrowserAction, ...]:
        enabled = self._operations is not None and self._selected_directory is not None
        return (
            ProjectBrowserAction("create-directory", "Create Directory...", enabled),
            ProjectBrowserAction("create-file", "Create File...", enabled),
            ProjectBrowserAction("create-material", "Create Material...", enabled),
            ProjectBrowserAction("create-shader", "Create Shader...", enabled),
            ProjectBrowserAction("create-component", "Create Component...", enabled),
            ProjectBrowserAction("create-pipeline", "Create Render Pipeline...", enabled),
            ProjectBrowserAction("create-prefab", "Create Prefab...", enabled),
        )

    def _execute_creation_action(self, action_id: str, directory: Path | None) -> bool:
        operations = self._operations
        if operations is None:
            return False
        callbacks = {
            "create-directory": operations.create_directory,
            "create-file": operations.create_file,
            "create-material": operations.create_material,
            "create-shader": operations.create_shader,
            "create-component": operations.create_component,
            "create-pipeline": operations.create_pipeline,
            "create-prefab": operations.create_prefab,
        }
        callback = callbacks.get(action_id)
        if callback is None:
            return False
        callback(directory, self._mutation_refresh)
        return True

    def snapshot(self) -> ProjectBrowserSnapshot:
        return ProjectBrowserSnapshot(
            root_path=self._root_path,
            selected_directory=self._selected_directory,
            entries=self._entries,
            breadcrumb=self._breadcrumb(),
            revision=self._revision,
        )

    def _entry(self, index: int) -> ProjectBrowserEntry | None:
        return self._entries[index] if 0 <= index < len(self._entries) else None

    def _scan_entries(self, directory: Path) -> tuple[ProjectBrowserEntry, ...]:
        try:
            paths = sorted(
                (path for path in directory.iterdir() if self._should_show(path)),
                key=lambda path: (not path.is_dir(), path.name.casefold()),
            )
        except OSError:
            _logger.exception("Failed to scan project directory: %s", directory)
            return ()
        entries = []
        for path in paths:
            is_directory = path.is_dir()
            if not is_directory and not path.is_file():
                continue
            entries.append(
                ProjectBrowserEntry(
                    stable_id=str(path.resolve(strict=False)),
                    path=path,
                    name=path.name,
                    subtitle="Folder" if is_directory else file_subtitle(path),
                    is_directory=is_directory,
                    icon_kind="folder" if is_directory else file_icon_kind(path),
                )
            )
        return tuple(entries)

    def _ignored_roots(self) -> tuple[Path, ...]:
        return project_ignored_roots(self._root_path) if self._root_path is not None else ()

    def _should_show(self, path: Path) -> bool:
        return not path.name.startswith(".") and not is_path_ignored(path, self._ignored_roots())

    def _is_visible_directory(self, path: Path) -> bool:
        if self._root_path is None:
            return False
        try:
            path.relative_to(self._root_path)
        except ValueError:
            return False
        return path == self._root_path or self._should_show(path)

    def _breadcrumb(self) -> tuple[tuple[str, Path], ...]:
        if self._root_path is None or self._selected_directory is None:
            return ()
        result = [(self._root_path.name or str(self._root_path), self._root_path)]
        relative = self._selected_directory.relative_to(self._root_path)
        for part in relative.parts:
            result.append((part, result[-1][1] / part))
        return tuple(result)


__all__ = [
    "ProjectBrowserAction",
    "ProjectBrowserController",
    "ProjectBrowserEntry",
    "ProjectBrowserSnapshot",
    "file_icon_kind",
    "file_subtitle",
]
