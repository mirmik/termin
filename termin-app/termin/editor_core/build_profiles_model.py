"""Toolkit-neutral draft controller for project build profiles."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Protocol

from termin.project_build import (
    AndroidTarget,
    BuildProfile,
    BuildProfileStore,
    DesktopTarget,
    ProfileBuildError,
    ProfileDiagnostic,
    QuestOpenXRTarget,
    validate_build_profile,
)


logger = logging.getLogger(__name__)


class BuildProfileAction(Enum):
    BUILD = "build"
    RUN = "run"
    INSTALL = "install"
    LAUNCH = "launch"
    DRY_RUN = "dry_run"


@dataclass(frozen=True)
class BuildProfileTemplate:
    template_id: str
    label: str
    profile: BuildProfile


@dataclass(frozen=True)
class BuildProfileActionCapability:
    enabled: bool
    diagnostics: tuple[ProfileDiagnostic, ...] = ()


@dataclass(frozen=True)
class BuildProfileActionCapabilities:
    build: BuildProfileActionCapability
    run: BuildProfileActionCapability
    install: BuildProfileActionCapability
    launch: BuildProfileActionCapability
    dry_run: BuildProfileActionCapability

    def for_action(self, action: BuildProfileAction) -> BuildProfileActionCapability:
        return {
            BuildProfileAction.BUILD: self.build,
            BuildProfileAction.RUN: self.run,
            BuildProfileAction.INSTALL: self.install,
            BuildProfileAction.LAUNCH: self.launch,
            BuildProfileAction.DRY_RUN: self.dry_run,
        }[action]


@dataclass(frozen=True)
class BuildProfileEntrySnapshot:
    entry_id: str
    profile: BuildProfile
    diagnostics: tuple[ProfileDiagnostic, ...]
    selected: bool


@dataclass(frozen=True)
class BuildProfilesSnapshot:
    entries: tuple[BuildProfileEntrySnapshot, ...]
    selected_id: str | None
    dirty: bool
    can_save: bool
    can_revert: bool
    capabilities: BuildProfileActionCapabilities

    @property
    def selected(self) -> BuildProfileEntrySnapshot | None:
        return next((entry for entry in self.entries if entry.selected), None)


class BuildProfilesValidationError(ProfileBuildError):
    """The visible draft collection cannot be persisted as-is."""


class BuildProfilesPersistence(Protocol):
    def load_profiles(self) -> tuple[BuildProfile, ...]: ...

    def save_profiles(self, profiles: tuple[BuildProfile, ...]) -> tuple[BuildProfile, ...]: ...


class BuildProfileActionService(Protocol):
    def capability_diagnostics(
        self,
        action: BuildProfileAction,
        profile: BuildProfile,
    ) -> tuple[ProfileDiagnostic, ...]: ...

    def execute(self, action: BuildProfileAction, profile: BuildProfile) -> None: ...


class BuildProfileStorePersistence:
    """Filesystem adapter kept outside the draft/controller state machine."""

    def __init__(self, project_root: Path, path: Path) -> None:
        self._project_root = project_root
        self._path = path

    def load_profiles(self) -> tuple[BuildProfile, ...]:
        if not self._path.exists():
            return ()
        store = BuildProfileStore.load(self._project_root, self._path)
        return tuple(store.get_profile(name) for name in store.profile_names())

    def save_profiles(self, profiles: tuple[BuildProfile, ...]) -> tuple[BuildProfile, ...]:
        store = BuildProfileStore.create(self._project_root, self._path)
        for profile in profiles:
            store.update_profile(profile.name, profile)
        store.save()
        return tuple(store.get_profile(profile.name) for profile in profiles)


@dataclass(frozen=True)
class _DraftEntry:
    entry_id: str
    profile: BuildProfile


_ALL_ACTIONS = tuple(BuildProfileAction)
_TARGET_ACTIONS = {
    DesktopTarget: frozenset(
        (BuildProfileAction.BUILD, BuildProfileAction.RUN, BuildProfileAction.DRY_RUN)
    ),
    AndroidTarget: frozenset(
        (
            BuildProfileAction.BUILD,
            BuildProfileAction.INSTALL,
            BuildProfileAction.LAUNCH,
            BuildProfileAction.DRY_RUN,
        )
    ),
    QuestOpenXRTarget: frozenset(
        (
            BuildProfileAction.BUILD,
            BuildProfileAction.INSTALL,
            BuildProfileAction.LAUNCH,
            BuildProfileAction.DRY_RUN,
        )
    ),
}


class BuildProfilesController:
    def __init__(
        self,
        persistence: BuildProfilesPersistence,
        templates: tuple[BuildProfileTemplate, ...],
        *,
        action_service: BuildProfileActionService | None = None,
    ) -> None:
        self._persistence = persistence
        self._action_service = action_service
        self._templates = self._index_templates(templates)
        self._next_draft_id = 1
        self._entries: tuple[_DraftEntry, ...] = ()
        self._baseline: tuple[BuildProfile, ...] = ()
        self._selected_id: str | None = None
        self._load()

    @property
    def snapshot(self) -> BuildProfilesSnapshot:
        diagnostics = self._entry_diagnostics()
        entries = tuple(
            BuildProfileEntrySnapshot(
                entry_id=entry.entry_id,
                profile=entry.profile,
                diagnostics=diagnostics[index],
                selected=entry.entry_id == self._selected_id,
            )
            for index, entry in enumerate(self._entries)
        )
        dirty = self._profiles() != self._baseline
        return BuildProfilesSnapshot(
            entries=entries,
            selected_id=self._selected_id,
            dirty=dirty,
            can_save=dirty and not any(diagnostics),
            can_revert=dirty,
            capabilities=self._capabilities(diagnostics),
        )

    def select(self, entry_id: str) -> BuildProfilesSnapshot:
        self._entry_index(entry_id)
        self._selected_id = entry_id
        return self.snapshot

    def add_from_template(self, template_id: str, name: str) -> BuildProfilesSnapshot:
        template = self._templates.get(template_id)
        if template is None:
            raise KeyError(f"unknown build profile template: {template_id}")
        entry = _DraftEntry(self._new_draft_id(), replace(template.profile, name=name))
        self._entries += (entry,)
        self._selected_id = entry.entry_id
        return self.snapshot

    def duplicate_selected(self, name: str) -> BuildProfilesSnapshot:
        source = self._selected_entry()
        entry = _DraftEntry(self._new_draft_id(), replace(source.profile, name=name))
        index = self._entry_index(source.entry_id)
        self._entries = self._entries[: index + 1] + (entry,) + self._entries[index + 1 :]
        self._selected_id = entry.entry_id
        return self.snapshot

    def rename_selected(self, name: str) -> BuildProfilesSnapshot:
        entry = self._selected_entry()
        return self.update_selected(replace(entry.profile, name=name))

    def update_selected(self, profile: BuildProfile) -> BuildProfilesSnapshot:
        index = self._entry_index(self._selected_entry().entry_id)
        self._entries = (
            self._entries[:index]
            + (_DraftEntry(self._entries[index].entry_id, profile),)
            + self._entries[index + 1 :]
        )
        return self.snapshot

    def delete_selected(self) -> BuildProfilesSnapshot:
        index = self._entry_index(self._selected_entry().entry_id)
        self._entries = self._entries[:index] + self._entries[index + 1 :]
        if self._entries:
            self._selected_id = self._entries[min(index, len(self._entries) - 1)].entry_id
        else:
            self._selected_id = None
        return self.snapshot

    def save(self) -> BuildProfilesSnapshot:
        diagnostics = tuple(
            diagnostic
            for entry_diagnostics in self._entry_diagnostics()
            for diagnostic in entry_diagnostics
        )
        if diagnostics:
            logger.warning("Build profile draft save rejected: %s", "; ".join(d.format() for d in diagnostics))
            raise BuildProfilesValidationError(diagnostics=diagnostics)
        try:
            persisted = self._persistence.save_profiles(self._profiles())
        except Exception:
            logger.exception("Failed to save build profile collection")
            raise
        if tuple(persisted) != self._profiles():
            logger.error("Build profile persistence changed the saved collection")
            raise RuntimeError("build profile persistence changed the saved collection")
        self._baseline = tuple(persisted)
        return self.snapshot

    def revert(self) -> BuildProfilesSnapshot:
        self._load()
        return self.snapshot

    def execute(self, action: BuildProfileAction) -> BuildProfilesSnapshot:
        capability = self.snapshot.capabilities.for_action(action)
        if not capability.enabled:
            raise BuildProfilesValidationError(diagnostics=capability.diagnostics)
        profile = self._selected_entry().profile
        assert self._action_service is not None
        try:
            self._action_service.execute(action, profile)
        except Exception:
            logger.exception("Build profile action '%s' failed for '%s'", action.value, profile.name)
            raise
        return self.snapshot

    def _load(self) -> None:
        try:
            profiles = tuple(self._persistence.load_profiles())
        except Exception:
            logger.exception("Failed to load build profile collection")
            raise
        self._baseline = profiles
        self._entries = tuple(
            _DraftEntry(f"stored:{profile.name}", profile) for profile in profiles
        )
        self._selected_id = self._entries[0].entry_id if self._entries else None

    def _profiles(self) -> tuple[BuildProfile, ...]:
        return tuple(entry.profile for entry in self._entries)

    def _entry_diagnostics(self) -> tuple[tuple[ProfileDiagnostic, ...], ...]:
        names: dict[str, int] = {}
        for entry in self._entries:
            names[entry.profile.name] = names.get(entry.profile.name, 0) + 1
        result: list[tuple[ProfileDiagnostic, ...]] = []
        for entry in self._entries:
            entry_diagnostics = list(validate_build_profile(entry.profile))
            if names[entry.profile.name] > 1:
                entry_diagnostics.append(
                    ProfileDiagnostic(
                        "profile.duplicate",
                        "profile.name",
                        f"build profile name '{entry.profile.name}' is not unique",
                    )
                )
            result.append(tuple(entry_diagnostics))
        return tuple(result)

    def _capabilities(
        self,
        diagnostics: tuple[tuple[ProfileDiagnostic, ...], ...],
    ) -> BuildProfileActionCapabilities:
        selected_index = None
        if self._selected_id is not None:
            selected_index = self._entry_index(self._selected_id)
        values: dict[BuildProfileAction, BuildProfileActionCapability] = {}
        for action in _ALL_ACTIONS:
            action_diagnostics: tuple[ProfileDiagnostic, ...]
            if selected_index is None:
                action_diagnostics = (_capability_diagnostic(action, "no build profile is selected"),)
            else:
                profile = self._entries[selected_index].profile
                supported = _TARGET_ACTIONS.get(type(profile.target), frozenset())
                if action not in supported:
                    action_diagnostics = (
                        _capability_diagnostic(
                            action,
                            f"action is not supported for target '{profile.target_kind}'",
                        ),
                    )
                elif diagnostics[selected_index]:
                    action_diagnostics = diagnostics[selected_index]
                elif self._action_service is None:
                    action_diagnostics = (_capability_diagnostic(action, "action service is unavailable"),)
                else:
                    action_diagnostics = self._action_service.capability_diagnostics(action, profile)
            values[action] = BuildProfileActionCapability(not action_diagnostics, action_diagnostics)
        return BuildProfileActionCapabilities(
            build=values[BuildProfileAction.BUILD],
            run=values[BuildProfileAction.RUN],
            install=values[BuildProfileAction.INSTALL],
            launch=values[BuildProfileAction.LAUNCH],
            dry_run=values[BuildProfileAction.DRY_RUN],
        )

    def _selected_entry(self) -> _DraftEntry:
        if self._selected_id is None:
            raise RuntimeError("no build profile is selected")
        return self._entries[self._entry_index(self._selected_id)]

    def _entry_index(self, entry_id: str) -> int:
        for index, entry in enumerate(self._entries):
            if entry.entry_id == entry_id:
                return index
        raise KeyError(f"unknown build profile entry: {entry_id}")

    def _new_draft_id(self) -> str:
        entry_id = f"draft:{self._next_draft_id}"
        self._next_draft_id += 1
        return entry_id

    @staticmethod
    def _index_templates(
        templates: tuple[BuildProfileTemplate, ...],
    ) -> dict[str, BuildProfileTemplate]:
        indexed: dict[str, BuildProfileTemplate] = {}
        for template in templates:
            if not template.template_id:
                raise ValueError("build profile template id must not be empty")
            if template.template_id in indexed:
                raise ValueError(f"duplicate build profile template id: {template.template_id}")
            indexed[template.template_id] = template
        return indexed


def _capability_diagnostic(action: BuildProfileAction, message: str) -> ProfileDiagnostic:
    return ProfileDiagnostic("profile.action_unavailable", f"actions.{action.value}", message)


__all__ = [
    "BuildProfileAction",
    "BuildProfileActionCapabilities",
    "BuildProfileActionCapability",
    "BuildProfileActionService",
    "BuildProfileEntrySnapshot",
    "BuildProfileStorePersistence",
    "BuildProfileTemplate",
    "BuildProfilesController",
    "BuildProfilesPersistence",
    "BuildProfilesSnapshot",
    "BuildProfilesValidationError",
]
