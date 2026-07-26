from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from termin.editor_core.build_profiles_model import (
    BuildProfileAction,
    BuildProfilesController,
)
from termin.editor_native.build_profiles_window import (
    NativeBuildProfilesWindow,
    build_native_build_profiles_window,
    default_build_profile_templates,
)
from termin.editor_native.ui_host import resolve_native_ui_font
from termin.gui_native import (
    DrawList,
    DrawListRenderer,
    PaintContext,
    Rect,
    TcDocument,
    tc_ui_document_create,
    tc_ui_document_destroy,
)
from termin.project_build import BuildProfile, ProfileDiagnostic, QuestOpenXRTarget


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


def _bind_font(document: TcDocument) -> DrawListRenderer:
    renderer = DrawListRenderer()
    assert renderer.set_default_font_path(str(resolve_native_ui_font()), 15)
    renderer.bind_text_measurer(document)
    return renderer


def _fixture() -> tuple[
    TcDocument,
    DrawListRenderer,
    MemoryPersistence,
    ActionService,
    NativeBuildProfilesWindow,
    list[bool],
]:
    document = tc_ui_document_create()
    renderer = _bind_font(document)
    templates = default_build_profile_templates(
        Path("/project"),
        Path("Scenes/Main.scene"),
    )
    quest = replace(
        templates[2].profile,
        target=QuestOpenXRTarget("arm64-v8a", 32),
    )
    profiles = (templates[0].profile, templates[1].profile, quest)
    persistence = MemoryPersistence(profiles)
    actions = ActionService()
    controller = BuildProfilesController(
        persistence,
        templates,
        action_service=actions,
    )
    renders: list[bool] = []
    window = build_native_build_profiles_window(
        document,
        controller,
        viewport=lambda: Rect(0.0, 0.0, 1280.0, 800.0),
        request_render=lambda: renders.append(True),
    )
    return document, renderer, persistence, actions, window, renders


def _release(document: TcDocument, renderer: DrawListRenderer) -> None:
    renderer.release_gpu()
    tc_ui_document_destroy(document)


def test_native_build_profiles_projects_targets_actions_and_bounded_layout() -> None:
    document, renderer, _, _, window, renders = _fixture()
    try:
        assert window.show()
        document.layout_roots(Rect(0.0, 0.0, 1280.0, 800.0))

        assert window.root.stable_id == "editor.build-profiles"
        assert window.profile_model.row_count == 3
        assert window.profile_table.visible_range[1] <= 3
        assert window.desktop_rows[0].visible
        assert not window.mobile_rows[0].visible
        assert window.action_buttons[BuildProfileAction.BUILD].widget.enabled
        assert window.action_buttons[BuildProfileAction.RUN].widget.enabled
        assert not window.action_buttons[BuildProfileAction.INSTALL].widget.enabled

        window.select_index(1)
        assert not window.desktop_rows[0].visible
        assert window.mobile_rows[0].visible
        assert not window.action_buttons[BuildProfileAction.RUN].widget.enabled
        assert window.action_buttons[BuildProfileAction.INSTALL].widget.enabled
        assert window.action_buttons[BuildProfileAction.LAUNCH].widget.enabled

        window.select_index(2)
        assert window.target.selected_text == "Quest/OpenXR"
        assert window.mobile_ndk_api.value == 32
        assert "Quest/OpenXR" in window.deploy_summary.text

        draw_list = DrawList()
        document.paint(PaintContext(draw_list))
        assert 20 < draw_list.command_count < 500
        assert renders
    finally:
        _release(document, renderer)


def test_native_build_profiles_edits_collection_saves_reverts_and_executes() -> None:
    document, renderer, persistence, actions, window, _ = _fixture()
    try:
        window.name.text = "quest-store"
        assert window.controller.snapshot.selected is not None
        assert window.controller.snapshot.selected.profile.name == "quest-store"
        assert window.controller.snapshot.dirty
        assert window.save_button.widget.enabled

        window.duplicate_selected()
        assert window.profile_model.row_count == 4
        assert window.controller.snapshot.selected is not None
        assert window.controller.snapshot.selected.profile.name == "quest-store-copy"
        window.delete_selected()
        assert window.profile_model.row_count == 3

        window.add_profile("android")
        assert window.profile_model.row_count == 4
        assert window.controller.snapshot.selected is not None
        assert window.controller.snapshot.selected.profile.name == "android-2"

        window.save()
        assert len(persistence.saved) == 1
        assert not window.controller.snapshot.dirty
        window.name.text = "draft"
        window.revert()
        assert window.controller.snapshot.selected is not None
        assert window.controller.snapshot.selected.profile.name == "quest-store"

        window.select_index(3)
        window.execute(BuildProfileAction.INSTALL)
        assert actions.executed[-1][0] == BuildProfileAction.INSTALL
        assert actions.executed[-1][1].name == "android-2"
    finally:
        _release(document, renderer)


def test_native_build_profiles_surfaces_validation_and_tool_diagnostics() -> None:
    document, renderer, _, actions, window, _ = _fixture()
    try:
        window.name.text = "android"
        assert not window.save_button.widget.enabled
        assert "unique" in window.diagnostics.text

        window.name.text = "desktop-renamed"
        window.select_index(1)
        unavailable = ProfileDiagnostic(
            "tool.adb_missing",
            "tools.adb",
            "adb is unavailable",
        )
        actions.diagnostics[BuildProfileAction.INSTALL] = (unavailable,)
        window.refresh()
        assert not window.action_buttons[BuildProfileAction.INSTALL].widget.enabled
        assert "adb is unavailable" in window.toolchain_report.text
    finally:
        _release(document, renderer)
