"""Workstation-local Termin build settings shared by every frontend."""

from __future__ import annotations

from pathlib import Path

from termin.base import Settings

from termin.project_build.toolchains import ToolchainContext


TERMIN_USER_SETTINGS_APP_ID = "termin"

KEY_BUILD_SDK_ROOT = "Build/sdkRoot"
KEY_BUILD_TERMIN_ROOT = "Build/terminRoot"
KEY_BUILD_ANDROID_SDK_ROOT = "Build/androidSdkRoot"
KEY_BUILD_ANDROID_HOME = "Build/androidHome"
KEY_BUILD_ANDROID_NDK_ROOT = "Build/androidNdkRoot"
KEY_BUILD_JAVA_HOME = "Build/javaHome"
KEY_BUILD_SHADER_COMPILER = "Build/shaderCompiler"
KEY_BUILD_FXC = "Build/fxc"
KEY_BUILD_ANDROID_SCRIPT = "Build/androidScript"
KEY_BUILD_QUEST_OPENXR_SCRIPT = "Build/questOpenxrScript"
KEY_BUILD_GRADLE = "Build/gradle"
KEY_BUILD_ADB = "Build/adb"

TOOLCHAIN_SETTING_KEYS = (
    KEY_BUILD_SDK_ROOT,
    KEY_BUILD_TERMIN_ROOT,
    KEY_BUILD_ANDROID_SDK_ROOT,
    KEY_BUILD_ANDROID_HOME,
    KEY_BUILD_ANDROID_NDK_ROOT,
    KEY_BUILD_JAVA_HOME,
    KEY_BUILD_SHADER_COMPILER,
    KEY_BUILD_FXC,
    KEY_BUILD_ANDROID_SCRIPT,
    KEY_BUILD_QUEST_OPENXR_SCRIPT,
    KEY_BUILD_GRADLE,
    KEY_BUILD_ADB,
)


class UserToolchainSettings:
    """Read and write the shared ``Build/*`` section of Termin user settings."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings(TERMIN_USER_SETTINGS_APP_ID)

    @property
    def path(self) -> Path:
        return Path(self._settings.path)

    def load(self) -> ToolchainContext:
        return ToolchainContext(
            sdk_root=self._path(KEY_BUILD_SDK_ROOT),
            termin_root=self._path(KEY_BUILD_TERMIN_ROOT),
            android_sdk_root=self._path(KEY_BUILD_ANDROID_SDK_ROOT),
            android_home=self._path(KEY_BUILD_ANDROID_HOME),
            android_ndk_root=self._path(KEY_BUILD_ANDROID_NDK_ROOT),
            java_home=self._path(KEY_BUILD_JAVA_HOME),
            shader_compiler=self._path(KEY_BUILD_SHADER_COMPILER),
            fxc=self._path(KEY_BUILD_FXC),
            android_build_script=self._path(KEY_BUILD_ANDROID_SCRIPT),
            quest_openxr_build_script=self._path(KEY_BUILD_QUEST_OPENXR_SCRIPT),
            gradle=self._path(KEY_BUILD_GRADLE),
            adb=self._path(KEY_BUILD_ADB),
        )

    def save(self, context: ToolchainContext) -> ToolchainContext:
        self._set_path(KEY_BUILD_SDK_ROOT, context.sdk_root)
        self._set_path(KEY_BUILD_TERMIN_ROOT, context.termin_root)
        self._set_path(KEY_BUILD_ANDROID_SDK_ROOT, context.android_sdk_root)
        self._set_path(KEY_BUILD_ANDROID_HOME, context.android_home)
        self._set_path(KEY_BUILD_ANDROID_NDK_ROOT, context.android_ndk_root)
        self._set_path(KEY_BUILD_JAVA_HOME, context.java_home)
        self._set_path(KEY_BUILD_SHADER_COMPILER, context.shader_compiler)
        self._set_path(KEY_BUILD_FXC, context.fxc)
        self._set_path(KEY_BUILD_ANDROID_SCRIPT, context.android_build_script)
        self._set_path(
            KEY_BUILD_QUEST_OPENXR_SCRIPT,
            context.quest_openxr_build_script,
        )
        self._set_path(KEY_BUILD_GRADLE, context.gradle)
        self._set_path(KEY_BUILD_ADB, context.adb)
        return context

    def _path(self, key: str) -> Path | None:
        value = str(self._settings.get(key, "") or "").strip()
        return Path(value) if value else None

    def _set_path(self, key: str, value: Path | None) -> None:
        self._settings.set(key, str(value) if value is not None else "")


__all__ = [
    "KEY_BUILD_ADB",
    "KEY_BUILD_ANDROID_SCRIPT",
    "KEY_BUILD_ANDROID_HOME",
    "KEY_BUILD_ANDROID_NDK_ROOT",
    "KEY_BUILD_ANDROID_SDK_ROOT",
    "KEY_BUILD_FXC",
    "KEY_BUILD_GRADLE",
    "KEY_BUILD_JAVA_HOME",
    "KEY_BUILD_QUEST_OPENXR_SCRIPT",
    "KEY_BUILD_SDK_ROOT",
    "KEY_BUILD_SHADER_COMPILER",
    "KEY_BUILD_TERMIN_ROOT",
    "TERMIN_USER_SETTINGS_APP_ID",
    "TOOLCHAIN_SETTING_KEYS",
    "UserToolchainSettings",
]
