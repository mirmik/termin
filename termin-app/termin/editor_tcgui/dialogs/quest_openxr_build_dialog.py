"""Quest/OpenXR build and deploy dialog."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from tcbase import log
from tcgui.widgets.button import Button
from tcgui.widgets.dialog import Dialog
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.text_area import TextArea
from tcgui.widgets.units import px
from tcgui.widgets.vstack import VStack


def show_quest_openxr_build_dialog(
    ui,
    project_root: str | Path,
    entry_scene: str | Path,
    output_dir: str | Path | None = None,
    on_log: Callable[[str], None] | None = None,
) -> None:
    """Show Quest/OpenXR build dialog for the current project scene."""
    project_root_path = Path(project_root).resolve()
    entry_scene_path = Path(entry_scene)
    output_dir_path = Path(output_dir).resolve() if output_dir is not None else None

    last_apk_path: Path | None = None
    busy = False
    action_buttons: list[Button] = []

    content = VStack()
    content.spacing = 8
    content.preferred_width = px(760)
    content.preferred_height = px(430)

    title = Label()
    title.text = f"Project: {project_root_path.name}"
    content.add_child(title)

    scene_label = Label()
    scene_label.text = f"Entry scene: {entry_scene_path}"
    content.add_child(scene_label)

    status_label = Label()
    status_label.text = "Idle"
    content.add_child(status_label)

    actions = HStack()
    actions.spacing = 8
    content.add_child(actions)

    log_view = TextArea()
    log_view.read_only = True
    log_view.word_wrap = False
    log_view.preferred_height = px(300)
    log_view.stretch = True
    content.add_child(log_view)

    def request_layout() -> None:
        if status_label._ui is not None:
            status_label._ui.request_layout()

    def append_log(message: str) -> None:
        current = log_view.text
        log_view.text = message if current == "" else current + "\n" + message
        if on_log is not None:
            on_log(message)
        request_layout()

    def set_status(message: str) -> None:
        status_label.text = message
        request_layout()

    def set_busy(value: bool) -> None:
        nonlocal busy
        busy = value
        for button in action_buttons:
            button.enabled = not value
        request_layout()

    def defer(callback: Callable[[], None]) -> None:
        ui.defer(callback)

    def run_async(label: str, action: Callable[[], None]) -> None:
        if busy:
            append_log("Another Quest/OpenXR action is already running.")
            return

        set_busy(True)
        set_status(f"{label}...")

        def worker() -> None:
            try:
                action()
            except Exception as e:
                error_message = str(e)
                log.error(f"[QuestOpenXRBuildDialog] {label} failed: {error_message}", exc_info=True)

                def report_failure() -> None:
                    set_status(f"{label} failed")
                    append_log(f"{label} failed: {error_message}")
                    set_busy(False)

                defer(report_failure)
                return

            def report_complete() -> None:
                set_busy(False)

            defer(report_complete)

        thread = threading.Thread(target=worker, name=f"QuestOpenXR-{label}", daemon=True)
        thread.start()

    def resolve_apk_path() -> Path:
        if last_apk_path is not None:
            return last_apk_path
        from termin.project_build import default_quest_openxr_apk_path
        return default_quest_openxr_apk_path(project_root_path, output_dir_path)

    def deploy_log_path() -> Path:
        from termin.project_build import default_quest_openxr_log_path
        return default_quest_openxr_log_path(project_root_path, output_dir_path)

    def run_build() -> Path | None:
        nonlocal last_apk_path
        defer(lambda: append_log(f"Build started: {entry_scene_path}"))
        try:
            from termin.project_build import build_quest_openxr_project

            result = build_quest_openxr_project(
                project_root=project_root_path,
                entry_scene=entry_scene_path,
                output_dir=output_dir_path,
                log_callback=lambda line: defer(lambda line=line: append_log(line)),
            )
        except Exception as e:
            raise RuntimeError(f"Build failed: {e}") from e

        last_apk_path = result.apk_path

        def report() -> None:
            set_status("Build complete")
            append_log(f"APK: {result.apk_path}")
            append_log(f"Package: {result.package_result.package_dir}")
            append_log(f"Build log: {result.log_path}")
            for diagnostic in result.diagnostics:
                append_log(f"Build {diagnostic.level}: {diagnostic.path}: {diagnostic.message}")

        defer(report)
        return result.apk_path

    def run_install() -> bool:
        apk_path = resolve_apk_path()
        defer(lambda: append_log(f"Install: {apk_path}"))
        try:
            from termin.project_build import install_quest_openxr_apk

            result = install_quest_openxr_apk(
                apk_path,
                log_path=deploy_log_path(),
                log_callback=lambda line: defer(lambda line=line: append_log(line)),
            )
        except Exception as e:
            raise RuntimeError(f"Install failed: {e}") from e

        def report() -> None:
            set_status("Install complete")
            if result.log_path is not None:
                append_log(f"Deploy log: {result.log_path}")

        defer(report)
        return True

    def run_launch() -> bool:
        defer(lambda: append_log("Launch: org.termin.openxr"))
        try:
            from termin.project_build import launch_quest_openxr_app

            launch_quest_openxr_app(
                log_path=deploy_log_path(),
                log_callback=lambda line: defer(lambda line=line: append_log(line)),
            )
        except Exception as e:
            raise RuntimeError(f"Launch failed: {e}") from e

        def report() -> None:
            set_status("Launch complete")
            append_log("Launch command sent.")

        defer(report)
        return True

    def build_only() -> None:
        run_async("Build", lambda: run_build())

    def install_only() -> None:
        run_async("Install", lambda: run_install())

    def launch_only() -> None:
        run_async("Launch", lambda: run_launch())

    def build_install() -> None:
        def action() -> None:
            if run_build() is None:
                return
            run_install()

        run_async("Build + Install", action)

    def build_install_launch() -> None:
        def action() -> None:
            if run_build() is None:
                return
            if not run_install():
                return
            run_launch()

        run_async("Build + Install + Launch", action)

    for text, callback in [
        ("Build APK", build_only),
        ("Install", install_only),
        ("Launch", launch_only),
        ("Build + Install", build_install),
        ("Build + Install + Launch", build_install_launch),
    ]:
        button = Button()
        button.text = text
        button.on_click = callback
        action_buttons.append(button)
        actions.add_child(button)

    dlg = Dialog()
    dlg.title = "Quest/OpenXR Build"
    dlg.content = content
    dlg.buttons = ["Close"]
    dlg.default_button = "Close"
    dlg.cancel_button = "Close"
    dlg.min_width = 800

    append_log("Ready.")
    append_log("Connect and wake the Quest before Install or Launch.")
    dlg.show(ui, windowed=True)
