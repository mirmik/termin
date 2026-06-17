import json
from pathlib import Path
from types import SimpleNamespace

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
            "profiles": {
                "dev": {
                    "target": "desktop",
                    "entry_scene": "Scenes/Main.scene",
                    "output_dir": "dist/dev",
                    "default_shader_language": "slang",
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
            "sdk_root": tmp_path / "sdk",
        }
    ]


def test_profile_build_routes_android_profile(tmp_path: Path, monkeypatch) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_json(
        profiles_path,
        {
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
            "abi": "x86_64",
            "platform": "android-29",
        }
    ]


def test_profile_build_routes_quest_openxr_profile(tmp_path: Path, monkeypatch) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_json(
        profiles_path,
        {
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
            "abi": "arm64-v8a",
            "platform": "android-26",
        }
    ]


def test_profile_build_rejects_unsupported_target_with_supported_list(tmp_path: Path, capsys) -> None:
    project, profiles_path = _write_project(tmp_path)
    _write_json(
        profiles_path,
        {
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
