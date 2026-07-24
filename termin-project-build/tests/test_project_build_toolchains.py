import json
import os
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from termin.project_build.capability_reports import inspect_profile_capabilities
from termin.project_build.profile_build import main
from termin.project_build.profiles import BuildProfileStore
from termin.project_build.runtime_package import shaders
from termin.project_build.toolchains import (
    StaticToolchainContextProvider,
    ToolchainContext,
    create_local_toolchain_context,
    resolve_toolchain_context,
)


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_tool(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def _write_project(tmp_path: Path, target: dict[str, object]) -> tuple[Path, Path]:
    project = tmp_path / "ProfileGame"
    project.mkdir()
    _write_json(project / "ProfileGame.terminproj", {"version": 1, "name": "ProfileGame"})
    _write_json(project / "Scenes/Main.scene", {"uuid": "main", "entities": []})
    profiles_path = project / "project_settings/build_profiles.json"
    profile: dict[str, object] = {
        "target": target,
        "configuration": "debug",
        "content": {
            "entry_scene": "Scenes/Main.scene",
            "scenes": ["Scenes/Main.scene"],
            "modules": [],
            "python": {"requirements": []},
            "resources": {"policy": "strict", "include": []},
        },
    }
    if target["kind"] == "desktop":
        profile["runtime"] = {"backends": ["vulkan"]}
    _write_json(profiles_path, {"version": 2, "profiles": {"dev": profile}})
    return project, profiles_path


def _write_sdk(
    root: Path,
    *,
    desktop_os: str = "linux",
    desktop_arch: str = "x86_64",
    android_abis: tuple[str, ...] = (),
    quest_abis: tuple[str, ...] = (),
) -> ToolchainContext:
    shaderc = _write_tool(root / "bin/termin_shaderc")
    _write_tool(root / "bin/termin_player")
    android_root = root / "android"
    android_root.mkdir(parents=True)
    _write_json(
        root / "termin-sdk-capabilities.json",
        {
            "version": 1,
            "sdk_version": "test",
            "platforms": {
                "desktop": {
                    "os": desktop_os,
                    "arch": desktop_arch,
                    "player": True,
                    "native_libraries": True,
                    "python_runtime": True,
                    "builtin_shaders": True,
                },
                "android": {
                    "abis": list(android_abis),
                    "vulkan": bool(android_abis),
                    "python_runtime": bool(android_abis),
                },
                "quest_openxr": {
                    "abis": list(quest_abis),
                    "openxr_headers": bool(quest_abis),
                    "openxr_loader": bool(quest_abis),
                    "vulkan": bool(quest_abis),
                },
            },
            "tools": {
                "termin_shaderc": "bin/termin_shaderc",
                "termin_player": "bin/termin_player",
            },
        },
    )
    return ToolchainContext(
        sdk_root=root,
        android_sdk_root=android_root,
        shader_compiler=shaderc,
    )


def test_provider_precedence_is_per_field_and_derivation_uses_final_roots(
    tmp_path: Path,
) -> None:
    install_sdk = tmp_path / "install-sdk"
    env_sdk = tmp_path / "env-sdk"
    editor_sdk = tmp_path / "editor-sdk"
    invocation_shaderc = _write_tool(tmp_path / "invocation/termin_shaderc")
    editor_fxc = _write_tool(editor_sdk / "bin/fxc")
    editor_gradle = _write_tool(tmp_path / "editor/gradle")

    context = create_local_toolchain_context(
        installation_defaults=ToolchainContext(sdk_root=install_sdk),
        environ={"TERMIN_SDK": str(env_sdk), "GRADLE_BIN": str(tmp_path / "env/gradle")},
        editor_settings=ToolchainContext(sdk_root=editor_sdk, gradle=editor_gradle),
        invocation_overrides=ToolchainContext(shader_compiler=invocation_shaderc),
        path_search=lambda _name: None,
    )

    assert context.sdk_root == editor_sdk.resolve()
    assert context.shader_compiler == invocation_shaderc.resolve()
    assert context.fxc == editor_fxc.resolve()
    assert context.gradle == editor_gradle.resolve()
    assert context.android_sdk_root == (editor_sdk / "android").resolve()


def test_resolver_normalizes_static_provider_paths(tmp_path: Path) -> None:
    relative = Path("relative-sdk")
    context = resolve_toolchain_context(
        [StaticToolchainContextProvider(ToolchainContext(sdk_root=relative))],
        path_search=lambda _name: None,
    )
    assert context.sdk_root == (Path.cwd() / relative).resolve()


def test_explicit_environment_does_not_leak_process_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    tools = tmp_path / "process-tools"
    _write_tool(tools / ("termin_shaderc.exe" if os.name == "nt" else "termin_shaderc"))
    _write_tool(tools / ("gradle.exe" if os.name == "nt" else "gradle"))
    monkeypatch.setenv("PATH", str(tools))

    context = create_local_toolchain_context(
        installation_defaults=ToolchainContext(),
        environ={},
    )

    assert context.shader_compiler is None
    assert context.gradle is None


def test_supplied_environment_path_drives_tool_discovery(tmp_path: Path) -> None:
    tools = tmp_path / "environment-tools"
    shaderc = _write_tool(
        tools / ("termin_shaderc.exe" if os.name == "nt" else "termin_shaderc")
    )
    gradle = _write_tool(tools / ("gradle.exe" if os.name == "nt" else "gradle"))

    context = create_local_toolchain_context(
        installation_defaults=ToolchainContext(),
        environ={"PATH": str(tools)},
    )

    assert context.shader_compiler == shaderc.resolve()
    assert context.gradle == gradle.resolve()


def test_desktop_report_is_stable_and_does_not_mutate_profile(tmp_path: Path) -> None:
    project, profiles_path = _write_project(
        tmp_path,
        {"kind": "desktop", "os": "linux", "arch": "x86_64"},
    )
    profile = BuildProfileStore.load(project, profiles_path).get_profile("dev")
    before = profiles_path.read_bytes()
    local = _write_sdk(tmp_path / "sdk")

    report = inspect_profile_capabilities(
        profile,
        installation_defaults=ToolchainContext(),
        invocation_overrides=local,
        environ={},
        host_os="linux",
    )

    assert report.buildable
    assert report.diagnostics == ()
    assert profiles_path.read_bytes() == before


def test_desktop_report_distinguishes_invalid_sdk_and_missing_tools(tmp_path: Path) -> None:
    project, profiles_path = _write_project(
        tmp_path,
        {"kind": "desktop", "os": "windows", "arch": "x86_64"},
    )
    profile = BuildProfileStore.load(project, profiles_path).get_profile("dev")
    invalid_sdk = tmp_path / "sdk"
    invalid_sdk.mkdir()
    _write_json(invalid_sdk / "termin-sdk-capabilities.json", {"version": 99})

    report = inspect_profile_capabilities(
        profile,
        installation_defaults=ToolchainContext(),
        invocation_overrides=ToolchainContext(sdk_root=invalid_sdk),
        environ={},
        host_os="linux",
    )
    codes = {diagnostic.code for diagnostic in report.diagnostics}

    assert "capability.sdk.invalid" in codes
    assert "capability.shader_compiler.missing" in codes
    assert "capability.host_platform.mismatch" in codes


def test_android_report_has_stable_build_tool_and_abi_codes(tmp_path: Path) -> None:
    project, profiles_path = _write_project(
        tmp_path,
        {"kind": "quest_openxr", "abi": "arm64-v8a", "ndk_api": 26},
    )
    profile = BuildProfileStore.load(project, profiles_path).get_profile("dev")
    local = _write_sdk(tmp_path / "sdk", android_abis=("x86_64",))
    termin_root = tmp_path / "termin"
    termin_root.mkdir()
    local = replace(
        local,
        termin_root=termin_root,
        quest_openxr_build_script=termin_root / "missing-quest-build.sh",
    )

    report = inspect_profile_capabilities(
        profile,
        installation_defaults=ToolchainContext(),
        invocation_overrides=local,
        environ={},
    )
    codes = {diagnostic.code for diagnostic in report.diagnostics}

    assert "capability.build_script.invalid" in codes
    assert "capability.gradle.missing" in codes
    assert "capability.android_sdk.abi_mismatch" in codes
    assert "capability.quest_openxr.mismatch" in codes


def test_cli_json_is_the_same_canonical_report_as_editor_api(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    project, profiles_path = _write_project(
        tmp_path,
        {"kind": "desktop", "os": "linux", "arch": "x86_64"},
    )
    local = _write_sdk(tmp_path / "sdk")
    monkeypatch.setenv("TERMIN_SDK", str(local.sdk_root))
    monkeypatch.setenv("TERMIN_SHADERC", str(local.shader_compiler))
    profile = BuildProfileStore.load(project, profiles_path).get_profile("dev")

    expected = inspect_profile_capabilities(profile, host_os="linux").to_dict()
    assert main(
        [
            "capabilities",
            "--project-root",
            str(project),
            "--profiles-path",
            str(profiles_path),
            "--profile",
            "dev",
            "--json",
        ]
    ) == 0

    assert json.loads(capsys.readouterr().out) == expected


def test_d3d11_compilation_receives_resolved_fxc(tmp_path: Path, monkeypatch) -> None:
    compiler = _write_tool(tmp_path / "termin_shaderc")
    fxc = _write_tool(tmp_path / "fxc")
    source = tmp_path / "shader.slang"
    source.write_text("shader", encoding="utf-8")
    output = tmp_path / "shader.dxbc"
    commands: list[list[str]] = []

    def run(command, **_kwargs):
        commands.append(command)
        output.write_bytes(b"dxbc")
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(shaders.subprocess, "run", run)

    shaders.compile_shader_stage(
        compiler,
        "slang",
        "d3d11",
        "vertex",
        source,
        output,
        "test",
        fxc=fxc,
    )

    assert commands[0][commands[0].index("--fxc") + 1] == str(fxc)
