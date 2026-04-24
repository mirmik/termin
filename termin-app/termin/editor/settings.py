"""
Настройки редактора.

Централизованное хранение и загрузка настроек между сессиями.
Использует tcbase.Settings (JSON) для кроссплатформенного хранения.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tcbase import Settings


class EditorSettings:
    """
    Менеджер настроек редактора.

    Singleton-класс для доступа к настройкам из любого места.
    Настройки хранятся в JSON-файле через tcbase.Settings.
    """

    _instance: "EditorSettings | None" = None

    # Ключи настроек
    KEY_LAST_PROJECT_PATH = "ProjectBrowser/lastProjectPath"
    KEY_LAST_SCENE_PATH = "Editor/lastScenePath"
    KEY_TEXT_EDITOR = "Editor/textEditor"

    def __init__(self):
        self._settings = Settings("TerminEditor")

    @classmethod
    def instance(cls) -> "EditorSettings":
        """Получить singleton экземпляр."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get(self, key: str, default: Any = None) -> Any:
        """Получить значение настройки."""
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Установить значение настройки."""
        self._settings.set(key, value)

    def sync(self) -> None:
        """Принудительно сохранить настройки на диск."""
        self._settings.save()

    # --- Удобные методы для частых настроек ---

    def get_last_project_file(self) -> Path | None:
        """Получить путь к файлу последнего открытого проекта (.terminproj)."""
        path_str = self.get(self.KEY_LAST_PROJECT_PATH)
        if path_str:
            path = Path(path_str)
            if path.exists() and path.is_file() and path.suffix == ".terminproj":
                return path
        return None

    def set_last_project_file(self, path: Path | str) -> None:
        """Сохранить путь к файлу проекта."""
        self.set(self.KEY_LAST_PROJECT_PATH, str(path))


    def get_last_scene_path(self) -> Path | None:
        """Получить путь последней открытой сцены."""
        path_str = self.get(self.KEY_LAST_SCENE_PATH)
        if path_str:
            path = Path(path_str)
            if path.exists():
                return path
        return None

    def set_last_scene_path(self, path: Path | str) -> None:
        """Сохранить путь сцены."""
        self.set(self.KEY_LAST_SCENE_PATH, str(path))

    def get_text_editor(self) -> str | None:
        """Получить путь к внешнему текстовому редактору."""
        return self.get(self.KEY_TEXT_EDITOR)

    def init_text_editor_if_empty(self) -> None:
        """
        Инициализирует настройку текстового редактора, если она не задана.

        Вызывается при старте редактора. Ищет VS Code в стандартных путях
        и сохраняет найденный путь в настройки.
        """
        editor = self.get(self.KEY_TEXT_EDITOR)
        if editor:
            return

        # Пытаемся найти VS Code по умолчанию
        detected = self._detect_vscode()
        if detected:
            self.set_text_editor(detected)
            self.sync()

    def _detect_vscode(self) -> str | None:
        """
        Ищет VS Code в стандартных путях установки.

        Returns:
            Путь к исполняемому файлу VS Code или None.
        """
        import platform
        import os

        system = platform.system()

        if system == "Windows":
            # Windows: проверяем стандартные пути установки VS Code
            candidates = [
                # User installation
                Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Microsoft VS Code" / "Code.exe",
                # System installation
                Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft VS Code" / "Code.exe",
                Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft VS Code" / "Code.exe",
            ]
        elif system == "Darwin":  # macOS
            candidates = [
                Path("/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"),
                Path.home() / "Applications" / "Visual Studio Code.app" / "Contents" / "Resources" / "app" / "bin" / "code",
            ]
        else:  # Linux
            candidates = [
                Path("/usr/bin/code"),
                Path("/usr/local/bin/code"),
                Path("/snap/bin/code"),
                Path.home() / ".local" / "bin" / "code",
            ]

        for path in candidates:
            if path.exists():
                return str(path)

        return None

    def set_text_editor(self, editor_path: str | None) -> None:
        """Сохранить путь к текстовому редактору."""
        self.set(self.KEY_TEXT_EDITOR, editor_path or "")
