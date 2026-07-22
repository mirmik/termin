from pathlib import Path

import pytest

from termin.project_build.build_context import create_build_context, resolve_build_dist_dir


def _write_project(tmp_path: Path, name: str = "ContextGame") -> Path:
    project = tmp_path / name
    project.mkdir()
    (project / f"{name}.terminproj").write_text(
        "{\n"
        '  "version": 1,\n'
        f'  "name": "{name}"\n'
        "}\n",
        encoding="utf-8",
    )
    (project / "Scenes").mkdir()
    (project / "Scenes" / "Main.scene").write_text("{}", encoding="utf-8")
    return project


def test_create_build_context_uses_project_name_and_default_desktop_dirs(tmp_path: Path) -> None:
    project = _write_project(tmp_path)

    context = create_build_context(
        project_root=project,
        entry_scene="Scenes/Main.scene",
        target="desktop",
    )

    assert context.project_root == project.resolve()
    assert context.project_name == "ContextGame"
    assert context.target == "desktop"
    assert context.configuration == "dev"
    assert context.resource_policy == "strict"
    assert context.entry_scene == (project / "Scenes" / "Main.scene").resolve()
    assert context.scenes == ((project / "Scenes" / "Main.scene").resolve(),)
    assert context.dist_dir == (project / "dist" / "desktop" / "ContextGame").resolve()
    assert context.package_dir == context.dist_dir / "package"
    assert context.logs_dir == context.dist_dir / "logs"
    assert context.target_options == {}


def test_create_build_context_uses_target_default_dist_dirs(tmp_path: Path) -> None:
    project = _write_project(tmp_path)

    android_context = create_build_context(project, "Scenes/Main.scene", "android")
    quest_context = create_build_context(project, "Scenes/Main.scene", "quest_openxr")

    assert android_context.dist_dir == (project / "dist" / "android" / "ContextGame").resolve()
    assert quest_context.dist_dir == (project / "dist" / "quest_openxr" / "ContextGame").resolve()


def test_create_build_context_resolves_explicit_scene_roots(tmp_path: Path) -> None:
    project = _write_project(tmp_path)
    menu = project / "Scenes" / "Menu.scene"
    menu.write_text("{}", encoding="utf-8")

    context = create_build_context(
        project_root=project,
        entry_scene="Scenes/Main.scene",
        scenes=("Scenes/Main.scene", menu),
        target="desktop",
    )

    assert context.scenes == (
        (project / "Scenes/Main.scene").resolve(),
        menu.resolve(),
    )


def test_create_build_context_uses_explicit_output_and_target_options(tmp_path: Path) -> None:
    project = _write_project(tmp_path)
    output_dir = tmp_path / "external-output"

    context = create_build_context(
        project_root=project,
        entry_scene=project / "Scenes" / "Main.scene",
        target="android",
        output_dir=output_dir,
        project_name="OverrideName",
        configuration="debug",
        resource_policy="dev_smoke",
        target_options={
            "abi": "arm64-v8a",
            "platform": "android-26",
        },
    )

    assert context.project_name == "OverrideName"
    assert context.configuration == "debug"
    assert context.resource_policy == "dev_smoke"
    assert context.dist_dir == output_dir.resolve()
    assert context.package_dir == output_dir.resolve() / "package"
    assert context.logs_dir == output_dir.resolve() / "logs"
    assert context.target_options == {
        "abi": "arm64-v8a",
        "platform": "android-26",
    }


def test_create_build_context_rejects_unknown_target_default_output(tmp_path: Path) -> None:
    project = _write_project(tmp_path)

    with pytest.raises(ValueError, match="Unsupported build target"):
        create_build_context(project, "Scenes/Main.scene", "unknown")


def test_resolve_build_dist_dir_allows_unknown_target_with_explicit_output(tmp_path: Path) -> None:
    project = _write_project(tmp_path)
    output_dir = tmp_path / "custom-output"

    assert resolve_build_dist_dir(project, "ContextGame", "unknown", output_dir) == output_dir.resolve()
