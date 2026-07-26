"""Native Build Profiles window over the toolkit-neutral collection controller."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import logging
import os
from pathlib import Path
from typing import Callable
import weakref

from termin.editor_core.build_profiles_model import (
    BuildProfileAction,
    BuildProfileTemplate,
    BuildProfilesController,
    BuildProfilesSnapshot,
)
from termin.gui_native import (
    DialogAction,
    Rect,
    Size,
    TableColumn,
    TableColumnModel,
    TableColumnPolicy,
    TableModel,
    TableRowData,
    TcDocument,
    WidgetRef,
)
from termin.project_build import (
    AndroidTarget,
    BuildProfile,
    DesktopTarget,
    ProfileContent,
    QuestOpenXRTarget,
)
from termin.project_build.profiles import (
    SUPPORTED_ANDROID_ABIS,
    SUPPORTED_CONFIGURATIONS,
    SUPPORTED_DESKTOP_ARCHITECTURES,
    SUPPORTED_DESKTOP_BACKENDS,
    SUPPORTED_DESKTOP_OSES,
    SUPPORTED_DESKTOP_PYTHON_POLICIES,
    SUPPORTED_RESOURCE_POLICIES,
)

from .metrics import EDITOR_UI_METRICS


_logger = logging.getLogger(__name__)
_TARGET_KINDS = ("desktop", "android", "quest_openxr")
_TARGET_LABELS = ("Desktop", "Android", "Quest/OpenXR")
_ACTION_LABELS = {
    BuildProfileAction.BUILD: "Build",
    BuildProfileAction.RUN: "Run",
    BuildProfileAction.INSTALL: "Install",
    BuildProfileAction.LAUNCH: "Launch",
    BuildProfileAction.DRY_RUN: "Dry Run",
}


def _ref(document: TcDocument, reference) -> WidgetRef:
    return reference if isinstance(reference, WidgetRef) else document.ref(reference.handle)


def _stable(reference, stable_id: str) -> None:
    widget = reference if isinstance(reference, WidgetRef) else reference.widget
    widget.stable_id = stable_id


def _lines(text: str) -> tuple[str, ...]:
    return tuple(line.strip() for line in text.splitlines() if line.strip())


def _paths(text: str) -> tuple[Path, ...]:
    return tuple(Path(line) for line in _lines(text))


def _row(
    document: TcDocument,
    stable_id: str,
    label: str,
    control,
) -> WidgetRef:
    row = document.create_hstack(stable_id)
    row.stable_id = f"editor.build-profiles.row.{stable_id}"
    row.set_layout_spacing(EDITOR_UI_METRICS.spacing)
    row.add_fixed_child(document.create_label(label), EDITOR_UI_METRICS.form_label)
    row.add_stretch_child(_ref(document, control))
    return row


def _checkbox_row(
    document: TcDocument,
    stable_id: str,
    label: str,
    checkbox,
) -> WidgetRef:
    row = document.create_hstack(stable_id)
    row.stable_id = f"editor.build-profiles.row.{stable_id}"
    row.add_stretch_child(document.create_label(label))
    row.add_fixed_child(_ref(document, checkbox), EDITOR_UI_METRICS.field_row)
    return row


def _page(document: TcDocument, stable_id: str) -> WidgetRef:
    page = document.create_vstack(f"build-profiles-{stable_id}")
    page.stable_id = f"editor.build-profiles.{stable_id}"
    page.set_layout_padding(EDITOR_UI_METRICS.panel_insets)
    page.set_layout_spacing(EDITOR_UI_METRICS.spacing)
    return page


def _combo(document: TcDocument, stable_id: str, values: tuple[str, ...]):
    combo = document.create_combo_box()
    _stable(combo, stable_id)
    for value in values:
        combo.add_item(value)
    return combo


def default_build_profile_templates(
    project_root: Path,
    entry_scene: Path,
) -> tuple[BuildProfileTemplate, ...]:
    """Create portable explicit templates without probing local capabilities."""

    root = project_root.resolve()
    scene = Path(entry_scene)
    content = ProfileContent(
        entry_scene=scene,
        scenes=(scene,),
        modules=(),
        python_requirements=(),
        resource_policy="strict",
        resource_includes=(),
    )
    desktop_os = "windows" if os.name == "nt" else "linux"
    desktop_backend = "d3d11" if desktop_os == "windows" else "vulkan"
    return (
        BuildProfileTemplate(
            "desktop",
            "Desktop",
            BuildProfile(
                "desktop",
                root,
                DesktopTarget(
                    desktop_os,
                    "x86_64",
                    (desktop_backend,),
                ),
                "dev",
                content,
            ),
        ),
        BuildProfileTemplate(
            "android",
            "Android",
            BuildProfile(
                "android",
                root,
                AndroidTarget("arm64-v8a", 29),
                "debug",
                content,
            ),
        ),
        BuildProfileTemplate(
            "quest_openxr",
            "Quest/OpenXR",
            BuildProfile(
                "quest-openxr",
                root,
                QuestOpenXRTarget("arm64-v8a", 29),
                "debug",
                content,
            ),
        ),
    )


@dataclass
class NativeBuildProfilesWindow:
    document: TcDocument
    controller: BuildProfilesController
    dialog: object
    root: WidgetRef
    profile_table: object
    profile_model: TableModel
    editor_tabs: object
    editor_root: WidgetRef
    name: object
    target: object
    configuration: object
    entry_scene: object
    scenes: object
    modules: object
    python_requirements: object
    resource_policy: object
    resource_includes: object
    desktop_os: object
    desktop_arch: object
    desktop_python_policy: object
    desktop_rows: tuple[WidgetRef, ...]
    backend_checks: dict[str, object]
    mobile_abi: object
    mobile_ndk_api: object
    mobile_rows: tuple[WidgetRef, ...]
    shader_summary: object
    toolchain_report: object
    deploy_summary: object
    output_dir: object
    output_summary: object
    diagnostics: object
    status: object
    add_buttons: dict[str, object]
    duplicate_button: object
    delete_button: object
    action_buttons: dict[BuildProfileAction, object]
    save_button: object
    revert_button: object
    viewport: Callable[[], Rect]
    request_render: Callable[[], None]
    on_snapshot: Callable[[BuildProfilesSnapshot], None]
    _output_lines: list[str] = field(default_factory=list)
    _updating: bool = False
    _closed: bool = False

    def show(self) -> bool:
        if self._closed:
            raise RuntimeError("native Build Profiles window is closed")
        if self.dialog.open:
            return False
        self.refresh()
        shown = self.dialog.show(self.viewport())
        if shown:
            self.request_render()
        return shown

    def refresh(self, snapshot: BuildProfilesSnapshot | None = None) -> None:
        self.apply_snapshot(snapshot or self.controller.snapshot)

    def apply_snapshot(self, snapshot: BuildProfilesSnapshot) -> None:
        self._updating = True
        try:
            rows = []
            selected_index = -1
            for index, entry in enumerate(snapshot.entries):
                profile = entry.profile
                target = profile.target
                if isinstance(target, DesktopTarget):
                    platform = f"{target.os}/{target.arch}"
                    runtime = ", ".join(target.backends)
                else:
                    platform = f"{target.abi}/android-{target.ndk_api}"
                    runtime = "vulkan"
                rows.append(
                    TableRowData(
                        entry.entry_id,
                        [
                            profile.name,
                            profile.target_kind,
                            platform,
                            profile.configuration,
                            runtime,
                            "Invalid" if entry.diagnostics else "Ready",
                        ],
                    )
                )
                if entry.selected:
                    selected_index = index
            self.profile_model.set_rows(rows)
            if selected_index >= 0:
                self.profile_table.select(selected_index)
            else:
                self.profile_table.clear_selection()

            selected = snapshot.selected
            self.editor_root.enabled = selected is not None
            self.duplicate_button.widget.enabled = selected is not None
            self.delete_button.widget.enabled = selected is not None
            if selected is None:
                self._clear_editor()
            else:
                self._apply_profile(selected.profile)
            self._apply_capabilities(snapshot)
            self._apply_diagnostics(snapshot)
            self.save_button.widget.enabled = snapshot.can_save
            self.revert_button.widget.enabled = snapshot.can_revert
            dirty = "Unsaved changes" if snapshot.dirty else "Saved"
            self.status.text = f"{len(snapshot.entries)} profile(s) | {dirty}"
        finally:
            self._updating = False
        self.on_snapshot(snapshot)
        self.request_render()

    def append_output(self, message: str) -> None:
        self._output_lines.append(str(message))
        del self._output_lines[:-200]
        selected = self.controller.snapshot.selected
        summary = (
            "Select a profile."
            if selected is None
            else self._profile_summary(selected.profile)
        )
        self.output_summary.text = summary + "\n\nAction output:\n" + "\n".join(
            self._output_lines
        )
        self.request_render()

    def select_index(self, index: int) -> None:
        if self._updating or not 0 <= index < len(self.controller.snapshot.entries):
            return
        entry = self.controller.snapshot.entries[index]
        self.apply_snapshot(self.controller.select(entry.entry_id))

    def add_profile(self, template_id: str, name: str | None = None) -> None:
        template = next(
            (
                candidate
                for candidate in self.controller.templates
                if candidate.template_id == template_id
            ),
            None,
        )
        if template is None:
            raise KeyError(f"unknown build profile template: {template_id}")
        base = name or template.profile.name or template.template_id
        self.apply_snapshot(
            self.controller.add_from_template(template_id, self._unique_name(base))
        )

    def duplicate_selected(self) -> None:
        selected = self.controller.snapshot.selected
        if selected is None:
            return
        self.apply_snapshot(
            self.controller.duplicate_selected(
                self._unique_name(f"{selected.profile.name}-copy")
            )
        )

    def delete_selected(self) -> None:
        if self.controller.snapshot.selected is not None:
            self.apply_snapshot(self.controller.delete_selected())

    def update_from_controls(self) -> None:
        if self._updating:
            return
        selected = self.controller.snapshot.selected
        if selected is None:
            return
        profile = selected.profile
        target_kind = _TARGET_KINDS[max(0, self.target.selected_index)]
        if target_kind == "desktop":
            backends = tuple(
                backend
                for backend in SUPPORTED_DESKTOP_BACKENDS
                if self.backend_checks[backend].checked
            )
            target = DesktopTarget(
                os=self.desktop_os.selected_text,
                arch=self.desktop_arch.selected_text,
                backends=backends,
                python_package_policy=self.desktop_python_policy.selected_text,
            )
        else:
            target_type = AndroidTarget if target_kind == "android" else QuestOpenXRTarget
            target = target_type(
                abi=self.mobile_abi.selected_text,
                ndk_api=int(self.mobile_ndk_api.value),
            )
        content = ProfileContent(
            entry_scene=Path(self.entry_scene.text),
            scenes=_paths(self.scenes.text),
            modules=_lines(self.modules.text),
            python_requirements=_lines(self.python_requirements.text),
            resource_policy=self.resource_policy.selected_text,
            resource_includes=_lines(self.resource_includes.text),
        )
        next_profile = replace(
            profile,
            name=self.name.text,
            target=target,
            configuration=self.configuration.selected_text,
            content=content,
            output_dir=Path(self.output_dir.text) if self.output_dir.text.strip() else None,
        )
        self.apply_snapshot(self.controller.update_selected(next_profile))

    def save(self) -> None:
        self._run_operation("save", self.controller.save)

    def revert(self) -> None:
        self._run_operation("revert", self.controller.revert)

    def execute(self, action: BuildProfileAction) -> None:
        self._run_operation(action.value, lambda: self.controller.execute(action))

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.dialog.open:
            self.dialog.close()
        if self.document.is_alive(self.dialog.handle):
            self.document.destroy_widget_recursive(self.dialog.handle)

    def _run_operation(
        self,
        name: str,
        callback: Callable[[], BuildProfilesSnapshot],
    ) -> None:
        try:
            self.apply_snapshot(callback())
        except Exception as error:
            _logger.exception("Native Build Profiles operation '%s' failed", name)
            self.diagnostics.text = f"{name} failed: {error}"
            self.status.text = f"{name} failed"
            self.request_render()

    def _unique_name(self, base: str) -> str:
        names = {entry.profile.name for entry in self.controller.snapshot.entries}
        if base not in names:
            return base
        suffix = 2
        while f"{base}-{suffix}" in names:
            suffix += 1
        return f"{base}-{suffix}"

    def _apply_profile(self, profile: BuildProfile) -> None:
        self.name.text = profile.name
        self.target.selected_index = _TARGET_KINDS.index(profile.target_kind)
        self.configuration.selected_index = SUPPORTED_CONFIGURATIONS.index(
            profile.configuration
        )
        self.entry_scene.text = profile.content.entry_scene.as_posix()
        self.scenes.text = "\n".join(path.as_posix() for path in profile.content.scenes)
        self.modules.text = "\n".join(profile.content.modules)
        self.python_requirements.text = "\n".join(profile.content.python_requirements)
        self.resource_policy.selected_index = SUPPORTED_RESOURCE_POLICIES.index(
            profile.content.resource_policy
        )
        self.resource_includes.text = "\n".join(profile.content.resource_includes)
        self.output_dir.text = "" if profile.output_dir is None else profile.output_dir.as_posix()

        desktop = isinstance(profile.target, DesktopTarget)
        for row in self.desktop_rows:
            row.visible = desktop
        for row in self.mobile_rows:
            row.visible = not desktop
        if desktop:
            self.desktop_os.selected_index = SUPPORTED_DESKTOP_OSES.index(profile.target.os)
            self.desktop_arch.selected_index = SUPPORTED_DESKTOP_ARCHITECTURES.index(
                profile.target.arch
            )
            self.desktop_python_policy.selected_index = (
                SUPPORTED_DESKTOP_PYTHON_POLICIES.index(
                    profile.target.python_package_policy
                )
            )
            for backend, checkbox in self.backend_checks.items():
                checkbox.checked = backend in profile.target.backends
            shader_backends = ", ".join(profile.target.backends) or "<none>"
            self.shader_summary.text = (
                f"Slang artifacts follow the ordered runtime backend list: {shader_backends}"
            )
        else:
            self.mobile_abi.selected_index = SUPPORTED_ANDROID_ABIS.index(profile.target.abi)
            self.mobile_ndk_api.value = profile.target.ndk_api
            for checkbox in self.backend_checks.values():
                checkbox.checked = False
            self.shader_summary.text = (
                "Android-family profiles use the canonical Vulkan artifact path."
            )
        self.output_summary.text = self._profile_summary(profile)
        if self._output_lines:
            self.output_summary.text += "\n\nAction output:\n" + "\n".join(
                self._output_lines
            )

    def _clear_editor(self) -> None:
        self.name.text = ""
        self.entry_scene.text = ""
        self.scenes.text = ""
        self.modules.text = ""
        self.python_requirements.text = ""
        self.resource_includes.text = ""
        self.output_dir.text = ""
        self.shader_summary.text = "Select a profile."
        self.toolchain_report.text = "Select a profile."
        self.deploy_summary.text = "Select a profile."
        self.output_summary.text = "Select a profile."

    def _apply_capabilities(self, snapshot: BuildProfilesSnapshot) -> None:
        capability_lines = []
        for action, button in self.action_buttons.items():
            capability = snapshot.capabilities.for_action(action)
            button.widget.enabled = capability.enabled
            if capability.diagnostics:
                capability_lines.extend(
                    f"{_ACTION_LABELS[action]}: {diagnostic.format()}"
                    for diagnostic in capability.diagnostics
                )
        report = "\n".join(dict.fromkeys(capability_lines))
        self.toolchain_report.text = report or "Local toolchain capabilities are ready."
        selected = snapshot.selected
        if selected is None:
            self.deploy_summary.text = "Select a profile."
        elif selected.profile.target_kind == "desktop":
            self.deploy_summary.text = "Desktop profiles support Build, Run and Dry Run."
        else:
            self.deploy_summary.text = (
                f"{_TARGET_LABELS[_TARGET_KINDS.index(selected.profile.target_kind)]} "
                "profiles support Build, Install, Launch and Dry Run when local tools are ready."
            )

    def _apply_diagnostics(self, snapshot: BuildProfilesSnapshot) -> None:
        selected = snapshot.selected
        if selected is None:
            self.diagnostics.text = "No profile selected."
            return
        if selected.diagnostics:
            self.diagnostics.text = "\n".join(
                diagnostic.format() for diagnostic in selected.diagnostics
            )
        else:
            self.diagnostics.text = "Profile schema is valid."

    @staticmethod
    def _profile_summary(profile: BuildProfile) -> str:
        output = profile.output_dir or Path("dist") / profile.name
        return "\n".join(
            (
                f"Profile: {profile.name}",
                f"Target: {profile.target_kind}",
                f"Configuration: {profile.configuration}",
                f"Entry scene: {profile.content.entry_scene.as_posix()}",
                f"Output: {output.as_posix()}",
            )
        )


def build_native_build_profiles_window(
    document: TcDocument,
    controller: BuildProfilesController,
    *,
    viewport: Callable[[], Rect],
    request_render: Callable[[], None],
    on_snapshot: Callable[[BuildProfilesSnapshot], None] | None = None,
) -> NativeBuildProfilesWindow:
    root = document.create_vstack("native-build-profiles")
    root.stable_id = "editor.build-profiles"
    root.preferred_size = Size(1120.0, 680.0)
    root.set_layout_padding(EDITOR_UI_METRICS.dialog_insets)
    root.set_layout_spacing(EDITOR_UI_METRICS.dialog_spacing)

    main = document.create_hstack("build-profiles-main")
    main.stable_id = "editor.build-profiles.main"
    main.set_layout_spacing(EDITOR_UI_METRICS.dialog_spacing)

    profile_panel = document.create_vstack("build-profiles-list")
    profile_panel.stable_id = "editor.build-profiles.list"
    profile_panel.set_layout_spacing(EDITOR_UI_METRICS.spacing)
    profile_model = TableModel()
    profile_columns = TableColumnModel()
    profile_columns.set_columns(
        [
            TableColumn("name", "Name", TableColumnPolicy.Stretch, min_width=100.0),
            TableColumn("target", "Target", TableColumnPolicy.Fixed, width=92.0),
            TableColumn("platform", "Platform", TableColumnPolicy.Fixed, width=138.0),
            TableColumn("config", "Config", TableColumnPolicy.Fixed, width=72.0),
            TableColumn("runtime", "Runtime", TableColumnPolicy.Fixed, width=110.0),
            TableColumn("status", "Status", TableColumnPolicy.Fixed, width=64.0),
        ]
    )
    profile_table = document.create_table_widget(profile_model, profile_columns)
    _stable(profile_table, "editor.build-profiles.table")
    profile_panel.add_stretch_child(profile_table.widget)

    add_row = document.create_hstack("build-profiles-add")
    add_row.set_layout_spacing(EDITOR_UI_METRICS.spacing)
    add_buttons = {}
    for template in controller.templates:
        button = document.create_button(f"+ {template.label}")
        _stable(button, f"editor.build-profiles.add.{template.template_id}")
        add_row.add_stretch_child(button.widget)
        add_buttons[template.template_id] = button
    profile_panel.add_fixed_child(add_row, EDITOR_UI_METRICS.action_row)

    mutate_row = document.create_hstack("build-profiles-mutate")
    mutate_row.set_layout_spacing(EDITOR_UI_METRICS.spacing)
    duplicate_button = document.create_button("Duplicate")
    delete_button = document.create_button("Delete")
    _stable(duplicate_button, "editor.build-profiles.duplicate")
    _stable(delete_button, "editor.build-profiles.delete")
    mutate_row.add_stretch_child(duplicate_button.widget)
    mutate_row.add_stretch_child(delete_button.widget)
    profile_panel.add_fixed_child(mutate_row, EDITOR_UI_METRICS.action_row)
    main.add_fixed_child(profile_panel, 500.0)

    editor_root = document.create_vstack("build-profiles-editor")
    editor_root.stable_id = "editor.build-profiles.editor"
    editor_root.set_layout_spacing(EDITOR_UI_METRICS.spacing)
    editor_tabs = document.create_tab_view("build-profiles-tabs")
    _stable(editor_tabs, "editor.build-profiles.tabs")

    general = _page(document, "general")
    name = document.create_text_input()
    _stable(name, "editor.build-profiles.name")
    target = _combo(
        document,
        "editor.build-profiles.target",
        _TARGET_LABELS,
    )
    configuration = _combo(
        document,
        "editor.build-profiles.configuration",
        SUPPORTED_CONFIGURATIONS,
    )
    entry_scene = document.create_text_input()
    _stable(entry_scene, "editor.build-profiles.entry-scene")
    scenes = document.create_text_area()
    _stable(scenes, "editor.build-profiles.scenes")
    general.add_fixed_child(_row(document, "name", "Name", name), EDITOR_UI_METRICS.field_row)
    general.add_fixed_child(
        _row(document, "target", "Target", target),
        EDITOR_UI_METRICS.field_row,
    )
    general.add_fixed_child(
        _row(document, "configuration", "Configuration", configuration),
        EDITOR_UI_METRICS.field_row,
    )
    general.add_fixed_child(
        _row(document, "entry-scene", "Entry Scene", entry_scene),
        EDITOR_UI_METRICS.field_row,
    )
    general.add_fixed_child(
        document.create_label("Packaged Scenes (one per line)"),
        EDITOR_UI_METRICS.section_row,
    )
    general.add_stretch_child(scenes.widget)
    editor_tabs.add_page("General", general)

    runtime = _page(document, "runtime")
    modules = document.create_text_area()
    python_requirements = document.create_text_area()
    resource_includes = document.create_text_area()
    _stable(modules, "editor.build-profiles.modules")
    _stable(python_requirements, "editor.build-profiles.python-requirements")
    _stable(resource_includes, "editor.build-profiles.resource-includes")
    resource_policy = _combo(
        document,
        "editor.build-profiles.resource-policy",
        SUPPORTED_RESOURCE_POLICIES,
    )
    runtime.add_fixed_child(
        _row(document, "resource-policy", "Resource Policy", resource_policy),
        EDITOR_UI_METRICS.field_row,
    )
    for label, control in (
        ("Modules", modules),
        ("Python Requirements", python_requirements),
        ("Dynamic Resource Includes", resource_includes),
    ):
        runtime.add_fixed_child(
            document.create_label(f"{label} (one per line)"),
            EDITOR_UI_METRICS.section_row,
        )
        runtime.add_stretch_child(control.widget)
    editor_tabs.add_page("Runtime", runtime)

    shaders = _page(document, "shaders")
    backend_checks = {}
    for backend in SUPPORTED_DESKTOP_BACKENDS:
        checkbox = document.create_checkbox(False)
        _stable(checkbox, f"editor.build-profiles.backend.{backend}")
        backend_checks[backend] = checkbox
        shaders.add_fixed_child(
            _checkbox_row(document, f"backend-{backend}", backend.upper(), checkbox),
            EDITOR_UI_METRICS.field_row,
        )
    shader_summary = document.create_text_area()
    shader_summary.widget.enabled = False
    _stable(shader_summary, "editor.build-profiles.shader-summary")
    shaders.add_stretch_child(shader_summary.widget)
    editor_tabs.add_page("Shaders", shaders)

    toolchain = _page(document, "toolchain")
    desktop_os = _combo(
        document,
        "editor.build-profiles.desktop-os",
        SUPPORTED_DESKTOP_OSES,
    )
    desktop_arch = _combo(
        document,
        "editor.build-profiles.desktop-arch",
        SUPPORTED_DESKTOP_ARCHITECTURES,
    )
    desktop_python_policy = _combo(
        document,
        "editor.build-profiles.python-policy",
        SUPPORTED_DESKTOP_PYTHON_POLICIES,
    )
    desktop_rows = (
        _row(document, "desktop-os", "Desktop OS", desktop_os),
        _row(document, "desktop-arch", "Architecture", desktop_arch),
        _row(document, "python-policy", "Python Policy", desktop_python_policy),
    )
    mobile_abi = _combo(
        document,
        "editor.build-profiles.mobile-abi",
        SUPPORTED_ANDROID_ABIS,
    )
    mobile_ndk_api = document.create_spin_box(29.0)
    mobile_ndk_api.set_range(21.0, 100.0)
    mobile_ndk_api.step = 1.0
    mobile_ndk_api.decimals = 0
    _stable(mobile_ndk_api, "editor.build-profiles.ndk-api")
    mobile_rows = (
        _row(document, "mobile-abi", "Android ABI", mobile_abi),
        _row(document, "ndk-api", "NDK API", mobile_ndk_api),
    )
    for row in (*desktop_rows, *mobile_rows):
        toolchain.add_fixed_child(row, EDITOR_UI_METRICS.field_row)
    toolchain_report = document.create_text_area()
    toolchain_report.widget.enabled = False
    _stable(toolchain_report, "editor.build-profiles.toolchain-report")
    toolchain.add_stretch_child(toolchain_report.widget)
    editor_tabs.add_page("Toolchain", toolchain)

    deploy = _page(document, "deploy")
    deploy_summary = document.create_text_area()
    deploy_summary.widget.enabled = False
    _stable(deploy_summary, "editor.build-profiles.deploy-summary")
    deploy.add_stretch_child(deploy_summary.widget)
    editor_tabs.add_page("Deploy", deploy)

    output = _page(document, "output")
    output_dir = document.create_text_input()
    _stable(output_dir, "editor.build-profiles.output-dir")
    output.add_fixed_child(
        _row(document, "output-dir", "Output Directory", output_dir),
        EDITOR_UI_METRICS.field_row,
    )
    output_summary = document.create_text_area()
    output_summary.widget.enabled = False
    _stable(output_summary, "editor.build-profiles.output-summary")
    output.add_stretch_child(output_summary.widget)
    editor_tabs.add_page("Output", output)

    editor_root.add_stretch_child(editor_tabs.widget)
    diagnostics = document.create_text_area()
    diagnostics.widget.enabled = False
    _stable(diagnostics, "editor.build-profiles.diagnostics")
    editor_root.add_fixed_child(diagnostics.widget, 96.0)
    main.add_stretch_child(editor_root)
    root.add_stretch_child(main)

    action_row = document.create_hstack("build-profiles-actions")
    action_row.stable_id = "editor.build-profiles.actions"
    action_row.set_layout_spacing(EDITOR_UI_METRICS.spacing)
    action_buttons = {}
    for action in BuildProfileAction:
        button = document.create_button(_ACTION_LABELS[action])
        _stable(button, f"editor.build-profiles.action.{action.value}")
        action_row.add_stretch_child(button.widget)
        action_buttons[action] = button
    save_button = document.create_button("Save")
    revert_button = document.create_button("Revert")
    _stable(save_button, "editor.build-profiles.save")
    _stable(revert_button, "editor.build-profiles.revert")
    action_row.add_stretch_child(save_button.widget)
    action_row.add_stretch_child(revert_button.widget)
    root.add_fixed_child(action_row, EDITOR_UI_METRICS.action_row)

    status = document.create_status_bar("Build profiles")
    _stable(status, "editor.build-profiles.status")
    root.add_fixed_child(status.widget, EDITOR_UI_METRICS.status_row)

    dialog = document.create_dialog("Build Profiles")
    dialog.actions = [DialogAction("close", "Close", is_default=True, is_cancel=True)]
    dialog.set_content(root)
    window = NativeBuildProfilesWindow(
        document=document,
        controller=controller,
        dialog=dialog,
        root=root,
        profile_table=profile_table,
        profile_model=profile_model,
        editor_tabs=editor_tabs,
        editor_root=editor_root,
        name=name,
        target=target,
        configuration=configuration,
        entry_scene=entry_scene,
        scenes=scenes,
        modules=modules,
        python_requirements=python_requirements,
        resource_policy=resource_policy,
        resource_includes=resource_includes,
        desktop_os=desktop_os,
        desktop_arch=desktop_arch,
        desktop_python_policy=desktop_python_policy,
        desktop_rows=desktop_rows,
        backend_checks=backend_checks,
        mobile_abi=mobile_abi,
        mobile_ndk_api=mobile_ndk_api,
        mobile_rows=mobile_rows,
        shader_summary=shader_summary,
        toolchain_report=toolchain_report,
        deploy_summary=deploy_summary,
        output_dir=output_dir,
        output_summary=output_summary,
        diagnostics=diagnostics,
        status=status,
        add_buttons=add_buttons,
        duplicate_button=duplicate_button,
        delete_button=delete_button,
        action_buttons=action_buttons,
        save_button=save_button,
        revert_button=revert_button,
        viewport=viewport,
        request_render=request_render,
        on_snapshot=on_snapshot or (lambda _snapshot: None),
    )
    weak_window = weakref.ref(window)

    def owner() -> NativeBuildProfilesWindow | None:
        return weak_window()

    profile_table.connect_selection_changed(
        lambda indices: (
            owner().select_index(indices[0])
            if owner() is not None and indices
            else None
        )
    )
    for template_id, button in add_buttons.items():
        button.connect_clicked(
            lambda template_id=template_id: (
                owner().add_profile(template_id) if owner() is not None else None
            )
        )
    duplicate_button.connect_clicked(
        lambda: owner().duplicate_selected() if owner() is not None else None
    )
    delete_button.connect_clicked(
        lambda: owner().delete_selected() if owner() is not None else None
    )

    for control in (
        name,
        entry_scene,
        scenes,
        modules,
        python_requirements,
        resource_includes,
        output_dir,
    ):
        control.connect_changed(
            lambda _value: owner().update_from_controls() if owner() is not None else None
        )
    for combo in (
        target,
        configuration,
        resource_policy,
        desktop_os,
        desktop_arch,
        desktop_python_policy,
        mobile_abi,
    ):
        combo.connect_changed(
            lambda _index, _text: (
                owner().update_from_controls() if owner() is not None else None
            )
        )
    mobile_ndk_api.connect_changed(
        lambda _value: owner().update_from_controls() if owner() is not None else None
    )
    for checkbox in backend_checks.values():
        checkbox.connect_changed(
            lambda _checked: owner().update_from_controls() if owner() is not None else None
        )
    for action, button in action_buttons.items():
        button.connect_clicked(
            lambda action=action: (
                owner().execute(action) if owner() is not None else None
            )
        )
    save_button.connect_clicked(lambda: owner().save() if owner() is not None else None)
    revert_button.connect_clicked(
        lambda: owner().revert() if owner() is not None else None
    )
    window.refresh()
    return window


def connect_build_profiles_command(menu_bar, command_id: int, window) -> None:
    weak_window = weakref.ref(window)

    def activated(_menu_index: int, activated_id: int, _command) -> None:
        owner = weak_window()
        if activated_id == command_id and owner is not None:
            owner.show()

    menu_bar.connect_activated(activated)


__all__ = [
    "NativeBuildProfilesWindow",
    "build_native_build_profiles_window",
    "connect_build_profiles_command",
    "default_build_profile_templates",
]
