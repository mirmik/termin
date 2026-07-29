"""Toolkit-neutral editor settings snapshot and persistence controller."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from termin.editor_core.settings import EditorSettings
from termin.project_build import ToolchainContext


@dataclass(frozen=True)
class EditorSettingsSnapshot:
    text_editor: str
    slang_compiler: str
    build_sdk_root: str
    build_termin_root: str
    build_android_sdk_root: str
    build_shader_compiler: str
    build_fxc: str
    build_android_script: str
    build_quest_openxr_script: str
    build_gradle: str
    build_adb: str
    font_size: float
    font_size_small: float
    mcp_server_enabled: bool
    vsync_enabled: bool
    fps_limit: int
    render_only_active_display: bool


class EditorSettingsController:
    def __init__(self, settings: EditorSettings | None = None) -> None:
        self._settings = settings or EditorSettings.instance()

    def load(self) -> EditorSettingsSnapshot:
        return EditorSettingsSnapshot(
            text_editor=self._settings.get_text_editor() or "",
            slang_compiler=self._settings.get_slang_compiler() or "",
            build_sdk_root=self._settings.get_build_sdk_root() or "",
            build_termin_root=self._settings.get_build_termin_root() or "",
            build_android_sdk_root=self._settings.get_build_android_sdk_root() or "",
            build_shader_compiler=self._settings.get_build_shader_compiler() or "",
            build_fxc=self._settings.get_build_fxc() or "",
            build_android_script=self._settings.get_build_android_script() or "",
            build_quest_openxr_script=(self._settings.get_build_quest_openxr_script() or ""),
            build_gradle=self._settings.get_build_gradle() or "",
            build_adb=self._settings.get_build_adb() or "",
            font_size=float(self._settings.get_font_size()),
            font_size_small=float(self._settings.get_font_size_small()),
            mcp_server_enabled=self._settings.get_mcp_server_enabled(),
            vsync_enabled=self._settings.get_vsync_enabled(),
            fps_limit=self._settings.get_fps_limit(),
            render_only_active_display=self._settings.get_render_only_active_display(),
        )

    def save(self, snapshot: EditorSettingsSnapshot) -> EditorSettingsSnapshot:
        validated = self.validate(snapshot)
        self._settings.set_text_editor(validated.text_editor or None)
        self._settings.set_slang_compiler(validated.slang_compiler or None)
        self._settings.set_build_sdk_root(validated.build_sdk_root or None)
        self._settings.set_build_termin_root(validated.build_termin_root or None)
        self._settings.set_build_android_sdk_root(validated.build_android_sdk_root or None)
        self._settings.set_build_shader_compiler(validated.build_shader_compiler or None)
        self._settings.set_build_fxc(validated.build_fxc or None)
        self._settings.set_build_android_script(validated.build_android_script or None)
        self._settings.set_build_quest_openxr_script(validated.build_quest_openxr_script or None)
        self._settings.set_build_gradle(validated.build_gradle or None)
        self._settings.set_build_adb(validated.build_adb or None)
        self._settings.set_font_size(validated.font_size)
        self._settings.set_font_size_small(validated.font_size_small)
        self._settings.set_mcp_server_enabled(validated.mcp_server_enabled)
        self._settings.set_vsync_enabled(validated.vsync_enabled)
        self._settings.set_fps_limit(validated.fps_limit)
        self._settings.set_render_only_active_display(validated.render_only_active_display)
        self._settings.sync()
        return validated

    def toolchain_context(self) -> ToolchainContext:
        return self.toolchain_context_from_snapshot(self.load())

    @staticmethod
    def toolchain_context_from_snapshot(
        snapshot: EditorSettingsSnapshot,
    ) -> ToolchainContext:
        def path(value: str) -> Path | None:
            normalized = value.strip()
            return Path(normalized) if normalized else None

        return ToolchainContext(
            sdk_root=path(snapshot.build_sdk_root),
            termin_root=path(snapshot.build_termin_root),
            android_sdk_root=path(snapshot.build_android_sdk_root),
            shader_compiler=path(snapshot.build_shader_compiler),
            fxc=path(snapshot.build_fxc),
            android_build_script=path(snapshot.build_android_script),
            quest_openxr_build_script=path(snapshot.build_quest_openxr_script),
            gradle=path(snapshot.build_gradle),
            adb=path(snapshot.build_adb),
        )

    @staticmethod
    def validate(snapshot: EditorSettingsSnapshot) -> EditorSettingsSnapshot:
        font_size = float(snapshot.font_size)
        small = float(snapshot.font_size_small)
        if not 8.0 <= font_size <= 32.0:
            raise ValueError("font size must be in range 8..32")
        if not 8.0 <= small <= 24.0:
            raise ValueError("small font size must be in range 8..24")
        fps_limit_value = float(snapshot.fps_limit)
        if not fps_limit_value.is_integer() or not 0.0 <= fps_limit_value <= 1000.0:
            raise ValueError("FPS limit must be zero (Unlimited) or an integer in range 1..1000")
        fps_limit = int(fps_limit_value)
        return EditorSettingsSnapshot(
            text_editor=snapshot.text_editor.strip(),
            slang_compiler=snapshot.slang_compiler.strip(),
            build_sdk_root=snapshot.build_sdk_root.strip(),
            build_termin_root=snapshot.build_termin_root.strip(),
            build_android_sdk_root=snapshot.build_android_sdk_root.strip(),
            build_shader_compiler=snapshot.build_shader_compiler.strip(),
            build_fxc=snapshot.build_fxc.strip(),
            build_android_script=snapshot.build_android_script.strip(),
            build_quest_openxr_script=snapshot.build_quest_openxr_script.strip(),
            build_gradle=snapshot.build_gradle.strip(),
            build_adb=snapshot.build_adb.strip(),
            font_size=font_size,
            font_size_small=small,
            mcp_server_enabled=bool(snapshot.mcp_server_enabled),
            vsync_enabled=bool(snapshot.vsync_enabled),
            fps_limit=fps_limit,
            render_only_active_display=bool(snapshot.render_only_active_display),
        )


__all__ = ["EditorSettingsController", "EditorSettingsSnapshot"]
