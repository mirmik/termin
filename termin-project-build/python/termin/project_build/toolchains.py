"""Resolve workstation-local build tools without touching project profiles."""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Callable, Mapping, Protocol, Sequence


@dataclass(frozen=True)
class ToolchainContext:
    """Resolved local build tools; this type is never project-persisted."""

    sdk_root: Path | None = None
    termin_root: Path | None = None
    android_sdk_root: Path | None = None
    shader_compiler: Path | None = None
    fxc: Path | None = None
    android_build_script: Path | None = None
    quest_openxr_build_script: Path | None = None
    gradle: Path | None = None
    adb: Path | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            field.name: str(value) if (value := getattr(self, field.name)) is not None else None
            for field in fields(self)
        }


class ToolchainContextProvider(Protocol):
    """One precedence layer contributing explicitly configured local paths."""

    def provide(self) -> ToolchainContext: ...


@dataclass(frozen=True)
class StaticToolchainContextProvider:
    context: ToolchainContext

    def provide(self) -> ToolchainContext:
        return self.context


@dataclass(frozen=True)
class EnvironmentToolchainContextProvider:
    environ: Mapping[str, str]

    def provide(self) -> ToolchainContext:
        root = _environment_path(self.environ, "TERMIN_ROOT")
        return ToolchainContext(
            sdk_root=_environment_path(self.environ, "TERMIN_SDK"),
            termin_root=root,
            android_sdk_root=_first_environment_path(
                self.environ,
                ("TERMIN_ANDROID_SDK_ROOT", "ANDROID_SDK_ROOT", "ANDROID_HOME"),
            ),
            shader_compiler=_environment_path(self.environ, "TERMIN_SHADERC"),
            fxc=_environment_path(self.environ, "TERMIN_FXC"),
            android_build_script=_environment_path(
                self.environ, "TERMIN_ANDROID_BUILD_SCRIPT"
            ),
            quest_openxr_build_script=_environment_path(
                self.environ, "TERMIN_QUEST_OPENXR_BUILD_SCRIPT"
            ),
            gradle=_environment_path(self.environ, "GRADLE_BIN"),
            adb=_environment_path(self.environ, "ADB"),
        )


@dataclass(frozen=True)
class SDKInstallationToolchainContextProvider:
    """Lowest-precedence roots inferred from the running SDK/source installation."""

    sdk_root: Path | None = None
    termin_root: Path | None = None
    prefix: Path | None = None
    module_path: Path = Path(__file__)

    def provide(self) -> ToolchainContext:
        prefix = (self.prefix or Path(sys.prefix)).expanduser().resolve()
        termin_root = _normalize_path(self.termin_root)
        if termin_root is None:
            termin_root = _find_termin_root((self.module_path.resolve(), prefix))

        sdk_root = _normalize_path(self.sdk_root)
        if sdk_root is None:
            sdk_root = _find_sdk_root(prefix, termin_root)
        return ToolchainContext(sdk_root=sdk_root, termin_root=termin_root)


def resolve_toolchain_context(
    providers: Sequence[ToolchainContextProvider],
    *,
    path_search: Callable[[str], str | None] = shutil.which,
) -> ToolchainContext:
    """Merge low-to-high precedence providers, then derive unset tool paths."""

    values: dict[str, Path | None] = {field.name: None for field in fields(ToolchainContext)}
    for provider in providers:
        provided = provider.provide()
        for field in fields(ToolchainContext):
            value = getattr(provided, field.name)
            if value is not None:
                values[field.name] = _normalize_path(value)

    merged = ToolchainContext(**values)
    return _derive_tool_paths(merged, path_search=path_search)


def create_local_toolchain_context(
    *,
    editor_settings: ToolchainContext | None = None,
    invocation_overrides: ToolchainContext | None = None,
    installation_defaults: ToolchainContext | None = None,
    environ: Mapping[str, str] | None = None,
    path_search: Callable[[str], str | None] = shutil.which,
) -> ToolchainContext:
    """Build the canonical local context with documented provider precedence."""

    installation_provider: ToolchainContextProvider
    if installation_defaults is None:
        installation_provider = SDKInstallationToolchainContextProvider()
    else:
        installation_provider = StaticToolchainContextProvider(installation_defaults)

    providers: list[ToolchainContextProvider] = [
        installation_provider,
        EnvironmentToolchainContextProvider(os.environ if environ is None else environ),
    ]
    if editor_settings is not None:
        providers.append(StaticToolchainContextProvider(editor_settings))
    if invocation_overrides is not None:
        providers.append(StaticToolchainContextProvider(invocation_overrides))
    return resolve_toolchain_context(providers, path_search=path_search)


def _derive_tool_paths(
    context: ToolchainContext,
    *,
    path_search: Callable[[str], str | None],
) -> ToolchainContext:
    sdk_root = context.sdk_root
    if sdk_root is None and context.termin_root is not None:
        sdk_root = (context.termin_root / "sdk").resolve()

    android_sdk_root = context.android_sdk_root
    if android_sdk_root is None and sdk_root is not None:
        android_sdk_root = (sdk_root / "android").resolve()

    shader_compiler = context.shader_compiler or _first_existing(
        _sdk_tool_candidates(sdk_root, "termin_shaderc")
    )
    if shader_compiler is None:
        shader_compiler = _searched_path(path_search, "termin_shaderc")

    fxc = context.fxc or _first_existing(_sdk_tool_candidates(sdk_root, "fxc"))
    if fxc is None:
        fxc = _searched_path(path_search, "fxc")

    android_script = context.android_build_script
    quest_script = context.quest_openxr_build_script
    if context.termin_root is not None:
        android_script = android_script or (
            context.termin_root / _platform_script("build-android-apk")
        ).resolve()
        quest_script = quest_script or (
            context.termin_root / _platform_script("build-quest-openxr-apk")
        ).resolve()

    gradle = context.gradle or _searched_path(path_search, "gradle")
    if gradle is None:
        gradle = _first_existing(
            (
                Path.home() / "soft" / "gradle-8" / "bin" / _platform_executable("gradle"),
                Path.home()
                / "soft"
                / "gradle-8.10.2"
                / "bin"
                / _platform_executable("gradle"),
            )
        )
    adb = context.adb
    if adb is None and android_sdk_root is not None:
        adb = _first_existing(
            (
                android_sdk_root / "platform-tools" / "adb",
                android_sdk_root / "platform-tools" / "adb.exe",
            )
        )
    if adb is None:
        adb = _searched_path(path_search, "adb")

    return ToolchainContext(
        sdk_root=sdk_root,
        termin_root=context.termin_root,
        android_sdk_root=android_sdk_root,
        shader_compiler=shader_compiler,
        fxc=fxc,
        android_build_script=android_script,
        quest_openxr_build_script=quest_script,
        gradle=gradle,
        adb=adb,
    )


def _find_termin_root(search_roots: Sequence[Path]) -> Path | None:
    for start in search_roots:
        for candidate in (start, *start.parents):
            if (candidate / "build-android-apk.sh").is_file() or (
                candidate / "build-android-apk.ps1"
            ).is_file():
                return candidate.resolve()
    return None


def _find_sdk_root(prefix: Path, termin_root: Path | None) -> Path | None:
    candidates = [prefix]
    if termin_root is not None:
        candidates.append(termin_root / "sdk")
    for candidate in candidates:
        if (candidate / "termin-sdk-capabilities.json").is_file() or (
            candidate / "bin" / _platform_executable("termin_shaderc")
        ).is_file():
            return candidate.resolve()
    return None


def _sdk_tool_candidates(sdk_root: Path | None, name: str) -> tuple[Path, ...]:
    if sdk_root is None:
        return ()
    return (
        sdk_root / "bin" / name,
        sdk_root / "bin" / f"{name}.exe",
    )


def _platform_executable(name: str) -> str:
    return f"{name}.exe" if os.name == "nt" else name


def _platform_script(stem: str) -> str:
    return f"{stem}.ps1" if os.name == "nt" else f"{stem}.sh"


def _environment_path(environ: Mapping[str, str], name: str) -> Path | None:
    value = environ.get(name)
    return Path(value) if value else None


def _first_environment_path(
    environ: Mapping[str, str], names: Sequence[str]
) -> Path | None:
    for name in names:
        value = _environment_path(environ, name)
        if value is not None:
            return value
    return None


def _normalize_path(path: Path | None) -> Path | None:
    return path.expanduser().resolve() if path is not None else None


def _first_existing(candidates: Sequence[Path]) -> Path | None:
    return next((candidate.resolve() for candidate in candidates if candidate.is_file()), None)


def _searched_path(
    path_search: Callable[[str], str | None], name: str
) -> Path | None:
    found = path_search(name)
    return Path(found).expanduser().resolve() if found else None


__all__ = [
    "EnvironmentToolchainContextProvider",
    "SDKInstallationToolchainContextProvider",
    "StaticToolchainContextProvider",
    "ToolchainContext",
    "ToolchainContextProvider",
    "create_local_toolchain_context",
    "resolve_toolchain_context",
]
