from pathlib import Path

import pytest

from termin.project.scene_paths import project_scene_identity, scene_display_label


def test_project_scene_identity_is_project_relative_posix(tmp_path: Path) -> None:
    scene = tmp_path / "Scenes" / "Acts" / "Main.scene"
    assert project_scene_identity(tmp_path, scene) == "Scenes/Acts/Main.scene"
    assert project_scene_identity(tmp_path, "Scenes/Acts/Main.scene") == (
        "Scenes/Acts/Main.scene"
    )
    assert project_scene_identity(tmp_path, "Scenes/Other/Main.scene") != (
        project_scene_identity(tmp_path, scene)
    )


def test_project_scene_identity_rejects_outside_project(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="outside project root"):
        project_scene_identity(tmp_path / "Project", tmp_path / "Other.scene")


def test_project_scene_identity_requires_scene_suffix(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=".scene suffix"):
        project_scene_identity(tmp_path, tmp_path / "Scenes" / "Main.json")


def test_scene_display_label_is_not_the_identity() -> None:
    assert scene_display_label("Scenes/Acts/Main.scene") == "Main"
