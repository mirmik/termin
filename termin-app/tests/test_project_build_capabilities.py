import json
from pathlib import Path

import pytest

from termin.project_build.capabilities import SDKCapabilityError, load_sdk_capabilities


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_executable(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(0o755)


def test_sdk_capabilities_read_manifest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("TERMIN_SDK", raising=False)
    monkeypatch.delenv("TERMIN_ANDROID_SDK_ROOT", raising=False)
    sdk_root = tmp_path / "sdk"
    _write_json(
        sdk_root / "termin-sdk-capabilities.json",
        {
            "version": 1,
            "sdk_version": "0.1.0",
            "platforms": {
                "desktop": {
                    "player": True,
                    "native_libraries": True,
                    "python_runtime": True,
                    "builtin_shaders": True,
                },
                "android": {
                    "abis": ["x86_64", "arm64-v8a"],
                    "vulkan": True,
                    "python_runtime": False,
                },
                "quest_openxr": {
                    "abis": ["arm64-v8a"],
                    "openxr_headers": True,
                    "openxr_loader": True,
                    "vulkan": True,
                },
            },
            "tools": {
                "termin_shaderc": "bin/termin_shaderc",
                "termin_player": "bin/termin_player",
            },
        },
    )

    capabilities = load_sdk_capabilities(sdk_root=sdk_root)

    assert capabilities.sdk_root == sdk_root.resolve()
    assert capabilities.manifest_path == sdk_root.resolve() / "termin-sdk-capabilities.json"
    assert capabilities.sdk_version == "0.1.0"
    assert capabilities.tools.termin_shaderc == sdk_root.resolve() / "bin" / "termin_shaderc"
    assert capabilities.tools.termin_player == sdk_root.resolve() / "bin" / "termin_player"
    assert capabilities.desktop.player is True
    assert capabilities.desktop.python_runtime is True
    assert capabilities.android.abis == ("arm64-v8a", "x86_64")
    assert capabilities.android.has_abi("arm64-v8a")
    assert capabilities.quest_openxr.supports_openxr("arm64-v8a")
    assert capabilities.quest_openxr.openxr_config_path("arm64-v8a") == (
        sdk_root.resolve()
        / "android"
        / "arm64-v8a"
        / "lib"
        / "cmake"
        / "termin_openxr"
        / "termin_openxrConfig.cmake"
    )


def test_sdk_capabilities_synthesize_from_current_layout(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("TERMIN_SDK", raising=False)
    monkeypatch.delenv("TERMIN_ANDROID_SDK_ROOT", raising=False)
    sdk_root = tmp_path / "sdk"
    _write_executable(sdk_root / "bin" / "termin_shaderc")
    _write_executable(sdk_root / "bin" / "termin_player")
    (sdk_root / "lib").mkdir(parents=True)
    (sdk_root / "lib" / "libtermin_base.so").write_bytes(b"termin")
    python_home = sdk_root / "lib" / "python3.10"
    python_home.mkdir()
    (python_home / "os.py").write_text("", encoding="utf-8")
    (sdk_root / "share" / "termin" / "builtin_shaders").mkdir(parents=True)
    openxr_config = (
        sdk_root
        / "android"
        / "arm64-v8a"
        / "lib"
        / "cmake"
        / "termin_openxr"
        / "termin_openxrConfig.cmake"
    )
    openxr_config.parent.mkdir(parents=True)
    openxr_config.write_text("# fake OpenXR package\n", encoding="utf-8")

    capabilities = load_sdk_capabilities(sdk_root=sdk_root)

    assert capabilities.manifest_path is None
    assert capabilities.tools.termin_shaderc == sdk_root.resolve() / "bin" / "termin_shaderc"
    assert capabilities.tools.termin_player == sdk_root.resolve() / "bin" / "termin_player"
    assert capabilities.desktop.player is True
    assert capabilities.desktop.native_libraries is True
    assert capabilities.desktop.python_runtime is True
    assert capabilities.desktop.builtin_shaders is True
    assert capabilities.android.sdk_root == sdk_root.resolve() / "android"
    assert capabilities.android.abis == ("arm64-v8a",)
    assert capabilities.android.vulkan is True
    assert capabilities.quest_openxr.abis == ("arm64-v8a",)
    assert capabilities.quest_openxr.supports_openxr("arm64-v8a")
    assert capabilities.quest_openxr.openxr_config_path("arm64-v8a") == openxr_config.resolve()


def test_sdk_capabilities_synthesize_from_windows_desktop_layout(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("TERMIN_SDK", raising=False)
    monkeypatch.delenv("TERMIN_ANDROID_SDK_ROOT", raising=False)
    sdk_root = tmp_path / "sdk"
    _write_executable(sdk_root / "bin" / "termin_shaderc.exe")
    _write_executable(sdk_root / "bin" / "termin_player.exe")
    (sdk_root / "bin" / "termin_base.dll").write_bytes(b"termin")
    python_lib = sdk_root / "python" / "Lib"
    python_lib.mkdir(parents=True)
    (python_lib / "os.py").write_text("", encoding="utf-8")
    (sdk_root / "share" / "termin" / "builtin_shaders").mkdir(parents=True)

    capabilities = load_sdk_capabilities(sdk_root=sdk_root)

    assert capabilities.tools.termin_shaderc == sdk_root.resolve() / "bin" / "termin_shaderc.exe"
    assert capabilities.tools.termin_player == sdk_root.resolve() / "bin" / "termin_player.exe"
    assert capabilities.desktop.player is True
    assert capabilities.desktop.native_libraries is True
    assert capabilities.desktop.python_runtime is True
    assert capabilities.desktop.builtin_shaders is True


def test_sdk_capabilities_prefer_explicit_termin_root_over_env_sdk(
    tmp_path: Path,
    monkeypatch,
) -> None:
    env_sdk_root = tmp_path / "env-sdk"
    env_sdk_root.mkdir()
    termin_root = tmp_path / "termin-root"
    target_sdk_root = termin_root / "sdk"
    target_android_sdk = target_sdk_root / "android" / "arm64-v8a" / "lib"
    target_android_sdk.mkdir(parents=True)
    monkeypatch.setenv("TERMIN_SDK", str(env_sdk_root))
    monkeypatch.delenv("TERMIN_ANDROID_SDK_ROOT", raising=False)

    capabilities = load_sdk_capabilities(termin_root=termin_root)

    assert capabilities.sdk_root == target_sdk_root.resolve()
    assert capabilities.android.sdk_root == (target_sdk_root / "android").resolve()
    assert capabilities.android.abis == ("arm64-v8a",)


def test_sdk_capabilities_reject_invalid_manifest_version(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("TERMIN_SDK", raising=False)
    sdk_root = tmp_path / "sdk"
    _write_json(
        sdk_root / "termin-sdk-capabilities.json",
        {
            "version": 2,
            "platforms": {},
        },
    )

    with pytest.raises(SDKCapabilityError, match="unsupported SDK capability version 2"):
        load_sdk_capabilities(sdk_root=sdk_root)
