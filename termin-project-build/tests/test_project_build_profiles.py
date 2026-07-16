import json
from pathlib import Path

import pytest

from termin.project_build.profiles import (
    AndroidTarget,
    BuildProfile,
    BuildProfileStore,
    DesktopTarget,
    ProfileBuildError,
    ProfileContent,
    QuestOpenXRTarget,
)


def _content(entry_scene: str = "Scenes/Main.scene") -> dict[str, object]:
    return {
        "entry_scene": entry_scene,
        "scenes": [entry_scene],
        "modules": [],
        "python": {"requirements": []},
        "resources": {"policy": "strict", "include": []},
    }


def _desktop_profile() -> dict[str, object]:
    return {
        "target": {"kind": "desktop", "os": "linux", "arch": "x86_64"},
        "configuration": "dev",
        "content": _content(),
        "runtime": {
            "backends": ["vulkan", "opengl"],
            "python_package_policy": "minimal_strict",
        },
    }


def _android_profile() -> dict[str, object]:
    return {
        "target": {"kind": "android", "abi": "x86_64", "ndk_api": 29},
        "configuration": "debug",
        "content": _content(),
        "output_dir": "dist/android-debug",
    }


def _quest_profile() -> dict[str, object]:
    return {
        "target": {"kind": "quest_openxr", "abi": "arm64-v8a", "ndk_api": 26},
        "configuration": "release",
        "content": _content("Scenes/XR.scene"),
    }


def _write_document(path: Path, profiles: dict[str, object], version: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"version": version, "profiles": profiles}),
        encoding="utf-8",
    )


def test_profile_store_loads_closed_target_variants(tmp_path: Path) -> None:
    project_root = tmp_path / "Project"
    profiles_path = project_root / "project_settings" / "build_profiles.json"
    _write_document(
        profiles_path,
        {
            "linux": _desktop_profile(),
            "android": _android_profile(),
            "quest": _quest_profile(),
        },
    )

    store = BuildProfileStore.load(project_root, profiles_path)

    assert store.profile_names() == ("android", "linux", "quest")
    desktop = store.get_profile("linux")
    assert isinstance(desktop.target, DesktopTarget)
    assert desktop.target.backends == ("vulkan", "opengl")
    assert desktop.content.entry_scene == Path("Scenes/Main.scene")
    assert desktop.output_dir is None

    android = store.get_profile("android")
    assert isinstance(android.target, AndroidTarget)
    assert android.target.abi == "x86_64"
    assert android.target.ndk_api == 29
    assert android.output_dir == Path("dist/android-debug")

    quest = store.get_profile("quest")
    assert isinstance(quest.target, QuestOpenXRTarget)
    assert quest.configuration == "release"
    assert quest.content.scenes == (Path("Scenes/XR.scene"),)


def test_profile_store_round_trip_is_canonical_and_deterministic(tmp_path: Path) -> None:
    project_root = tmp_path / "Project"
    profiles_path = project_root / "project_settings" / "build_profiles.json"
    _write_document(
        profiles_path,
        {"quest": _quest_profile(), "linux": _desktop_profile()},
    )
    store = BuildProfileStore.load(project_root, profiles_path)

    first_path = store.save()
    first_contents = first_path.read_text(encoding="utf-8")
    store.save()

    assert first_path.read_text(encoding="utf-8") == first_contents
    assert first_contents.endswith("\n")
    saved = json.loads(first_contents)
    assert saved["version"] == 2
    assert list(saved["profiles"]) == ["linux", "quest"]
    assert saved["profiles"]["linux"]["content"]["python"] == {"requirements": []}
    assert saved["profiles"]["linux"]["runtime"]["backends"] == ["vulkan", "opengl"]
    assert not list(profiles_path.parent.glob("*.tmp"))


def test_profile_store_typed_update_duplicate_and_delete(tmp_path: Path) -> None:
    project_root = tmp_path / "Project"
    store = BuildProfileStore.create(
        project_root,
        project_root / "project_settings" / "build_profiles.json",
    )
    source = BuildProfile(
        name="source-object-name",
        project_root=tmp_path / "OtherProject",
        target=DesktopTarget(
            os="linux",
            arch="x86_64",
            backends=("vulkan",),
        ),
        configuration="dev",
        content=ProfileContent(
            entry_scene=Path("Scenes/Main.scene"),
            scenes=(Path("Scenes/Main.scene"),),
            modules=(),
            python_requirements=(),
            resource_policy="strict",
            resource_includes=(),
        ),
    )

    stored = store.update_profile("dev", source)
    duplicate = store.duplicate_profile("dev", "release")
    store.delete_profile("dev")

    assert stored.name == "dev"
    assert stored.project_root == project_root.resolve()
    assert duplicate.name == "release"
    assert store.profile_names() == ("release",)


@pytest.mark.parametrize(
    ("replacement", "path_fragment"),
    [
        ({"output_dir": Path("../outside")}, "profile.output_dir"),
        ({"modules": ("game", "game")}, "profile.content.modules[1]"),
        ({"python_requirements": ("numpy", "numpy")}, "profile.content.python.requirements[1]"),
        ({"resource_includes": ("Assets/Dynamic", "")}, "profile.content.resources.include[1]"),
    ],
)
def test_profile_store_typed_update_enforces_serialized_invariants(
    tmp_path: Path,
    replacement: dict[str, object],
    path_fragment: str,
) -> None:
    store = BuildProfileStore.create(tmp_path, tmp_path / "build_profiles.json")
    content = ProfileContent(
        entry_scene=Path("Scenes/Main.scene"),
        scenes=(Path("Scenes/Main.scene"),),
        modules=replacement.get("modules", ()),
        python_requirements=replacement.get("python_requirements", ()),
        resource_policy="strict",
        resource_includes=replacement.get("resource_includes", ()),
    )
    profile = BuildProfile(
        name="dev",
        project_root=tmp_path,
        target=DesktopTarget(os="linux", arch="x86_64", backends=("vulkan",)),
        configuration="dev",
        content=content,
        output_dir=replacement.get("output_dir"),
    )

    with pytest.raises(ProfileBuildError) as raised:
        store.update_profile("dev", profile)

    assert path_fragment in raised.value.diagnostics[0].path


def test_profile_store_loads_foreign_platform_without_probing_tools(tmp_path: Path) -> None:
    profiles_path = tmp_path / "build_profiles.json"
    profile = _desktop_profile()
    profile["target"] = {"kind": "desktop", "os": "windows", "arch": "x86_64"}
    profile["runtime"] = {"backends": ["d3d11"]}
    _write_document(profiles_path, {"windows": profile})

    loaded = BuildProfileStore.load(tmp_path / "MissingProject", profiles_path).get_profile("windows")

    assert isinstance(loaded.target, DesktopTarget)
    assert loaded.target.os == "windows"
    assert loaded.target.backends == ("d3d11",)


@pytest.mark.parametrize(
    ("version", "code", "message"),
    [
        (1, "profile.version_unsupported", "schema v1 is not migrated automatically"),
        (3, "profile.version_unsupported", "supported version is 2"),
    ],
)
def test_profile_store_rejects_old_and_unknown_versions(
    tmp_path: Path,
    version: int,
    code: str,
    message: str,
) -> None:
    profiles_path = tmp_path / "build_profiles.json"
    _write_document(profiles_path, {"dev": _desktop_profile()}, version=version)

    with pytest.raises(ProfileBuildError, match=message) as raised:
        BuildProfileStore.load(tmp_path, profiles_path)

    assert raised.value.diagnostics[0].code == code
    assert raised.value.diagnostics[0].path.endswith("build_profiles.json.version")


@pytest.mark.parametrize(
    ("mutate", "code", "path_fragment", "message"),
    [
        (
            lambda profile: profile.update({"legacy": True}),
            "profile.unknown_field",
            "profiles.dev.legacy",
            "unknown field",
        ),
        (
            lambda profile: profile["target"].update({"abi": "arm64-v8a"}),
            "profile.unknown_field",
            "profiles.dev.target.abi",
            "unknown field",
        ),
        (
            lambda profile: profile["runtime"].update({"backends": ["vulkan", "vulkan"]}),
            "profile.duplicate",
            "runtime.backends[1]",
            "duplicate value 'vulkan'",
        ),
        (
            lambda profile: profile["content"].update({"scenes": ["Scenes/Other.scene"]}),
            "profile.entry_scene",
            "content.entry_scene",
            "entry scene must also occur",
        ),
        (
            lambda profile: profile["content"].update({"modules": ["game", "game"]}),
            "profile.duplicate",
            "content.modules[1]",
            "duplicate value 'game'",
        ),
        (
            lambda profile: profile.update({"output_dir": "../outside"}),
            "profile.path",
            "output_dir",
            "path must stay relative",
        ),
    ],
)
def test_profile_store_reports_structured_path_specific_diagnostics(
    tmp_path: Path,
    mutate,
    code: str,
    path_fragment: str,
    message: str,
) -> None:
    profiles_path = tmp_path / "build_profiles.json"
    profile = _desktop_profile()
    mutate(profile)
    _write_document(profiles_path, {"dev": profile})

    with pytest.raises(ProfileBuildError, match=message) as raised:
        BuildProfileStore.load(tmp_path, profiles_path)

    diagnostic = raised.value.diagnostics[0]
    assert diagnostic.code == code
    assert path_fragment in diagnostic.path


def test_profile_store_rejects_runtime_block_for_fixed_android_target(tmp_path: Path) -> None:
    profiles_path = tmp_path / "build_profiles.json"
    profile = _android_profile()
    profile["runtime"] = {"backends": ["vulkan"]}
    _write_document(profiles_path, {"mobile": profile})

    with pytest.raises(ProfileBuildError, match="does not expose configurable runtime") as raised:
        BuildProfileStore.load(tmp_path, profiles_path)

    assert raised.value.diagnostics[0].code == "profile.target_field"


def test_profile_store_rejects_linux_d3d11_runtime(tmp_path: Path) -> None:
    profiles_path = tmp_path / "build_profiles.json"
    profile = _desktop_profile()
    profile["runtime"] = {"backends": ["vulkan", "d3d11"]}
    _write_document(profiles_path, {"dev": profile})

    with pytest.raises(ProfileBuildError, match="cannot run the d3d11 backend") as raised:
        BuildProfileStore.load(tmp_path, profiles_path)

    assert raised.value.diagnostics[0].code == "profile.backend_platform"
