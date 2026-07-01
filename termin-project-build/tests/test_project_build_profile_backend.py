import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from termin.project_build import profile_build


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_project(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "ProfileGame"
    project.mkdir()
    _write_json(project / "ProfileGame.terminproj", {"version": 1, "name": "ProfileGame"})
    _write_json(project / "Scenes" / "Main.scene", {"uuid": "main-scene", "entities": []})
    profiles_path = project / "project_settings" / "build_profiles.json"
    return project, profiles_path


def _package_result(tmp_path: Path) -> SimpleNamespace:
    package_dir = tmp_path / "package"
    package_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = package_dir / "manifest.json"
    _write_json(manifest_path, {"resources": []})
    return SimpleNamespace(package_dir=package_dir, manifest_path=manifest_path)


def test_profile_build_routes_desktop_profile(tmp_path: Path, monkeypatch) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_json(
        profiles_path,
        {
            "version": 1,
            "profiles": {
                "dev": {
                    "target": "desktop",
                    "entry_scene": "Scenes/Main.scene",
                    "output_dir": "dist/dev",
                    "default_shader_language": "slang",
                    "shader_targets": ["vulkan", "opengl"],
                    "desktop": {"sdk_root": str(tmp_path / "sdk")},
                }
            }
        },
    )
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
            "entry_scene": (project / "Scenes" / "Main.scene").resolve(),
            "output_dir": (project / "dist" / "dev").resolve(),
            "shader_compiler": None,
            "default_shader_language": "slang",
            "shader_targets": ("vulkan", "opengl"),
            "sdk_root": tmp_path / "sdk",
            "configuration": "dev",
            "resource_policy": "strict",
        }
    ]


def test_profile_build_routes_android_profile(tmp_path: Path, monkeypatch) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_json(
        profiles_path,
        {
            "version": 1,
            "profiles": {
                "mobile": {
                    "target": "android",
                    "entry_scene": "Scenes/Main.scene",
                    "output_dir": "dist/android/mobile",
                    "android": {
                        "abi": "x86_64",
                        "platform": "android-29",
                        "gradle": str(tmp_path / "gradle"),
                    },
                }
            }
        },
    )
    calls: list[dict] = []

    def fake_build_android_project(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            apk_path=kwargs["output_dir"] / "apk" / "ProfileGame-debug.apk",
            package_result=_package_result(tmp_path),
            log_path=kwargs["output_dir"] / "logs" / "android-build.log",
            application_id="org.termin.builds.profilegame",
            launch_activity="org.termin.android.TerminActivity",
            diagnostics=[],
        )

    monkeypatch.setattr(profile_build, "build_android_project", fake_build_android_project)

    assert profile_build.main(
        [
            "build",
            "--project-root",
            str(project),
            "--profiles-path",
            str(profiles_path),
            "--profile",
            "mobile",
            "--target",
            "android",
        ]
    ) == 0

    assert calls == [
        {
            "project_root": project.resolve(),
            "entry_scene": (project / "Scenes" / "Main.scene").resolve(),
            "output_dir": (project / "dist" / "android" / "mobile").resolve(),
            "termin_root": None,
            "build_script": None,
            "gradle": tmp_path / "gradle",
            "shader_compiler": None,
            "default_shader_language": "slang",
            "shader_targets": None,
            "abi": "x86_64",
            "platform": "android-29",
            "configuration": "dev",
            "resource_policy": "strict",
        }
    ]


def test_profile_build_routes_quest_openxr_profile(tmp_path: Path, monkeypatch) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_json(
        profiles_path,
        {
            "version": 1,
            "profiles": {
                "quest": {
                    "target": "quest_openxr",
                    "entry_scene": "Scenes/Main.scene",
                    "output_dir": "dist/quest",
                    "android": {
                        "abi": "arm64-v8a",
                        "platform": "android-26",
                        "gradle": str(tmp_path / "gradle"),
                    },
                    "openxr": {
                        "build_script": str(tmp_path / "build-quest-openxr-apk.sh"),
                    },
                }
            }
        },
    )
    calls: list[dict] = []

    def fake_build_quest_openxr_project(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            apk_path=kwargs["output_dir"] / "apk" / "ProfileGame-quest-openxr-debug.apk",
            package_result=_package_result(tmp_path),
            log_path=kwargs["output_dir"] / "logs" / "quest-openxr-build.log",
            application_id="org.termin.openxr",
            launch_activity="android.app.NativeActivity",
            diagnostics=[],
        )

    monkeypatch.setattr(profile_build, "build_quest_openxr_project", fake_build_quest_openxr_project)

    assert profile_build.main(
        [
            "build",
            "--project-root",
            str(project),
            "--profiles-path",
            str(profiles_path),
            "--profile",
            "quest",
            "--target",
            "quest_openxr",
        ]
    ) == 0

    assert calls == [
        {
            "project_root": project.resolve(),
            "entry_scene": (project / "Scenes" / "Main.scene").resolve(),
            "output_dir": (project / "dist" / "quest").resolve(),
            "termin_root": None,
            "build_script": tmp_path / "build-quest-openxr-apk.sh",
            "gradle": tmp_path / "gradle",
            "shader_compiler": None,
            "default_shader_language": "slang",
            "shader_targets": None,
            "abi": "arm64-v8a",
            "platform": "android-26",
            "configuration": "dev",
            "resource_policy": "strict",
        }
    ]


def test_profile_build_normalizes_desktop_request(tmp_path: Path) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_json(
        profiles_path,
        {
            "version": 1,
            "profiles": {
                "dev": {
                    "target": "desktop",
                    "entry_scene": "Scenes/Main.scene",
                    "output_dir": "dist/dev",
                    "shader_targets": ["vulkan", "opengl"],
                    "desktop": {"sdk_root": str(tmp_path / "sdk")},
                }
            },
        },
    )

    profile = profile_build.load_build_profile(project, profiles_path, "dev")
    request = profile_build.normalize_profile_build_request(profile)

    assert request.name == "dev"
    assert request.target == "desktop"
    assert request.context.project_root == project.resolve()
    assert request.context.entry_scene == (project / "Scenes" / "Main.scene").resolve()
    assert request.context.dist_dir == (project / "dist" / "dev").resolve()
    assert request.context.configuration == "dev"
    assert request.context.resource_policy == "strict"
    assert request.context.target_options == {"desktop": {"sdk_root": str(tmp_path / "sdk")}}
    assert request.shader_targets == ("vulkan", "opengl")
    assert request.sdk_root == tmp_path / "sdk"
    assert request.termin_root is None
    assert request.gradle is None


def test_profile_build_routes_profile_shader_targets(tmp_path: Path, monkeypatch) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_json(
        profiles_path,
        {
            "version": 1,
            "profiles": {
                "d3d": {
                    "target": "desktop",
                    "entry_scene": "Scenes/Main.scene",
                    "output_dir": "dist/d3d",
                    "shader_targets": ["vulkan", "opengl", "d3d11", "d3d11"],
                }
            },
        },
    )
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
    monkeypatch.setattr(profile_build, "_d3d11_shader_compiler_available", lambda sdk_root: True)

    assert profile_build.main(
        [
            "build",
            "--project-root",
            str(project),
            "--profiles-path",
            str(profiles_path),
            "--profile",
            "d3d",
            "--target",
            "desktop",
        ]
    ) == 0

    assert calls[0]["shader_targets"] == ("vulkan", "opengl", "d3d11")


def test_profile_build_routes_direct_desktop_shader_targets(tmp_path: Path, monkeypatch) -> None:
    project, _profiles_path = _write_project(tmp_path)
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
            "desktop",
            "--project-root",
            str(project),
            "--entry-scene",
            "Scenes/Main.scene",
            "--output-dir",
            "dist/d3d",
            "--shader-target",
            "vulkan",
            "--shader-target",
            "d3d11",
        ]
    ) == 0

    assert calls[0]["shader_targets"] == ("vulkan", "d3d11")


def test_profile_build_rejects_desktop_profile_without_shader_targets(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_json(
        profiles_path,
        {
            "version": 1,
            "profiles": {
                "dev": {
                    "target": "desktop",
                    "entry_scene": "Scenes/Main.scene",
                    "output_dir": "dist/dev",
                }
            },
        },
    )
    calls: list[dict] = []

    def fake_build_desktop_project(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(profile_build, "build_desktop_project", fake_build_desktop_project)

    profile = profile_build.load_build_profile(project, profiles_path, "dev")
    with pytest.raises(profile_build.ProfileBuildError, match="must set ordered field 'shader_targets'"):
        profile_build.build_profile(profile)

    assert calls == []


def test_profile_build_normalizes_explicit_profile_policy(tmp_path: Path) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_json(
        profiles_path,
        {
            "version": 1,
            "profiles": {
                "release": {
                    "target": "desktop",
                    "configuration": "release",
                    "resource_policy": "dev_smoke",
                    "entry_scene": "Scenes/Main.scene",
                    "output_dir": "dist/release",
                    "shader_targets": ["vulkan", "opengl"],
                }
            },
        },
    )

    profile = profile_build.load_build_profile(project, profiles_path, "release")
    request = profile_build.normalize_profile_build_request(profile)

    assert request.context.configuration == "release"
    assert request.context.resource_policy == "dev_smoke"


def test_profile_build_routes_desktop_python_package_policy(tmp_path: Path, monkeypatch) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_json(
        profiles_path,
        {
            "version": 1,
            "profiles": {
                "dev": {
                    "target": "desktop",
                    "entry_scene": "Scenes/Main.scene",
                    "output_dir": "dist/dev",
                    "shader_targets": ["vulkan", "opengl"],
                    "python": {
                        "package_policy": "sdk_broad_copy",
                        "requirements": ["python-chess"],
                    },
                }
            },
        },
    )
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

    assert calls[0]["python_package_policy"] == "sdk_broad_copy"
    assert calls[0]["python_requirements"] == ("python-chess",)


def test_profile_build_rejects_invalid_desktop_python_package_policy(tmp_path: Path) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_json(
        profiles_path,
        {
            "version": 1,
            "profiles": {
                "dev": {
                    "target": "desktop",
                    "entry_scene": "Scenes/Main.scene",
                    "output_dir": "dist/dev",
                    "shader_targets": ["vulkan", "opengl"],
                    "python": {"package_policy": "guess_imports"},
                }
            },
        },
    )

    profile = profile_build.load_build_profile(project, profiles_path, "dev")
    with pytest.raises(profile_build.ProfileBuildError, match="python.package_policy"):
        profile_build.normalize_profile_build_request(profile)


@pytest.mark.parametrize(
    ("shader_targets", "message"),
    [
        ("d3d11", "field 'shader_targets' must be a list"),
        ([], "field 'shader_targets' must not be empty"),
        (["vulkan", ""], "field 'shader_targets\\[1\\]' must be a non-empty string"),
        (["metal"], "Supported values: vulkan, opengl, d3d11"),
    ],
)
def test_profile_build_rejects_invalid_shader_targets_before_wrapper(
    tmp_path: Path,
    monkeypatch,
    shader_targets: object,
    message: str,
) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_json(
        profiles_path,
        {
            "version": 1,
            "profiles": {
                "dev": {
                    "target": "desktop",
                    "entry_scene": "Scenes/Main.scene",
                    "output_dir": "dist/dev",
                    "shader_targets": shader_targets,
                }
            },
        },
    )
    calls: list[dict] = []

    def fake_build_desktop_project(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(profile_build, "build_desktop_project", fake_build_desktop_project)

    profile = profile_build.load_build_profile(project, profiles_path, "dev")
    with pytest.raises(profile_build.ProfileBuildError, match=message):
        profile_build.build_profile(profile)

    assert calls == []


def test_profile_build_rejects_d3d11_without_fxc_before_wrapper(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_json(
        profiles_path,
        {
            "version": 1,
            "profiles": {
                "dev": {
                    "target": "desktop",
                    "entry_scene": "Scenes/Main.scene",
                    "output_dir": "dist/dev",
                    "shader_targets": ["vulkan", "opengl", "d3d11"],
                }
            },
        },
    )
    calls: list[dict] = []

    def fake_build_desktop_project(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(profile_build, "build_desktop_project", fake_build_desktop_project)
    monkeypatch.setattr(profile_build, "_d3d11_shader_compiler_available", lambda sdk_root: False)

    profile = profile_build.load_build_profile(project, profiles_path, "dev")
    with pytest.raises(profile_build.ProfileBuildError, match="requests shader target 'd3d11'.*fxc"):
        profile_build.build_profile(profile)

    assert calls == []


def test_profile_build_normalizes_android_request(tmp_path: Path) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_json(
        profiles_path,
        {
            "version": 1,
            "profiles": {
                "mobile": {
                    "target": "android",
                    "entry_scene": "Scenes/Main.scene",
                    "output_dir": "dist/android/mobile",
                    "android": {
                        "abi": "x86_64",
                        "platform": "android-29",
                        "build_script": "tools/build-android.sh",
                    },
                }
            },
        },
    )

    profile = profile_build.load_build_profile(project, profiles_path, "mobile")
    request = profile_build.normalize_profile_build_request(profile)

    assert request.target == "android"
    assert request.context.dist_dir == (project / "dist" / "android" / "mobile").resolve()
    assert request.context.configuration == "dev"
    assert request.context.resource_policy == "strict"
    assert request.context.target_options == {
        "android": {
            "abi": "x86_64",
            "platform": "android-29",
            "build_script": "tools/build-android.sh",
        }
    }
    assert request.build_script == project.resolve() / "tools" / "build-android.sh"
    assert request.abi == "x86_64"
    assert request.platform == "android-29"


def test_profile_build_normalizes_quest_openxr_request(tmp_path: Path) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_json(
        profiles_path,
        {
            "version": 1,
            "profiles": {
                "quest": {
                    "target": "quest_openxr",
                    "entry_scene": "Scenes/Main.scene",
                    "output_dir": "dist/quest",
                    "android": {
                        "gradle": str(tmp_path / "gradle"),
                    },
                    "openxr": {
                        "build_script": str(tmp_path / "build-quest-openxr-apk.sh"),
                    },
                }
            },
        },
    )

    profile = profile_build.load_build_profile(project, profiles_path, "quest")
    request = profile_build.normalize_profile_build_request(profile)

    assert request.target == "quest_openxr"
    assert request.context.configuration == "dev"
    assert request.context.resource_policy == "strict"
    assert request.context.target_options == {
        "android": {"gradle": str(tmp_path / "gradle")},
        "openxr": {"build_script": str(tmp_path / "build-quest-openxr-apk.sh")},
    }
    assert request.gradle == tmp_path / "gradle"
    assert request.build_script == tmp_path / "build-quest-openxr-apk.sh"
    assert request.abi == "arm64-v8a"
    assert request.platform == "android-26"


def test_profile_build_rejects_unsupported_target_block_before_wrapper(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_json(
        profiles_path,
        {
            "version": 1,
            "profiles": {
                "dev": {
                    "target": "desktop",
                    "entry_scene": "Scenes/Main.scene",
                    "output_dir": "dist/dev",
                    "android": {"abi": "x86_64"},
                }
            },
        },
    )
    calls: list[dict] = []

    def fake_build_desktop_project(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(profile_build, "build_desktop_project", fake_build_desktop_project)

    profile = profile_build.load_build_profile(project, profiles_path, "dev")
    with pytest.raises(profile_build.ProfileBuildError, match="does not support option block 'android'"):
        profile_build.build_profile(profile)

    assert calls == []


@pytest.mark.parametrize(
    ("field_name", "field_value", "message"),
    [
        ("configuration", "shipping", "Supported values: dev, debug, release"),
        ("resource_policy", "placeholder", "Supported values: dev_smoke, strict"),
    ],
)
def test_profile_build_rejects_unsupported_profile_policy_before_wrapper(
    tmp_path: Path,
    monkeypatch,
    field_name: str,
    field_value: str,
    message: str,
) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_json(
        profiles_path,
        {
            "version": 1,
            "profiles": {
                "dev": {
                    "target": "desktop",
                    field_name: field_value,
                    "entry_scene": "Scenes/Main.scene",
                    "output_dir": "dist/dev",
                }
            },
        },
    )
    calls: list[dict] = []

    def fake_build_desktop_project(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(profile_build, "build_desktop_project", fake_build_desktop_project)

    profile = profile_build.load_build_profile(project, profiles_path, "dev")
    with pytest.raises(profile_build.ProfileBuildError, match=message):
        profile_build.build_profile(profile)

    assert calls == []


@pytest.mark.parametrize(
    ("profile_target", "builder_name", "result_fields"),
    [
        (
            "desktop",
            "build_desktop_project",
            {
                "dist_dir": "dist/dev",
                "app_manifest_path": "dist/dev/app.json",
            },
        ),
        (
            "android",
            "build_android_project",
            {
                "apk_path": "dist/dev/apk/ProfileGame-debug.apk",
                "log_path": "dist/dev/logs/android-build.log",
                "application_id": "org.termin.builds.profilegame",
                "launch_activity": "org.termin.android.TerminActivity",
            },
        ),
        (
            "quest_openxr",
            "build_quest_openxr_project",
            {
                "apk_path": "dist/dev/apk/ProfileGame-quest-openxr-debug.apk",
                "log_path": "dist/dev/logs/quest-openxr-build.log",
                "application_id": "org.termin.openxr",
                "launch_activity": "android.app.NativeActivity",
            },
        ),
    ],
)
def test_profile_build_returns_nonzero_when_builder_reports_error_diagnostic(
    tmp_path: Path,
    monkeypatch,
    profile_target: str,
    builder_name: str,
    result_fields: dict[str, str],
    capsys,
) -> None:
    project, profiles_path = _write_project(tmp_path)
    profile_data = {
        "target": profile_target,
        "entry_scene": "Scenes/Main.scene",
        "output_dir": "dist/dev",
    }
    if profile_target == "desktop":
        profile_data["shader_targets"] = ["vulkan", "opengl"]
    _write_json(
        profiles_path,
        {
            "version": 1,
            "profiles": {"dev": profile_data},
        },
    )
    diagnostic = SimpleNamespace(
        level="error",
        path="manifest.json",
        message="package is invalid",
    )

    def fake_builder(**kwargs):
        resolved_fields = {
            key: project / value
            if key.endswith("_path") or key.endswith("_dir")
            else value
            for key, value in result_fields.items()
        }
        return SimpleNamespace(
            package_result=_package_result(tmp_path),
            diagnostics=[diagnostic],
            **resolved_fields,
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
            "dev",
            "--target",
            profile_target,
        ]
    ) == 1

    captured = capsys.readouterr()
    assert "error: manifest.json: package is invalid" in captured.out


def test_profile_build_rejects_unsafe_output_before_wrapper(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_json(
        profiles_path,
        {
            "version": 1,
            "profiles": {
                "dev": {
                    "target": "desktop",
                    "entry_scene": "Scenes/Main.scene",
                    "output_dir": "build/dev",
                }
            },
        },
    )
    calls: list[dict] = []

    def fake_build_desktop_project(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(profile_build, "build_desktop_project", fake_build_desktop_project)

    profile = profile_build.load_build_profile(project, profiles_path, "dev")
    with pytest.raises(profile_build.ProfileBuildError, match="Refusing to use project-internal"):
        profile_build.build_profile(profile)

    assert calls == []


def test_profile_build_rejects_missing_entry_scene_before_wrapper(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_json(
        profiles_path,
        {
            "version": 1,
            "profiles": {
                "dev": {
                    "target": "desktop",
                    "entry_scene": "Scenes/Missing.scene",
                    "output_dir": "dist/dev",
                }
            },
        },
    )
    calls: list[dict] = []

    def fake_build_desktop_project(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(profile_build, "build_desktop_project", fake_build_desktop_project)

    profile = profile_build.load_build_profile(project, profiles_path, "dev")
    with pytest.raises(profile_build.ProfileBuildError, match="Entry scene does not exist"):
        profile_build.build_profile(profile)

    assert calls == []


def test_profile_build_rejects_unsupported_target_with_supported_list(tmp_path: Path, capsys) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_json(
        profiles_path,
        {
            "version": 1,
            "profiles": {
                "web": {
                    "target": "web",
                    "entry_scene": "Scenes/Main.scene",
                    "output_dir": "dist/web",
                }
            }
        },
    )

    assert profile_build.main(
        [
            "build",
            "--project-root",
            str(project),
            "--profiles-path",
            str(profiles_path),
            "--profile",
            "web",
            "--target",
            "web",
        ]
    ) == 3

    captured = capsys.readouterr()
    assert "unsupported build target 'web'" in captured.err
    assert "Supported targets: android, desktop, quest_openxr" in captured.err


def test_profile_build_rejects_launcher_target_mismatch(tmp_path: Path, capsys) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_json(
        profiles_path,
        {
            "version": 1,
            "profiles": {
                "dev": {
                    "target": "desktop",
                    "entry_scene": "Scenes/Main.scene",
                    "output_dir": "dist/dev",
                }
            }
        },
    )

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

    captured = capsys.readouterr()
    assert "target mismatch" in captured.err


def test_profile_build_rejects_missing_schema_version(tmp_path: Path, capsys) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_json(
        profiles_path,
        {
            "profiles": {
                "dev": {
                    "target": "desktop",
                    "entry_scene": "Scenes/Main.scene",
                    "output_dir": "dist/dev",
                }
            }
        },
    )

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

    captured = capsys.readouterr()
    assert "must contain integer field 'version' with value 1" in captured.err


def test_profile_build_rejects_unsupported_schema_version(tmp_path: Path, capsys) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_json(
        profiles_path,
        {
            "version": 2,
            "profiles": {
                "dev": {
                    "target": "desktop",
                    "entry_scene": "Scenes/Main.scene",
                    "output_dir": "dist/dev",
                }
            },
        },
    )

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

    captured = capsys.readouterr()
    assert "unsupported build profile schema version 2" in captured.err
