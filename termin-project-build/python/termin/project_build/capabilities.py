"""Termin SDK capability model and discovery."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


SDK_CAPABILITIES_FILENAME = "termin-sdk-capabilities.json"


class SDKCapabilityError(RuntimeError):
    pass


@dataclass(frozen=True)
class SDKToolCapabilities:
    termin_shaderc: Path | None = None
    termin_player: Path | None = None


@dataclass(frozen=True)
class DesktopSDKCapabilities:
    player: bool = False
    native_libraries: bool = False
    python_runtime: bool = False
    builtin_shaders: bool = False


@dataclass(frozen=True)
class AndroidSDKCapabilities:
    sdk_root: Path
    abis: tuple[str, ...] = ()
    vulkan: bool = False
    python_runtime: bool = False

    def has_abi(self, abi: str) -> bool:
        return abi in self.abis

    def abi_prefix(self, abi: str) -> Path:
        return self.sdk_root / abi

    def abi_lib_dir(self, abi: str) -> Path:
        return self.abi_prefix(abi) / "lib"


@dataclass(frozen=True)
class QuestOpenXRSDKCapabilities:
    android_sdk_root: Path
    abis: tuple[str, ...] = ()
    openxr_headers: bool = False
    openxr_loader: bool = False
    vulkan: bool = False
    openxr_config_paths: dict[str, Path] = field(default_factory=dict)

    def has_abi(self, abi: str) -> bool:
        return abi in self.abis

    def supports_openxr(self, abi: str) -> bool:
        return (
            self.has_abi(abi)
            and self.openxr_headers
            and self.openxr_loader
            and self.vulkan
        )

    def openxr_config_path(self, abi: str) -> Path:
        configured_path = self.openxr_config_paths.get(abi)
        if configured_path is not None:
            return configured_path
        return (
            self.android_sdk_root
            / abi
            / "lib"
            / "cmake"
            / "termin_openxr"
            / "termin_openxrConfig.cmake"
        )


@dataclass(frozen=True)
class SDKCapabilities:
    sdk_root: Path | None
    manifest_path: Path | None
    version: int
    sdk_version: str
    tools: SDKToolCapabilities
    desktop: DesktopSDKCapabilities
    android: AndroidSDKCapabilities
    quest_openxr: QuestOpenXRSDKCapabilities


def load_sdk_capabilities(
    sdk_root: str | Path | None = None,
    termin_root: str | Path | None = None,
    android_sdk_root: str | Path | None = None,
) -> SDKCapabilities:
    resolved_sdk_root = _resolve_sdk_root(sdk_root, termin_root)
    resolved_android_sdk_root = _resolve_android_sdk_root(
        android_sdk_root=android_sdk_root,
        sdk_root=resolved_sdk_root,
        termin_root=termin_root,
    )

    manifest_path = (
        resolved_sdk_root / SDK_CAPABILITIES_FILENAME
        if resolved_sdk_root is not None
        else None
    )
    if manifest_path is not None and manifest_path.is_file():
        return _load_manifest_capabilities(
            manifest_path=manifest_path,
            sdk_root=resolved_sdk_root,
            android_sdk_root=resolved_android_sdk_root,
        )

    return _synthesize_capabilities(
        sdk_root=resolved_sdk_root,
        android_sdk_root=resolved_android_sdk_root,
    )


def _resolve_sdk_root(
    sdk_root: str | Path | None,
    termin_root: str | Path | None,
) -> Path | None:
    if sdk_root is not None:
        return Path(sdk_root).expanduser().resolve()

    if termin_root is not None:
        return (Path(termin_root).expanduser().resolve() / "sdk").resolve()

    env_sdk = os.environ.get("TERMIN_SDK")
    if env_sdk:
        return Path(env_sdk).expanduser().resolve()

    candidates: list[Path] = []
    cwd = Path.cwd().resolve()
    candidates.append(cwd / "sdk")
    for parent in cwd.parents:
        candidates.append(parent / "sdk")

    package_path = Path(__file__).resolve()
    for parent in package_path.parents:
        candidates.append(parent / "sdk")

    for candidate in _unique_paths(candidates):
        resolved = candidate.resolve()
        if resolved.exists() and resolved.is_dir():
            return resolved
    return None


def _resolve_android_sdk_root(
    android_sdk_root: str | Path | None,
    sdk_root: Path | None,
    termin_root: str | Path | None,
) -> Path:
    if android_sdk_root is not None:
        return Path(android_sdk_root).expanduser().resolve()

    env_android_sdk = os.environ.get("TERMIN_ANDROID_SDK_ROOT")
    if env_android_sdk:
        return Path(env_android_sdk).expanduser().resolve()

    if sdk_root is not None:
        return (sdk_root / "android").resolve()

    if termin_root is not None:
        return (Path(termin_root).expanduser().resolve() / "sdk" / "android").resolve()

    return (Path.cwd().resolve() / "sdk" / "android").resolve()


def _load_manifest_capabilities(
    manifest_path: Path,
    sdk_root: Path,
    android_sdk_root: Path,
) -> SDKCapabilities:
    data = _read_manifest(manifest_path)
    version_value = data.get("version")
    if not isinstance(version_value, int):
        raise SDKCapabilityError(f"{manifest_path} field 'version' must be an integer")
    if version_value != 1:
        raise SDKCapabilityError(
            f"{manifest_path} has unsupported SDK capability version {version_value}; "
            "supported version is 1"
        )

    platforms = _mapping_field(data, "platforms", manifest_path)
    desktop_data = _optional_mapping(platforms, "desktop")
    android_data = _optional_mapping(platforms, "android")
    quest_data = _optional_mapping(platforms, "quest_openxr")
    tools_data = _optional_mapping(data, "tools")

    android_abis = _string_tuple(android_data.get("abis"))
    quest_abis = _string_tuple(quest_data.get("abis"))
    openxr_config_paths = {
        abi: _default_openxr_config_path(android_sdk_root, abi)
        for abi in quest_abis
    }

    return SDKCapabilities(
        sdk_root=sdk_root,
        manifest_path=manifest_path,
        version=version_value,
        sdk_version=_string_field(data, "sdk_version", ""),
        tools=SDKToolCapabilities(
            termin_shaderc=_relative_tool_path(sdk_root, tools_data.get("termin_shaderc")),
            termin_player=_relative_tool_path(sdk_root, tools_data.get("termin_player")),
        ),
        desktop=DesktopSDKCapabilities(
            player=_bool_field(desktop_data, "player", tools_data.get("termin_player") is not None),
            native_libraries=_bool_field(desktop_data, "native_libraries", False),
            python_runtime=_bool_field(desktop_data, "python_runtime", False),
            builtin_shaders=_bool_field(desktop_data, "builtin_shaders", False),
        ),
        android=AndroidSDKCapabilities(
            sdk_root=android_sdk_root,
            abis=android_abis,
            vulkan=_bool_field(android_data, "vulkan", False),
            python_runtime=_bool_field(android_data, "python_runtime", False),
        ),
        quest_openxr=QuestOpenXRSDKCapabilities(
            android_sdk_root=android_sdk_root,
            abis=quest_abis,
            openxr_headers=_bool_field(quest_data, "openxr_headers", False),
            openxr_loader=_bool_field(quest_data, "openxr_loader", False),
            vulkan=_bool_field(quest_data, "vulkan", False),
            openxr_config_paths=openxr_config_paths,
        ),
    )


def _synthesize_capabilities(
    sdk_root: Path | None,
    android_sdk_root: Path,
) -> SDKCapabilities:
    tools = SDKToolCapabilities(
        termin_shaderc=_tool_path(sdk_root, "termin_shaderc"),
        termin_player=_tool_path(sdk_root, "termin_player"),
    )
    android_abis = _discover_android_abis(android_sdk_root)
    openxr_config_paths = {
        abi: _default_openxr_config_path(android_sdk_root, abi)
        for abi in android_abis
        if _default_openxr_config_path(android_sdk_root, abi).is_file()
    }
    quest_abis = tuple(sorted(openxr_config_paths))

    return SDKCapabilities(
        sdk_root=sdk_root,
        manifest_path=None,
        version=1,
        sdk_version="",
        tools=tools,
        desktop=DesktopSDKCapabilities(
            player=tools.termin_player is not None and tools.termin_player.is_file(),
            native_libraries=_has_native_libraries(sdk_root),
            python_runtime=_has_python_runtime(sdk_root),
            builtin_shaders=_has_builtin_shaders(sdk_root),
        ),
        android=AndroidSDKCapabilities(
            sdk_root=android_sdk_root,
            abis=android_abis,
            vulkan=bool(android_abis),
            python_runtime=False,
        ),
        quest_openxr=QuestOpenXRSDKCapabilities(
            android_sdk_root=android_sdk_root,
            abis=quest_abis,
            openxr_headers=bool(quest_abis),
            openxr_loader=bool(quest_abis),
            vulkan=bool(quest_abis),
            openxr_config_paths=openxr_config_paths,
        ),
    )


def _read_manifest(path: Path) -> Mapping[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except OSError as exc:
        raise SDKCapabilityError(f"failed to read SDK capability manifest {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SDKCapabilityError(f"failed to parse SDK capability manifest {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SDKCapabilityError(f"SDK capability manifest must be a JSON object: {path}")
    return data


def _mapping_field(data: Mapping[str, Any], key: str, path: Path) -> Mapping[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise SDKCapabilityError(f"{path} must contain object field '{key}'")
    return value


def _optional_mapping(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = data.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SDKCapabilityError(f"SDK capability field '{key}' must be an object")
    return value


def _string_field(data: Mapping[str, Any], key: str, default: str) -> str:
    value = data.get(key)
    if value is None:
        return default
    if not isinstance(value, str):
        raise SDKCapabilityError(f"SDK capability field '{key}' must be a string")
    return value


def _bool_field(data: Mapping[str, Any], key: str, default: bool) -> bool:
    value = data.get(key)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise SDKCapabilityError(f"SDK capability field '{key}' must be a boolean")
    return value


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise SDKCapabilityError("SDK capability ABI lists must be arrays")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or item == "":
            raise SDKCapabilityError("SDK capability ABI entries must be non-empty strings")
        result.append(item)
    return tuple(sorted(result))


def _relative_tool_path(sdk_root: Path, value: Any) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, str) or value == "":
        raise SDKCapabilityError("SDK capability tool paths must be non-empty strings")
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    return (sdk_root / path).resolve()


def _tool_path(sdk_root: Path | None, name: str) -> Path | None:
    if sdk_root is None:
        return None
    names = [f"{name}.exe", name] if os.name == "nt" else [name, f"{name}.exe"]
    for candidate_name in names:
        candidate = sdk_root / "bin" / candidate_name
        if candidate.is_file():
            return candidate.resolve()
    return None


def _discover_android_abis(android_sdk_root: Path) -> tuple[str, ...]:
    if not android_sdk_root.exists() or not android_sdk_root.is_dir():
        return ()
    abis = [
        child.name
        for child in android_sdk_root.iterdir()
        if child.is_dir()
    ]
    return tuple(sorted(abis))


def _default_openxr_config_path(android_sdk_root: Path, abi: str) -> Path:
    return (
        android_sdk_root
        / abi
        / "lib"
        / "cmake"
        / "termin_openxr"
        / "termin_openxrConfig.cmake"
    )


def _has_native_libraries(sdk_root: Path | None) -> bool:
    if sdk_root is None:
        return False
    candidates = (
        (sdk_root / "lib", ("*.so", "*.so.*", "*.dylib", "*.dll")),
        (sdk_root / "bin", ("*.dll",)),
    )
    for directory, patterns in candidates:
        if not directory.is_dir():
            continue
        for pattern in patterns:
            for path in directory.glob(pattern):
                if path.is_file():
                    return True
    return False


def _has_posix_python_runtime(sdk_root: Path) -> bool:
    lib_dir = sdk_root / "lib"
    if not lib_dir.is_dir():
        return False
    for path in lib_dir.iterdir():
        if path.is_dir() and path.name.startswith("python3.") and (path / "os.py").is_file():
            return True
    return False


def _has_windows_python_runtime(sdk_root: Path) -> bool:
    return (sdk_root / "python" / "Lib" / "os.py").is_file()


def _has_python_runtime(sdk_root: Path | None) -> bool:
    if sdk_root is None:
        return False
    return _has_posix_python_runtime(sdk_root) or _has_windows_python_runtime(sdk_root)


def _has_builtin_shaders(sdk_root: Path | None) -> bool:
    if sdk_root is None:
        return False
    return (sdk_root / "share" / "termin" / "builtin_shaders").is_dir()


def _unique_paths(paths: list[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.expanduser().resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        result.append(resolved)
    return result
