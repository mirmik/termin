import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from termin.project_build import profile_build
from termin.project_build.profile_requests import ToolchainContext, compile_profile_build_request
from termin.project_build.profiles import BuildProfileStore, ProfileBuildError


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_project(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "ProfileGame"
    project.mkdir()
    _write_json(project / "ProfileGame.terminproj", {"version": 1, "name": "ProfileGame"})
    _write_json(project / "Scenes" / "Main.scene", {"uuid": "main-scene", "entities": []})
    return project, project / "project_settings" / "build_profiles.json"


def _content(**overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
        "entry_scene": "Scenes/Main.scene",
        "scenes": ["Scenes/Main.scene"],
        "modules": [],
        "python": {"requirements": []},
        "resources": {"policy": "strict", "include": []},
    }
    result.update(overrides)
    return result


def _desktop_profile(**overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
        "target": {"kind": "desktop", "os": "linux", "arch": "x86_64"},
        "configuration": "dev",
        "content": _content(),
        "runtime": {"backends": ["vulkan", "opengl"]},
    }
    result.update(overrides)
    return result


def _android_profile(**overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
        "target": {"kind": "android", "abi": "x86_64", "ndk_api": 29},
        "configuration": "debug",
        "content": _content(),
    }
    result.update(overrides)
    return result


def _quest_profile(**overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
        "target": {"kind": "quest_openxr", "abi": "arm64-v8a", "ndk_api": 26},
        "configuration": "debug",
        "content": _content(),
    }
    result.update(overrides)
    return result


def _write_profiles(path: Path, profiles: dict[str, object], version: int = 2) -> None:
    _write_json(path, {"version": version, "profiles": profiles})


def _package_result(tmp_path: Path) -> SimpleNamespace:
    package_dir = tmp_path / "package"
    package_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = package_dir / "manifest.json"
    _write_json(manifest_path, {"resources": []})
    return SimpleNamespace(package_dir=package_dir, manifest_path=manifest_path)


def test_compile_desktop_request_is_pure_and_uses_profile_defaults(tmp_path: Path) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_profiles(profiles_path, {"dev": _desktop_profile()})
    profile = BuildProfileStore.load(project, profiles_path).get_profile("dev")

    request = compile_profile_build_request(profile)

    assert request.target == "desktop"
    assert request.target_os == "linux"
    assert request.target_arch == "x86_64"
    assert request.context.entry_scene == (project / "Scenes/Main.scene").resolve()
    assert request.context.dist_dir == (project / "dist/dev").resolve()
    assert request.context.target_options == {"desktop": {"os": "linux", "arch": "x86_64"}}
    assert request.runtime_backends == ("vulkan", "opengl")
    assert request.shader_compiler is None
    assert request.sdk_root is None


def test_compile_android_and_quest_requests_use_local_toolchain_context(tmp_path: Path) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_profiles(
        profiles_path,
        {"mobile": _android_profile(), "quest": _quest_profile()},
    )
    store = BuildProfileStore.load(project, profiles_path)
    local = ToolchainContext(
        termin_root=tmp_path / "termin-root",
        android_build_script=tmp_path / "build-android.sh",
        quest_openxr_build_script=tmp_path / "build-quest.sh",
        gradle=tmp_path / "gradle",
    )

    android = compile_profile_build_request(store.get_profile("mobile"), local)
    quest = compile_profile_build_request(store.get_profile("quest"), local)

    assert android.target == "android"
    assert android.target_os == "android"
    assert android.abi == "x86_64"
    assert android.platform == "android-29"
    assert android.runtime_backends == ("vulkan",)
    assert android.build_script == tmp_path / "build-android.sh"
    assert android.gradle == tmp_path / "gradle"
    assert android.context.target_options == {"android": {"abi": "x86_64", "ndk_api": 29}}

    assert quest.target == "quest_openxr"
    assert quest.abi == "arm64-v8a"
    assert quest.platform == "android-26"
    assert quest.build_script == tmp_path / "build-quest.sh"
    assert quest.context.target_options == {
        "quest_openxr": {"abi": "arm64-v8a", "ndk_api": 26}
    }


def test_profile_build_routes_desktop_typed_request(tmp_path: Path, monkeypatch) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_json(project / "Scenes" / "Menu.scene", {"uuid": "menu", "entities": []})
    profile_data = _desktop_profile(
        output_dir="dist/linux-dev",
        runtime={
            "backends": ["vulkan", "opengl"],
            "python_package_policy": "sdk_broad_copy",
        },
    )
    profile_data["content"] = _content(
        python={"requirements": ["python-chess"]},
        scenes=["Scenes/Main.scene", "Scenes/Menu.scene"],
        modules=["gameplay"],
        resources={"policy": "dev_smoke", "include": []},
    )
    _write_profiles(profiles_path, {"dev": profile_data})
    calls: list[dict] = []

    def fake_build_desktop_project(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            dist_dir=kwargs["output_dir"],
            app_manifest_path=kwargs["output_dir"] / "app.json",
            package_result=_package_result(tmp_path),
            diagnostics=[],
        )

    monkeypatch.setattr(profile_build, "build_desktop_project", fake_build_desktop_project)

    assert profile_build.main(
        [
            "build",
            "--project-root",
            str(project),
            "--profiles-path",
            str(profiles_path),
            "--profile",
            "dev",
            "--target",
            "desktop",
        ]
    ) == 0

    assert calls == [
        {
            "project_root": project.resolve(),
                "entry_scene": (project / "Scenes/Main.scene").resolve(),
                "scenes": (
                    (project / "Scenes/Main.scene").resolve(),
                    (project / "Scenes/Menu.scene").resolve(),
                ),
            "output_dir": (project / "dist/linux-dev").resolve(),
            "shader_compiler": None,
            "default_shader_language": "slang",
            "shader_targets": ("vulkan", "opengl"),
            "sdk_root": None,
            "target_os": "linux",
            "target_arch": "x86_64",
            "configuration": "dev",
            "resource_policy": "dev_smoke",
            "python_package_policy": "sdk_broad_copy",
            "python_requirements": ("python-chess",),
            "modules": ("gameplay",),
        }
    ]


@pytest.mark.parametrize(
    ("profile_data", "builder_name", "target", "expected"),
    [
        (
            _android_profile(output_dir="dist/mobile"),
            "build_android_project",
            "android",
            {"abi": "x86_64", "platform": "android-29"},
        ),
        (
            _quest_profile(output_dir="dist/quest"),
            "build_quest_openxr_project",
            "quest_openxr",
            {"abi": "arm64-v8a", "platform": "android-26"},
        ),
    ],
)
def test_profile_build_routes_android_family_typed_request(
    tmp_path: Path,
    monkeypatch,
    profile_data: dict[str, object],
    builder_name: str,
    target: str,
    expected: dict[str, str],
) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_profiles(profiles_path, {"product": profile_data})
    calls: list[dict] = []

    def fake_builder(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            apk_path=kwargs["output_dir"] / "apk/app-debug.apk",
            package_result=_package_result(tmp_path),
            log_path=kwargs["output_dir"] / "logs/build.log",
            application_id="org.termin.product",
            application_label="Termin Product",
            version_code=1,
            version_name="0.1.0",
            launch_activity="android.app.NativeActivity",
            diagnostics=[],
        )

    monkeypatch.setattr(profile_build, builder_name, fake_builder)

    assert profile_build.main(
        [
            "build",
            "--project-root",
            str(project),
            "--profiles-path",
            str(profiles_path),
            "--profile",
            "product",
            "--target",
            target,
        ]
    ) == 0

    assert calls[0]["abi"] == expected["abi"]
    assert calls[0]["platform"] == expected["platform"]
    assert calls[0]["shader_targets"] == ("vulkan",)
    assert calls[0]["termin_root"] is None
    assert calls[0]["build_script"] is None
    assert calls[0]["gradle"] is None


def test_build_accepts_scenes_and_modules_but_rejects_pending_resource_roots(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_json(project / "Scenes" / "Menu.scene", {"uuid": "menu", "entities": []})
    profile_data = _desktop_profile()
    profile_data["content"] = _content(
        scenes=["Scenes/Main.scene", "Scenes/Menu.scene"],
        modules=["gameplay"],
        resources={"policy": "strict", "include": ["Materials/Dynamic.material"]},
    )
    _write_profiles(profiles_path, {"dev": profile_data})
    calls: list[dict] = []
    monkeypatch.setattr(profile_build, "build_desktop_project", lambda **kwargs: calls.append(kwargs))
    profile = BuildProfileStore.load(project, profiles_path).get_profile("dev")

    with pytest.raises(ProfileBuildError) as raised:
        profile_build.build_profile(profile)

    assert calls == []
    assert {diagnostic.path.rsplit(".", 1)[-1] for diagnostic in raised.value.diagnostics} == {"include"}


def test_build_rejects_d3d11_without_local_fxc(tmp_path: Path, monkeypatch) -> None:
    project, profiles_path = _write_project(tmp_path)
    profile_data = _desktop_profile()
    profile_data["target"] = {"kind": "desktop", "os": "windows", "arch": "x86_64"}
    profile_data["runtime"] = {"backends": ["d3d11"]}
    _write_profiles(profiles_path, {"windows": profile_data})
    profile = BuildProfileStore.load(project, profiles_path).get_profile("windows")
    calls: list[dict] = []
    monkeypatch.setattr(profile_build, "build_desktop_project", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(profile_build, "_d3d11_shader_compiler_available", lambda sdk_root: False)

    with pytest.raises(ProfileBuildError, match="runtime backend 'd3d11'.*fxc") as raised:
        profile_build.build_profile(profile)

    assert calls == []
    assert raised.value.diagnostics[0].code == "capability.shader_compiler"
    assert raised.value.diagnostics[0].path == "toolchain.shader_compiler"


def test_explicit_shader_compiler_is_local_context_not_profile_data(tmp_path: Path) -> None:
    project, profiles_path = _write_project(tmp_path)
    profile_data = _desktop_profile()
    profile_data["target"] = {"kind": "desktop", "os": "windows", "arch": "x86_64"}
    profile_data["runtime"] = {"backends": ["d3d11"]}
    _write_profiles(profiles_path, {"windows": profile_data})
    profile = BuildProfileStore.load(project, profiles_path).get_profile("windows")
    compiler = tmp_path / "fxc.exe"

    request = compile_profile_build_request(
        profile,
        ToolchainContext(shader_compiler=compiler),
    )

    assert request.shader_compiler == compiler
    assert request.target_os == "windows"


@pytest.mark.parametrize(
    ("output_dir", "message"),
    [
        ("build/dev", "Refusing to use project-internal"),
        (".", "path must not resolve to the project root"),
    ],
)
def test_profile_build_rejects_unsafe_output(
    tmp_path: Path,
    output_dir: str,
    message: str,
) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_profiles(profiles_path, {"dev": _desktop_profile(output_dir=output_dir)})

    with pytest.raises(ProfileBuildError, match=message):
        profile = BuildProfileStore.load(project, profiles_path).get_profile("dev")
        profile_build.build_profile(profile)


def test_profile_build_rejects_missing_entry_scene_before_wrapper(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_profiles(
        profiles_path,
        {"dev": _desktop_profile(content=_content(entry_scene="Scenes/Missing.scene", scenes=["Scenes/Missing.scene"]))},
    )
    calls: list[dict] = []
    monkeypatch.setattr(profile_build, "build_desktop_project", lambda **kwargs: calls.append(kwargs))
    profile = BuildProfileStore.load(project, profiles_path).get_profile("dev")

    with pytest.raises(ProfileBuildError, match="Entry scene does not exist") as raised:
        profile_build.build_profile(profile)

    assert calls == []
    assert raised.value.diagnostics[0].code == "project.resolution"
    assert raised.value.diagnostics[0].path == "profiles.dev.content.scenes[0]"


def test_profile_build_reports_missing_secondary_scene_at_profile_path(tmp_path: Path) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_profiles(
        profiles_path,
        {
            "dev": _desktop_profile(
                content=_content(
                    scenes=["Scenes/Main.scene", "Scenes/Missing.scene"]
                )
            )
        },
    )
    profile = BuildProfileStore.load(project, profiles_path).get_profile("dev")

    with pytest.raises(ProfileBuildError, match="Selected scene does not exist") as raised:
        profile_build.build_profile(profile)

    assert raised.value.diagnostics[0].path == "profiles.dev.content.scenes[1]"


def test_profile_build_rejects_launcher_target_mismatch(tmp_path: Path, capsys) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_profiles(profiles_path, {"dev": _desktop_profile()})

    assert profile_build.main(
        [
            "build",
            "--project-root",
            str(project),
            "--profiles-path",
            str(profiles_path),
            "--profile",
            "dev",
            "--target",
            "android",
        ]
    ) == 2
    assert "target mismatch" in capsys.readouterr().err


def test_profile_build_cli_rejects_schema_v1(tmp_path: Path, capsys) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_profiles(profiles_path, {"dev": _desktop_profile()}, version=1)

    assert profile_build.main(
        [
            "build",
            "--project-root",
            str(project),
            "--profiles-path",
            str(profiles_path),
            "--profile",
            "dev",
        ]
    ) == 2
    assert "schema v1 is not migrated automatically" in capsys.readouterr().err


def test_profile_build_resolve_writes_canonical_request_summary(tmp_path: Path) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_profiles(profiles_path, {"dev": _desktop_profile()})
    request_path = tmp_path / "request.json"

    assert profile_build.main(
        [
            "resolve",
            "--project-root",
            str(project),
            "--profiles-path",
            str(profiles_path),
            "--profile",
            "dev",
            "--request-output",
            str(request_path),
        ]
    ) == 0

    summary = json.loads(request_path.read_text(encoding="utf-8"))
    assert summary == {
        "backends": ["vulkan", "opengl"],
        "entry_scene": str((project / "Scenes/Main.scene").resolve()),
        "modules": [],
        "output_dir": str((project / "dist/dev").resolve()),
        "profile": "dev",
        "scenes": [str((project / "Scenes/Main.scene").resolve())],
        "target": "desktop",
        "target_arch": "x86_64",
        "target_os": "linux",
    }


def test_profile_build_list_and_show_use_typed_store(tmp_path: Path, capsys) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_profiles(profiles_path, {"dev": _desktop_profile()})

    assert profile_build.main(
        [
            "profiles",
            "--project-root",
            str(project),
            "--profiles-path",
            str(profiles_path),
        ]
    ) == 0
    assert "dev (desktop)" in capsys.readouterr().out

    assert profile_build.main(
        [
            "profile",
            "--project-root",
            str(project),
            "--profiles-path",
            str(profiles_path),
            "--profile",
            "dev",
        ]
    ) == 0
    output = capsys.readouterr().out
    assert "Target: desktop" in output
    assert "Runtime backends: vulkan, opengl" in output


def test_profile_build_returns_nonzero_for_builder_error_diagnostic(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_profiles(profiles_path, {"dev": _desktop_profile()})
    diagnostic = SimpleNamespace(level="error", path="manifest.json", message="package is invalid")

    def fake_builder(**kwargs):
        return SimpleNamespace(
            dist_dir=kwargs["output_dir"],
            app_manifest_path=kwargs["output_dir"] / "app.json",
            package_result=_package_result(tmp_path),
            diagnostics=[diagnostic],
        )

    monkeypatch.setattr(profile_build, "build_desktop_project", fake_builder)

    assert profile_build.main(
        [
            "build",
            "--project-root",
            str(project),
            "--profiles-path",
            str(profiles_path),
            "--profile",
            "dev",
        ]
    ) == 1
    assert "error: manifest.json: package is invalid" in capsys.readouterr().out
