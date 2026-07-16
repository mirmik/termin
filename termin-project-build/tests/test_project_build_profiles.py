import json
from pathlib import Path

import pytest

from termin.project_build.profiles import BuildProfileStore, ProfileBuildError


def _profile(target: str = "desktop") -> dict[str, object]:
    return {
        "target": target,
        "entry_scene": "Scenes/Main.scene",
        "output_dir": "dist/app",
        "shader_targets": ["vulkan"],
    }


def test_profile_store_loads_lists_and_resolves_project_paths(tmp_path: Path) -> None:
    project_root = tmp_path / "Project"
    profiles_path = project_root / "project_settings" / "build_profiles.json"
    profiles_path.parent.mkdir(parents=True)
    profiles_path.write_text(
        json.dumps(
            {
                "version": 1,
                "profiles": {
                    "release": _profile(),
                    "dev": _profile(),
                },
            }
        ),
        encoding="utf-8",
    )

    store = BuildProfileStore.load(project_root, profiles_path)

    assert store.profile_names() == ("dev", "release")
    profile = store.get_profile("dev")
    assert profile.project_root == project_root.resolve()
    assert profile.entry_scene == (project_root / "Scenes/Main.scene").resolve()
    assert profile.output_dir == (project_root / "dist/app").resolve()


def test_profile_store_update_and_save_are_deterministic(tmp_path: Path) -> None:
    project_root = tmp_path / "Project"
    profiles_path = project_root / "project_settings" / "build_profiles.json"
    store = BuildProfileStore.create(project_root, profiles_path)

    source = _profile("android")
    profile = store.update_profile("mobile", source)
    source["target"] = "changed-after-update"

    assert profile.target == "android"
    first_path = store.save()
    first_contents = first_path.read_text(encoding="utf-8")
    store.save()

    assert first_path.read_text(encoding="utf-8") == first_contents
    assert first_contents.endswith("\n")
    assert json.loads(first_contents) == {
        "version": 1,
        "profiles": {"mobile": _profile("android")},
    }
    assert not list(profiles_path.parent.glob("*.tmp"))


@pytest.mark.parametrize(
    ("document", "message"),
    [
        ([], "root must be a JSON object"),
        ({"profiles": {}}, "must contain integer field 'version' with value 1"),
        ({"version": "1", "profiles": {}}, "field 'version' must be an integer"),
        ({"version": 2, "profiles": {}}, "unsupported build profile schema version 2"),
        ({"version": 1, "profiles": []}, "must contain object field 'profiles'"),
    ],
)
def test_profile_store_rejects_malformed_documents(
    tmp_path: Path,
    document: object,
    message: str,
) -> None:
    profiles_path = tmp_path / "build_profiles.json"
    profiles_path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ProfileBuildError, match=message):
        BuildProfileStore.load(tmp_path, profiles_path)


def test_profile_store_rejects_malformed_profile_on_lookup(tmp_path: Path) -> None:
    profiles_path = tmp_path / "build_profiles.json"
    profiles_path.write_text(
        json.dumps({"version": 1, "profiles": {"dev": {"target": "desktop"}}}),
        encoding="utf-8",
    )

    store = BuildProfileStore.load(tmp_path, profiles_path)

    with pytest.raises(
        ProfileBuildError,
        match="profile 'dev' must contain non-empty string field 'entry_scene'",
    ):
        store.get_profile("dev")
