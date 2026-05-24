"""Qt Quest/OpenXR build and deploy dialog."""

from __future__ import annotations

import threading
from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)
from tcbase import log


class QuestOpenXRBuildDialog(QDialog):
    _append_log_signal = pyqtSignal(str)
    _status_signal = pyqtSignal(str)
    _busy_signal = pyqtSignal(bool)

    def __init__(
        self,
        project_root: str | Path,
        entry_scene: str | Path,
        output_dir: str | Path | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._project_root = Path(project_root).resolve()
        self._entry_scene = Path(entry_scene)
        self._output_dir = Path(output_dir).resolve() if output_dir is not None else None
        self._last_apk_path: Path | None = None
        self._busy = False
        self._action_buttons: list[QPushButton] = []

        self._status_label = QLabel("Idle")
        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)

        self.setWindowTitle("Quest/OpenXR Build")
        self.setMinimumSize(780, 480)
        self._init_ui()
        self._append_log_signal.connect(self._append_log)
        self._status_signal.connect(self._set_status)
        self._busy_signal.connect(self._set_busy)
        self._append_log("Ready.")
        self._append_log("Connect and wake the Quest before Install or Launch.")

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Project: {self._project_root.name}"))
        layout.addWidget(QLabel(f"Entry scene: {self._entry_scene}"))
        layout.addWidget(self._status_label)

        buttons = QHBoxLayout()
        for text, callback in [
            ("Build APK", self._build_only),
            ("Install", self._install_only),
            ("Launch", self._launch_only),
            ("Build + Install", self._build_install),
            ("Build + Install + Launch", self._build_install_launch),
        ]:
            button = QPushButton(text)
            button.clicked.connect(callback)
            self._action_buttons.append(button)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        layout.addWidget(self._log_view, stretch=1)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_row.addWidget(close_button)
        layout.addLayout(close_row)

    def _append_log(self, message: str) -> None:
        self._log_view.append(message)

    def _set_status(self, message: str) -> None:
        self._status_label.setText(message)

    def _set_busy(self, value: bool) -> None:
        self._busy = value
        for button in self._action_buttons:
            button.setEnabled(not value)

    def _emit_log(self, message: str) -> None:
        self._append_log_signal.emit(message)

    def _emit_status(self, message: str) -> None:
        self._status_signal.emit(message)

    def _emit_busy(self, value: bool) -> None:
        self._busy_signal.emit(value)

    def _run_async(self, label: str, action) -> None:
        if self._busy:
            self._append_log("Another Quest/OpenXR action is already running.")
            return

        self._set_busy(True)
        self._set_status(f"{label}...")

        def worker() -> None:
            try:
                action()
            except Exception as e:
                error_message = str(e)
                log.error(f"[QuestOpenXRBuildDialog] {label} failed: {error_message}", exc_info=True)
                self._emit_status(f"{label} failed")
                self._emit_log(f"{label} failed: {error_message}")
                self._emit_busy(False)
                return

            self._emit_busy(False)

        thread = threading.Thread(target=worker, name=f"QuestOpenXR-{label}", daemon=True)
        thread.start()

    def _resolve_apk_path(self) -> Path:
        if self._last_apk_path is not None:
            return self._last_apk_path
        from termin.project_build import default_quest_openxr_apk_path
        return default_quest_openxr_apk_path(self._project_root, self._output_dir)

    def _deploy_log_path(self) -> Path:
        from termin.project_build import default_quest_openxr_log_path
        return default_quest_openxr_log_path(self._project_root, self._output_dir)

    def _run_build(self) -> Path | None:
        self._emit_log(f"Build started: {self._entry_scene}")
        try:
            from termin.project_build import build_quest_openxr_project

            result = build_quest_openxr_project(
                project_root=self._project_root,
                entry_scene=self._entry_scene,
                output_dir=self._output_dir,
                log_callback=self._emit_log,
            )
        except Exception as e:
            raise RuntimeError(f"Build failed: {e}") from e

        self._last_apk_path = result.apk_path
        self._emit_status("Build complete")
        self._emit_log(f"APK: {result.apk_path}")
        self._emit_log(f"Package: {result.package_result.package_dir}")
        self._emit_log(f"Build log: {result.log_path}")
        for diagnostic in result.diagnostics:
            self._emit_log(f"Build {diagnostic.level}: {diagnostic.path}: {diagnostic.message}")
        return result.apk_path

    def _run_install(self) -> bool:
        apk_path = self._resolve_apk_path()
        self._emit_log(f"Install: {apk_path}")
        try:
            from termin.project_build import install_quest_openxr_apk

            result = install_quest_openxr_apk(
                apk_path,
                log_path=self._deploy_log_path(),
                log_callback=self._emit_log,
            )
        except Exception as e:
            raise RuntimeError(f"Install failed: {e}") from e

        self._emit_status("Install complete")
        if result.log_path is not None:
            self._emit_log(f"Deploy log: {result.log_path}")
        return True

    def _run_launch(self) -> bool:
        self._emit_log("Launch: org.termin.openxr")
        try:
            from termin.project_build import launch_quest_openxr_app

            results = launch_quest_openxr_app(
                log_path=self._deploy_log_path(),
                log_callback=self._emit_log,
            )
        except Exception as e:
            raise RuntimeError(f"Launch failed: {e}") from e

        self._emit_status("Launch complete")
        self._emit_log("Launch command sent.")
        return True

    def _build_only(self) -> None:
        self._run_async("Build", self._run_build)

    def _install_only(self) -> None:
        self._run_async("Install", self._run_install)

    def _launch_only(self) -> None:
        self._run_async("Launch", self._run_launch)

    def _build_install(self) -> None:
        def action() -> None:
            if self._run_build() is None:
                return
            self._run_install()

        self._run_async("Build + Install", action)

    def _build_install_launch(self) -> None:
        def action() -> None:
            if self._run_build() is None:
                return
            if not self._run_install():
                return
            self._run_launch()

        self._run_async("Build + Install + Launch", action)
