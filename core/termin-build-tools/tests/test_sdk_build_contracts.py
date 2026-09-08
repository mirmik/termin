import json
import re
from pathlib import Path

import pytest

from termin_build import (
    artifact_manifest,
    sdk,
    sdk_product_inputs,
    sdk_wheel_pipeline,
)
from termin_build.application_payload import load_application_payloads
from termin_build.package_manifest import load_manifest
from termin_build.sdk_profiles import load_sdk_profiles


REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def _repository_profiles_for_mechanism_tests(monkeypatch):
    """Use the real repository recipe when a synthetic repo omits product policy."""
    real_loader = load_sdk_profiles
    real_packages = load_manifest
    real_payloads = load_application_payloads

    def load_profiles(repo_root: Path):
        manifest = repo_root / "build-system" / "sdk-profiles.json"
        return real_loader(repo_root if manifest.is_file() else REPO_ROOT)

    monkeypatch.setattr(sdk, "load_sdk_profiles", load_profiles)
    monkeypatch.setattr(sdk_product_inputs, "load_sdk_profiles", load_profiles)
    monkeypatch.setattr(
        sdk_product_inputs,
        "load_manifest",
        lambda repo_root: real_packages(
            repo_root if (repo_root / "build-system" / "packages.json").is_file() else REPO_ROOT
        ),
    )
    monkeypatch.setattr(
        sdk_product_inputs,
        "load_application_payloads",
        lambda repo_root: real_payloads(
            repo_root if (repo_root / "build-system" / "application-python-payloads.json").is_file() else REPO_ROOT
        ),
    )
    monkeypatch.setattr(
        sdk,
        "prepare_slang_toolchain",
        lambda repo_root, _python: repo_root / "build" / "toolchains" / "slangc",
    )


def test_sdk_build_propagates_one_absolute_python_to_child_stages(
    tmp_path,
    monkeypatch,
):
    interpreter = tmp_path / "python"
    interpreter.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        sdk,
        "prepare_pinned_python_build_environment",
        lambda _root: interpreter,
    )
    captured = []

    def run(command, *, cwd, env=None):
        captured.append((command, cwd, env))
        return 1

    monkeypatch.setattr(sdk, "_run", run)

    result = sdk.run_sdk_build(
        repo_root=tmp_path,
        build_type="Release",
        stage_args=[],
        build_csharp=False,
        dry_run=False,
    )

    assert result == 1
    assert len(captured) == 1
    child_env = captured[0][2]
    assert child_env["PYTHON_BIN"] == str(interpreter)
    assert child_env["PYTHON_EXECUTABLE"] == str(interpreter)
    assert child_env["TERMIN_SLANGC"] == str(tmp_path / "build" / "toolchains" / "slangc")


def test_core_sdk_build_uses_isolated_prefix_and_build_directory(
    tmp_path,
    monkeypatch,
):
    interpreter = tmp_path / "python"
    interpreter.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        sdk,
        "prepare_pinned_python_build_environment",
        lambda _root: interpreter,
    )
    captured = []

    def run(command, *, cwd, env=None):
        captured.append((command, cwd, env))
        return 1

    monkeypatch.setattr(sdk, "_run", run)

    result = sdk.run_sdk_build(
        repo_root=tmp_path,
        build_type="Release",
        stage_args=[],
        build_csharp=True,
        dry_run=False,
        profile_name="core",
    )

    assert result == 1
    command, _, child_env = captured[0]
    assert "--profile=core" in command
    assert child_env["SDK_PREFIX"] == str(tmp_path / "sdk-core")
    assert child_env["BUILD_DIR"] == str(tmp_path / "build" / "Release-core")


def test_windows_dry_run_uses_powershell_stages_and_windows_python_layout(
    tmp_path,
    monkeypatch,
    capsys,
):
    repo_root = tmp_path / "termin"
    repo_root.mkdir()
    sdk_prefix = repo_root / "sdk"

    monkeypatch.setattr(sdk.sys, "platform", "win32")
    monkeypatch.setenv("SDK_PREFIX", str(sdk_prefix))
    monkeypatch.setattr(
        sdk.shutil,
        "which",
        lambda name: "C:/Program Files/PowerShell/7/pwsh.exe" if name == "pwsh" else None,
    )

    result = sdk.run_sdk_build(
        repo_root=repo_root,
        build_type="Release",
        stage_args=["--no-parallel"],
        build_csharp=True,
        dry_run=True,
    )

    output = capsys.readouterr().out
    assert result == 0
    assert "pwsh.exe -ExecutionPolicy Bypass -File" in output
    normalized = output.replace("\\", "/")
    assert "scripts/build/bindings.ps1 --profile=full --no-parallel" in normalized
    assert "scripts/build/csharp.ps1 --profile=full --no-parallel" in normalized
    assert "sdk/python/Lib/site-packages" in output.replace("\\", "/")


def test_linux_sdk_build_skips_csharp_unless_requested(tmp_path, monkeypatch, capsys):
    interpreter = tmp_path / "python"
    interpreter.write_text("", encoding="utf-8")
    monkeypatch.setattr(sdk, "_is_windows", lambda: False)
    monkeypatch.setattr(sdk, "_python_executable", lambda: str(interpreter))
    monkeypatch.setattr(
        sdk,
        "prepare_pinned_python_build_environment",
        lambda _root: interpreter,
    )

    result = sdk.run_sdk_build(
        repo_root=tmp_path,
        build_type="Release",
        stage_args=[],
        build_csharp=False,
        dry_run=True,
    )

    output = capsys.readouterr().out
    normalized = output.replace("\\", "/")
    assert result == 0
    assert "scripts/build/bindings.sh" in normalized
    assert "scripts/build/csharp.sh" not in normalized
    assert "Skipping C# bindings (use --csharp on Linux)." in output


def test_linux_sdk_build_can_request_csharp(tmp_path, monkeypatch, capsys):
    interpreter = tmp_path / "python"
    interpreter.write_text("", encoding="utf-8")
    monkeypatch.setattr(sdk, "_is_windows", lambda: False)
    monkeypatch.setattr(
        sdk,
        "_python_version_and_paths",
        lambda _python: {
            "version": "3.10",
            "soabi": "cpython-310-x86_64-linux-gnu",
            "free_threaded": False,
            "py_gil_disabled": False,
        },
    )
    monkeypatch.setattr(sdk, "_python_executable", lambda: str(interpreter))

    result = sdk.run_sdk_build(
        repo_root=tmp_path,
        build_type="Release",
        stage_args=[],
        build_csharp=True,
        dry_run=True,
    )

    output = capsys.readouterr().out
    normalized = output.replace("\\", "/")
    assert result == 0
    assert "scripts/build/csharp.sh --profile=full" in normalized


def test_linux_csharp_stage_accepts_forwarded_profiles() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    csharp_script = (repo_root / "scripts/build/csharp.sh").read_text(encoding="utf-8")

    assert '[[ "$arg" == --profile=* ]]' in csharp_script
    assert "full|plot-d3d11)" in csharp_script
    assert '-DTERMIN_CSHARP_PROFILE="$PROFILE"' in csharp_script


def test_csharp_build_entrypoints_reset_generated_bindings() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    linux_script = (repo_root / "scripts/build/csharp.sh").read_text(encoding="utf-8")
    windows_script = (repo_root / "scripts/build/csharp.ps1").read_text(encoding="utf-8")

    assert 'find "$generated_dir" -maxdepth 1 -type f -delete' in linux_script
    assert "Get-ChildItem -Path $generatedDir -File" in windows_script
    assert "Remove-Item -Force" in windows_script


def test_graphics_sdk_profile_selects_chart_capable_native_and_csharp_stages(
    tmp_path,
    monkeypatch,
    capsys,
):
    interpreter = tmp_path / "python"
    interpreter.write_text("", encoding="utf-8")
    monkeypatch.setattr(sdk.sys, "platform", "win32")
    monkeypatch.setattr(
        sdk.shutil,
        "which",
        lambda name: "C:/Program Files/PowerShell/7/pwsh.exe" if name == "pwsh" else None,
    )

    result = sdk.run_sdk_build(
        repo_root=tmp_path,
        build_type="Release",
        stage_args=["--no-sdl", "--no-vulkan", "--no-opengl"],
        build_csharp=True,
        dry_run=True,
        profile_name="graphics",
    )

    output = capsys.readouterr().out
    assert result == 0
    normalized = output.replace("\\", "/")
    assert "scripts/build/bindings.ps1 --profile=graphics --no-sdl" in normalized
    assert "scripts/build/csharp.ps1 --profile=plot-d3d11 --no-sdl" in normalized


@pytest.mark.parametrize(
    "relative_script",
    (
        "scripts/build/cpp.ps1",
        "scripts/build/bindings.ps1",
        "scripts/test/cpp.ps1",
    ),
)
def test_windows_native_graphs_always_build_d3d11_shader_artifacts(
    relative_script: str,
) -> None:
    windows_script = (REPO_ROOT / relative_script).read_text(encoding="utf-8")

    assert '$TerminBuildBuiltinShaderArtifacts = "ON"' in windows_script
    assert '$TerminBuiltinShaderArtifactTargets = if ($TerminEnableOpenGl -eq "ON") {' in windows_script
    assert '"d3d11;opengl330"' in windows_script
    assert re.search(r'}\s*else\s*{\s*"d3d11"\s*}', windows_script)


def test_bindings_entrypoints_expose_core_profile_contract() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    linux_script = (repo_root / "scripts/build/bindings.sh").read_text(encoding="utf-8")
    windows_script = (repo_root / "scripts/build/bindings.ps1").read_text(encoding="utf-8")

    assert "full|graphics|core" in linux_script
    assert '@("full", "graphics", "core")' in windows_script
    assert "TERMIN_BUILD_BUILTIN_SHADER_ARTIFACTS=OFF" in linux_script
    assert '$TerminBuildBuiltinShaderArtifacts = "ON"' in windows_script


def test_sdk_build_publishes_and_verifies_canonical_wheelhouse(
    tmp_path,
    monkeypatch,
):
    interpreter = tmp_path / "python"
    interpreter.write_text("", encoding="utf-8")
    calls = []

    monkeypatch.setattr(sdk, "_python_executable", lambda: str(interpreter))
    monkeypatch.setattr(
        sdk,
        "prepare_pinned_python_build_environment",
        lambda _root: interpreter,
    )
    current_abi = artifact_manifest.PythonAbiIdentity.current()
    monkeypatch.setattr(
        sdk,
        "_python_version_and_paths",
        lambda _python: {
            "version": current_abi.version,
            "soabi": current_abi.soabi,
            "free_threaded": current_abi.free_threaded,
            "py_gil_disabled": current_abi.free_threaded,
        },
    )
    monkeypatch.setattr(sdk, "_run", lambda *args, **kwargs: 0)
    monkeypatch.setattr(
        sdk,
        "install_python_packages",
        lambda *args, **kwargs: calls.append("install") or 0,
    )
    monkeypatch.setattr(
        sdk,
        "write_artifacts",
        lambda *args, **kwargs: calls.append("manifest") or 0,
    )
    monkeypatch.setattr(
        sdk,
        "_publish_runtime_wheelhouse",
        lambda *args, **kwargs: calls.append("publish") or 0,
    )
    monkeypatch.setattr(
        sdk,
        "_verify_library_wheel_subset_install",
        lambda *args, **kwargs: calls.append("subset") or 0,
    )

    def verify_sdk(_sdk_prefix, _build_dir, **_kwargs):
        calls.append("verify")
        return 0

    monkeypatch.setattr(sdk, "verify_sdk", verify_sdk)

    result = sdk.run_sdk_build(
        repo_root=tmp_path,
        build_type="Release",
        stage_args=[],
        build_csharp=False,
        dry_run=False,
    )

    assert result == 0
    assert calls == ["install", "manifest", "publish", "subset", "verify"]


def test_wheelhouse_arg_parser_keeps_stage_args_but_extracts_wheel_options(tmp_path):
    sdk_prefix = tmp_path / "sdk"
    build_dir = tmp_path / "build" / "Release"

    wheel_dir, effective_build_dir = sdk_wheel_pipeline._parse_wheelhouse_args(
        sdk_prefix,
        build_dir,
        ["--no-parallel", "--wheel-dir", str(tmp_path / "wheels"), "--force"],
    )

    assert wheel_dir == tmp_path / "wheels"
    assert effective_build_dir == build_dir


def test_write_android_capabilities_records_placeholder_and_full_abis(tmp_path):
    sdk_root = tmp_path / "sdk"
    android_sdk_root = sdk_root / "android"
    vulkan_library = tmp_path / "ndk/libvulkan.so"
    vulkan_library.parent.mkdir(parents=True)
    vulkan_library.write_bytes(b"vulkan")

    placeholder_build = tmp_path / "build-placeholder"
    placeholder_build.mkdir()
    (placeholder_build / "CMakeCache.txt").write_text(
        "TERMIN_OPENXR_HAS_HEADERS:INTERNAL=OFF\n"
        "TERMIN_ENABLE_VULKAN:BOOL=ON\n"
        f"ANDROID_VULKAN_LIB:FILEPATH={vulkan_library}\n",
        encoding="utf-8",
    )
    assert (
        sdk.write_android_capabilities(
            sdk_root=sdk_root,
            android_sdk_root=android_sdk_root,
            abi="x86_64",
            build_dir=placeholder_build,
        )
        == 0
    )

    full_prefix = android_sdk_root / "arm64-v8a"
    loader = full_prefix / "lib/libopenxr_loader.so"
    loader.parent.mkdir(parents=True)
    loader.write_bytes(b"openxr")
    full_build = tmp_path / "build-full"
    full_build.mkdir()
    (full_build / "CMakeCache.txt").write_text(
        "TERMIN_OPENXR_HAS_HEADERS:INTERNAL=ON\n"
        "TERMIN_ENABLE_VULKAN:BOOL=ON\n"
        f"ANDROID_VULKAN_LIB:FILEPATH={vulkan_library}\n",
        encoding="utf-8",
    )
    assert (
        sdk.write_android_capabilities(
            sdk_root=sdk_root,
            android_sdk_root=android_sdk_root,
            abi="arm64-v8a",
            build_dir=full_build,
        )
        == 0
    )

    placeholder = json.loads(
        (android_sdk_root / "x86_64/share/termin/android-capabilities.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((sdk_root / "termin-sdk-capabilities.json").read_text(encoding="utf-8"))
    assert placeholder["openxr_headers"] is False
    assert placeholder["openxr_loader"] is False
    assert placeholder["vulkan"] is True
    assert manifest["platforms"]["android"] == {
        "abis": ["arm64-v8a", "x86_64"],
        "python_runtime": False,
        "vulkan": True,
    }
    assert manifest["platforms"]["quest_openxr"] == {
        "abis": ["arm64-v8a"],
        "openxr_headers": True,
        "openxr_loader": True,
        "vulkan": True,
    }


@pytest.mark.parametrize("obsolete_flag", ["--no-wheels", "--wheels"])
def test_sdk_build_rejects_removed_wheel_flags(obsolete_flag, capsys):
    result = sdk.main(["build", obsolete_flag, "--dry-run"])

    captured = capsys.readouterr()
    assert result == 2
    assert f"{obsolete_flag} was removed" in captured.err
