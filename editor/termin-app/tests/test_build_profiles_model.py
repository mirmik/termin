from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from termin.editor_core.build_profiles_model import (
    BuildProfileAction,
    BuildProfileStorePersistence,
    BuildProfileTemplate,
    BuildProfilesController,
    BuildProfilesValidationError,
)
from termin.project_build import (
    AndroidTarget,
    BuildProfile,
    DesktopTarget,
    ProfileContent,
    ProfileDiagnostic,
)


class MemoryPersistence:
    def __init__(self, profiles: tuple[BuildProfile, ...]) -> None:
        self.profiles = profiles
        self.saved: list[tuple[BuildProfile, ...]] = []

    def load_profiles(self) -> tuple[BuildProfile, ...]:
        return self.profiles

    def save_profiles(self, profiles: tuple[BuildProfile, ...]) -> tuple[BuildProfile, ...]:
        self.saved.append(profiles)
        self.profiles = profiles
        return profiles


class ActionService:
    def __init__(self) -> None:
        self.diagnostics: dict[BuildProfileAction, tuple[ProfileDiagnostic, ...]] = {}
        self.executed: list[tuple[BuildProfileAction, BuildProfile]] = []

    def capability_diagnostics(
        self,
        action: BuildProfileAction,
        profile: BuildProfile,
    ) -> tuple[ProfileDiagnostic, ...]:
        return self.diagnostics.get(action, ())

    def execute(self, action: BuildProfileAction, profile: BuildProfile) -> None:
        self.executed.append((action, profile))


def _profile(name: str, *, mobile: bool = False) -> BuildProfile:
    target = (
        AndroidTarget(abi="arm64-v8a", ndk_api=29)
        if mobile
        else DesktopTarget(os="linux", arch="x86_64", backends=("vulkan",))
    )
    return BuildProfile(
        name=name,
        project_root=Path("/project"),
        target=target,
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


def _controller(
    profiles: tuple[BuildProfile, ...] = (),
    *,
    action_service: ActionService | None = None,
) -> tuple[BuildProfilesController, MemoryPersistence]:
    persistence = MemoryPersistence(profiles)
    template = BuildProfileTemplate("desktop", "Desktop", _profile("template"))
    return (
        BuildProfilesController(
            persistence,
            (template,),
            action_service=action_service,
        ),
        persistence,
    )


def test_selection_is_deterministic_and_does_not_dirty_collection() -> None:
    controller, _ = _controller((_profile("first"), _profile("second")))

    initial = controller.snapshot
    selected = controller.select(initial.entries[1].entry_id)

    assert initial.selected is not None
    assert initial.selected.profile.name == "first"
    assert selected.selected is not None
    assert selected.selected.profile.name == "second"
    assert not selected.dirty
    assert not selected.can_save


def test_add_duplicate_rename_and_delete_have_stable_order_and_selection() -> None:
    controller, _ = _controller((_profile("first"), _profile("last")))

    added = controller.add_from_template("desktop", "added")
    added_id = added.selected_id
    assert [entry.profile.name for entry in added.entries] == ["first", "last", "added"]

    duplicated = controller.duplicate_selected("copy")
    assert [entry.profile.name for entry in duplicated.entries] == [
        "first",
        "last",
        "added",
        "copy",
    ]
    assert duplicated.selected_id != added_id

    renamed = controller.rename_selected("renamed")
    assert renamed.selected is not None
    assert renamed.selected.profile.name == "renamed"

    after_delete = controller.delete_selected()
    assert after_delete.selected is not None
    assert after_delete.selected.profile.name == "added"
    assert [entry.profile.name for entry in after_delete.entries] == ["first", "last", "added"]


def test_invalid_draft_remains_visible_and_cannot_be_saved() -> None:
    controller, persistence = _controller((_profile("first"), _profile("second")))

    snapshot = controller.rename_selected("second")

    assert snapshot.selected is not None
    assert snapshot.selected.profile.name == "second"
    assert snapshot.dirty
    assert not snapshot.can_save
    assert snapshot.selected.diagnostics[0].code == "profile.duplicate"
    with pytest.raises(BuildProfilesValidationError) as raised:
        controller.save()
    assert raised.value.diagnostics[0].code == "profile.duplicate"
    assert not persistence.saved
    assert controller.snapshot.selected is not None
    assert controller.snapshot.selected.profile.name == "second"


def test_invalid_profile_edit_is_not_normalized_on_save() -> None:
    controller, persistence = _controller((_profile("dev"),))
    selected = controller.snapshot.selected
    assert selected is not None

    invalid = replace(selected.profile, name="", configuration="optimized")
    snapshot = controller.update_selected(invalid)

    assert snapshot.selected is not None
    assert snapshot.selected.profile == invalid
    assert snapshot.selected.diagnostics[0].path == "profile.name"
    with pytest.raises(BuildProfilesValidationError):
        controller.save()
    assert controller.snapshot.selected is not None
    assert controller.snapshot.selected.profile == invalid
    assert not persistence.saved


def test_save_clears_dirty_and_preserves_unrelated_profiles() -> None:
    controller, persistence = _controller((_profile("first"), _profile("second")))
    controller.rename_selected("renamed")

    saved = controller.save()

    assert not saved.dirty
    assert not saved.can_revert
    assert [profile.name for profile in persistence.profiles] == ["renamed", "second"]
    assert persistence.profiles[1] == _profile("second")


def test_revert_discards_draft_and_reloads_persisted_collection() -> None:
    controller, persistence = _controller((_profile("first"), _profile("second")))
    controller.rename_selected("draft")
    persistence.profiles = (_profile("external"), _profile("second"))

    reverted = controller.revert()

    assert [entry.profile.name for entry in reverted.entries] == ["external", "second"]
    assert reverted.selected is not None
    assert reverted.selected.profile.name == "external"
    assert not reverted.dirty


def test_capabilities_follow_target_validation_and_local_diagnostics() -> None:
    actions = ActionService()
    controller, _ = _controller((_profile("desktop"), _profile("android", mobile=True)), action_service=actions)

    desktop = controller.snapshot.capabilities
    assert desktop.build.enabled
    assert desktop.run.enabled
    assert desktop.dry_run.enabled
    assert not desktop.install.enabled
    assert not desktop.launch.enabled

    controller.select(controller.snapshot.entries[1].entry_id)
    android = controller.snapshot.capabilities
    assert android.build.enabled
    assert not android.run.enabled
    assert android.install.enabled
    assert android.launch.enabled
    assert android.dry_run.enabled

    unavailable = ProfileDiagnostic("tool.adb_missing", "tools.adb", "adb is unavailable")
    actions.diagnostics[BuildProfileAction.INSTALL] = (unavailable,)
    assert not controller.snapshot.capabilities.install.enabled
    assert controller.snapshot.capabilities.install.diagnostics == (unavailable,)

    controller.execute(BuildProfileAction.BUILD)
    assert actions.executed == [(BuildProfileAction.BUILD, _profile("android", mobile=True))]
    with pytest.raises(BuildProfilesValidationError):
        controller.execute(BuildProfileAction.INSTALL)


def test_no_selection_or_action_service_disables_actions_with_diagnostics() -> None:
    empty, _ = _controller()
    assert not empty.snapshot.capabilities.build.enabled
    assert empty.snapshot.capabilities.build.diagnostics

    controller, _ = _controller((_profile("desktop"),))
    assert not controller.snapshot.capabilities.build.enabled
    assert "unavailable" in controller.snapshot.capabilities.build.diagnostics[0].message


def test_unknown_template_and_entry_are_rejected_without_mutation() -> None:
    controller, _ = _controller((_profile("desktop"),))
    original = controller.snapshot

    with pytest.raises(KeyError):
        controller.add_from_template("missing", "new")
    with pytest.raises(KeyError):
        controller.select("missing")

    assert controller.snapshot == original


def test_store_persistence_round_trips_collection_without_reordering(tmp_path: Path) -> None:
    project_root = tmp_path.resolve()
    persistence = BuildProfileStorePersistence(
        project_root,
        project_root / "project_settings" / "build_profiles.json",
    )
    profiles = (
        replace(_profile("z-last"), project_root=project_root),
        replace(_profile("a-first"), project_root=project_root),
    )

    persisted = persistence.save_profiles(profiles)

    assert persisted == profiles
    assert [profile.name for profile in persistence.load_profiles()] == ["a-first", "z-last"]
