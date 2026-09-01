"""
Настройки редактора.

Централизованное хранение и загрузка настроек между сессиями.
Использует termin.base.Settings (JSON) для кроссплатформенного хранения.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from termin.base import Settings
from termin.project_build.user_settings import (
    KEY_BUILD_ADB as USER_KEY_BUILD_ADB,
    KEY_BUILD_ANDROID_HOME as USER_KEY_BUILD_ANDROID_HOME,
    KEY_BUILD_ANDROID_SCRIPT as USER_KEY_BUILD_ANDROID_SCRIPT,
    KEY_BUILD_ANDROID_NDK_ROOT as USER_KEY_BUILD_ANDROID_NDK_ROOT,
    KEY_BUILD_ANDROID_SDK_ROOT as USER_KEY_BUILD_ANDROID_SDK_ROOT,
    KEY_BUILD_FXC as USER_KEY_BUILD_FXC,
    KEY_BUILD_GRADLE as USER_KEY_BUILD_GRADLE,
    KEY_BUILD_JAVA_HOME as USER_KEY_BUILD_JAVA_HOME,
    KEY_BUILD_QUEST_OPENXR_SCRIPT as USER_KEY_BUILD_QUEST_OPENXR_SCRIPT,
    KEY_BUILD_SDK_ROOT as USER_KEY_BUILD_SDK_ROOT,
    KEY_BUILD_SHADER_COMPILER as USER_KEY_BUILD_SHADER_COMPILER,
    KEY_BUILD_TERMIN_ROOT as USER_KEY_BUILD_TERMIN_ROOT,
    TERMIN_USER_SETTINGS_APP_ID,
    TOOLCHAIN_SETTING_KEYS,
)


class EditorSettings:
    """
    Менеджер настроек редактора.

    Singleton-класс для доступа к настройкам из любого места.
    Настройки хранятся в JSON-файле через termin.base.Settings.
    """

    _instance: "EditorSettings | None" = None
    LEGACY_APP_ID = "TerminEditor"
    KEY_LEGACY_MIGRATION = "Migration/terminEditorSettingsV1"

    # Ключи настроек
    KEY_LAST_PROJECT_PATH = "ProjectBrowser/lastProjectPath"
    KEY_TEXT_EDITOR = "Editor/textEditor"
    KEY_FONT_SIZE = "Editor/fontSize"
    KEY_FONT_SIZE_SMALL = "Editor/fontSizeSmall"
    KEY_SLANG_COMPILER = "Shader/slangCompiler"
    KEY_BUILD_SDK_ROOT = USER_KEY_BUILD_SDK_ROOT
    KEY_BUILD_TERMIN_ROOT = USER_KEY_BUILD_TERMIN_ROOT
    KEY_BUILD_ANDROID_SDK_ROOT = USER_KEY_BUILD_ANDROID_SDK_ROOT
    KEY_BUILD_ANDROID_HOME = USER_KEY_BUILD_ANDROID_HOME
    KEY_BUILD_ANDROID_NDK_ROOT = USER_KEY_BUILD_ANDROID_NDK_ROOT
    KEY_BUILD_JAVA_HOME = USER_KEY_BUILD_JAVA_HOME
    KEY_BUILD_SHADER_COMPILER = USER_KEY_BUILD_SHADER_COMPILER
    KEY_BUILD_FXC = USER_KEY_BUILD_FXC
    KEY_BUILD_ANDROID_SCRIPT = USER_KEY_BUILD_ANDROID_SCRIPT
    KEY_BUILD_QUEST_OPENXR_SCRIPT = USER_KEY_BUILD_QUEST_OPENXR_SCRIPT
    KEY_BUILD_GRADLE = USER_KEY_BUILD_GRADLE
    KEY_BUILD_ADB = USER_KEY_BUILD_ADB
    KEY_MCP_SERVER_ENABLED = "Editor/mcpServerEnabled"
    KEY_VSYNC_ENABLED = "Editor/vsyncEnabled"
    KEY_FPS_LIMIT = "Editor/fpsLimit"
    KEY_RENDER_ONLY_ACTIVE_DISPLAY = "Editor/renderOnlyActiveDisplay"

    # Значения по умолчанию
    DEFAULT_FONT_SIZE: float = 14.0
    DEFAULT_FONT_SIZE_SMALL: float = 11.0
    DEFAULT_VSYNC_ENABLED: bool = True
    DEFAULT_FPS_LIMIT: int = 60
    DEFAULT_RENDER_ONLY_ACTIVE_DISPLAY: bool = True

    def __init__(
        self,
        settings: Settings | None = None,
        legacy_settings: Settings | None = None,
        *,
        migrate_legacy: bool = True,
    ):
        self._settings = settings or Settings(TERMIN_USER_SETTINGS_APP_ID)
        if migrate_legacy:
            self._migrate_legacy_settings(legacy_settings or Settings(self.LEGACY_APP_ID))

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

    @property
    def path(self) -> Path:
        return Path(self._settings.path)

    def _migrate_legacy_settings(self, legacy: Settings) -> None:
        if bool(self.get(self.KEY_LEGACY_MIGRATION, False)):
            return
        keys = (
            self.KEY_LAST_PROJECT_PATH,
            self.KEY_TEXT_EDITOR,
            self.KEY_FONT_SIZE,
            self.KEY_FONT_SIZE_SMALL,
            self.KEY_SLANG_COMPILER,
            self.KEY_MCP_SERVER_ENABLED,
            self.KEY_VSYNC_ENABLED,
            self.KEY_FPS_LIMIT,
            self.KEY_RENDER_ONLY_ACTIVE_DISPLAY,
            *TOOLCHAIN_SETTING_KEYS,
        )
        for key in keys:
            if not self._settings.contains(key) and legacy.contains(key):
                self.set(key, legacy.get(key))
        self.set(self.KEY_LEGACY_MIGRATION, True)

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
                Path.home()
                / "Applications"
                / "Visual Studio Code.app"
                / "Contents"
                / "Resources"
                / "app"
                / "bin"
                / "code",
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

    def get_slang_compiler(self) -> str | None:
        """Получить путь к компилятору Slang."""
        return self.get(self.KEY_SLANG_COMPILER) or None

    def set_slang_compiler(self, compiler_path: str | None) -> None:
        """Сохранить путь к компилятору Slang."""
        self.set(self.KEY_SLANG_COMPILER, compiler_path or "")

    def get_build_sdk_root(self) -> str | None:
        return self.get(self.KEY_BUILD_SDK_ROOT) or None

    def set_build_sdk_root(self, path: str | None) -> None:
        self.set(self.KEY_BUILD_SDK_ROOT, path or "")

    def get_build_termin_root(self) -> str | None:
        return self.get(self.KEY_BUILD_TERMIN_ROOT) or None

    def set_build_termin_root(self, path: str | None) -> None:
        self.set(self.KEY_BUILD_TERMIN_ROOT, path or "")

    def get_build_android_sdk_root(self) -> str | None:
        return self.get(self.KEY_BUILD_ANDROID_SDK_ROOT) or None

    def set_build_android_sdk_root(self, path: str | None) -> None:
        self.set(self.KEY_BUILD_ANDROID_SDK_ROOT, path or "")

    def get_build_android_home(self) -> str | None:
        return self.get(self.KEY_BUILD_ANDROID_HOME) or None

    def set_build_android_home(self, path: str | None) -> None:
        self.set(self.KEY_BUILD_ANDROID_HOME, path or "")

    def get_build_android_ndk_root(self) -> str | None:
        return self.get(self.KEY_BUILD_ANDROID_NDK_ROOT) or None

    def set_build_android_ndk_root(self, path: str | None) -> None:
        self.set(self.KEY_BUILD_ANDROID_NDK_ROOT, path or "")

    def get_build_java_home(self) -> str | None:
        return self.get(self.KEY_BUILD_JAVA_HOME) or None

    def set_build_java_home(self, path: str | None) -> None:
        self.set(self.KEY_BUILD_JAVA_HOME, path or "")

    def get_build_shader_compiler(self) -> str | None:
        return self.get(self.KEY_BUILD_SHADER_COMPILER) or None

    def set_build_shader_compiler(self, path: str | None) -> None:
        self.set(self.KEY_BUILD_SHADER_COMPILER, path or "")

    def get_build_fxc(self) -> str | None:
        return self.get(self.KEY_BUILD_FXC) or None

    def set_build_fxc(self, path: str | None) -> None:
        self.set(self.KEY_BUILD_FXC, path or "")

    def get_build_android_script(self) -> str | None:
        return self.get(self.KEY_BUILD_ANDROID_SCRIPT) or None

    def set_build_android_script(self, path: str | None) -> None:
        self.set(self.KEY_BUILD_ANDROID_SCRIPT, path or "")

    def get_build_quest_openxr_script(self) -> str | None:
        return self.get(self.KEY_BUILD_QUEST_OPENXR_SCRIPT) or None

    def set_build_quest_openxr_script(self, path: str | None) -> None:
        self.set(self.KEY_BUILD_QUEST_OPENXR_SCRIPT, path or "")

    def get_build_gradle(self) -> str | None:
        return self.get(self.KEY_BUILD_GRADLE) or None

    def set_build_gradle(self, path: str | None) -> None:
        self.set(self.KEY_BUILD_GRADLE, path or "")

    def get_build_adb(self) -> str | None:
        return self.get(self.KEY_BUILD_ADB) or None

    def set_build_adb(self, path: str | None) -> None:
        self.set(self.KEY_BUILD_ADB, path or "")

    def get_mcp_server_enabled(self) -> bool:
        """Whether to start the editor MCP server when env override is absent."""
        return bool(self.get(self.KEY_MCP_SERVER_ENABLED, False))

    def set_mcp_server_enabled(self, enabled: bool) -> None:
        """Persist editor MCP server startup preference."""
        self.set(self.KEY_MCP_SERVER_ENABLED, bool(enabled))

    def get_vsync_enabled(self) -> bool:
        """Whether editor windows should use synchronized presentation."""
        return bool(self.get(self.KEY_VSYNC_ENABLED, self.DEFAULT_VSYNC_ENABLED))

    def set_vsync_enabled(self, enabled: bool) -> None:
        """Persist the presentation preference applied on editor startup."""
        self.set(self.KEY_VSYNC_ENABLED, bool(enabled))

    def get_fps_limit(self) -> int:
        """Return the editor software FPS limit; zero means unlimited."""
        return int(self.get(self.KEY_FPS_LIMIT, self.DEFAULT_FPS_LIMIT))

    def set_fps_limit(self, fps_limit: int) -> None:
        """Persist the editor software FPS limit; zero means unlimited."""
        self.set(self.KEY_FPS_LIMIT, int(fps_limit))

    def get_render_only_active_display(self) -> bool:
        """Whether inactive display tabs should be excluded from rendering."""
        return bool(
            self.get(
                self.KEY_RENDER_ONLY_ACTIVE_DISPLAY,
                self.DEFAULT_RENDER_ONLY_ACTIVE_DISPLAY,
            )
        )

    def set_render_only_active_display(self, enabled: bool) -> None:
        """Persist the editor display-tab rendering policy."""
        self.set(self.KEY_RENDER_ONLY_ACTIVE_DISPLAY, bool(enabled))

    def get_font_size(self) -> float:
        """Получить базовый размер шрифта."""
        return self.get(self.KEY_FONT_SIZE, self.DEFAULT_FONT_SIZE)

    def set_font_size(self, size: float) -> None:
        """Сохранить базовый размер шрифта."""
        self.set(self.KEY_FONT_SIZE, size)

    def get_font_size_small(self) -> float:
        """Получить малый размер шрифта."""
        return self.get(self.KEY_FONT_SIZE_SMALL, self.DEFAULT_FONT_SIZE_SMALL)

    def set_font_size_small(self, size: float) -> None:
        """Сохранить малый размер шрифта."""
        self.set(self.KEY_FONT_SIZE_SMALL, size)
