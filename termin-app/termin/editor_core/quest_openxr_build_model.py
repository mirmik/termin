"""Toolkit-neutral Quest/OpenXR build, install and launch orchestration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from queue import Empty, SimpleQueue
import threading
from typing import Callable

from termin.editor_core.signal import Signal


_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QuestOpenXRBuildSnapshot:
    project_name: str
    entry_scene: str
    status: str
    busy: bool
    log_text: str
    last_apk_path: str | None


class QuestOpenXRBuildController:
    def __init__(
        self,
        project_root: str | Path,
        entry_scene: str | Path,
        output_dir: str | Path | None = None,
        *,
        on_log: Callable[[str], None] | None = None,
        defer: Callable[[Callable[[], None]], None] | None = None,
        start_worker: Callable[[str, Callable[[], None]], None] | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.entry_scene = Path(entry_scene)
        self.output_dir = Path(output_dir).resolve() if output_dir is not None else None
        self._on_log = on_log
        self._pending: SimpleQueue[Callable[[], None]] = SimpleQueue()
        self._defer = defer or self._pending.put
        self._start_worker = start_worker or self._start_thread
        self._status = "Idle"
        self._busy = False
        self._lines = ["Ready.", "Connect and wake the Quest before Install or Launch."]
        self._last_apk_path: Path | None = None
        self._last_application_id: str | None = None
        self.changed = Signal()

    @property
    def snapshot(self) -> QuestOpenXRBuildSnapshot:
        return QuestOpenXRBuildSnapshot(
            project_name=self.project_root.name,
            entry_scene=self.entry_scene.as_posix(),
            status=self._status,
            busy=self._busy,
            log_text="\n".join(self._lines),
            last_apk_path=None if self._last_apk_path is None else str(self._last_apk_path),
        )

    def process_pending(self) -> int:
        processed = 0
        while True:
            try:
                callback = self._pending.get_nowait()
            except Empty:
                break
            callback()
            processed += 1
        return processed

    def build_only(self) -> bool:
        return self._run_async("Build", self._build)

    def install_only(self) -> bool:
        return self._run_async("Install", self._install)

    def launch_only(self) -> bool:
        return self._run_async("Launch", self._launch)

    def build_install(self) -> bool:
        return self._run_async("Build + Install", lambda: (self._build(), self._install()))

    def build_install_launch(self) -> bool:
        return self._run_async(
            "Build + Install + Launch",
            lambda: (self._build(), self._install(), self._launch()),
        )

    def _run_async(self, label: str, action: Callable[[], object]) -> bool:
        if self._busy:
            self._append_log("Another Quest/OpenXR action is already running.")
            return False
        self._busy = True
        self._status = f"{label}..."
        self._publish()

        def worker() -> None:
            try:
                action()
            except Exception as error:
                _logger.exception("Quest/OpenXR %s failed", label)
                message = str(error)
                self._defer(lambda: self._finish_failed(label, message))
                return
            self._defer(self._finish_complete)

        self._start_worker(label, worker)
        return True

    def _build(self) -> Path:
        self._post_log(f"Build started: {self.entry_scene}")
        from termin.project_build import build_quest_openxr_project

        try:
            result = build_quest_openxr_project(
                project_root=self.project_root,
                entry_scene=self.entry_scene,
                output_dir=self.output_dir,
                log_callback=self._post_log,
            )
        except Exception as error:
            raise RuntimeError(f"Build failed: {error}") from error
        self._last_apk_path = Path(result.apk_path)
        self._last_application_id = result.application_id
        self._defer(lambda: self._report_build(result))
        return self._last_apk_path

    def _install(self) -> None:
        apk_path = self._resolve_apk_path()
        self._post_log(f"Install: {apk_path}")
        from termin.project_build import install_quest_openxr_apk

        try:
            result = install_quest_openxr_apk(
                apk_path,
                log_path=self._deploy_log_path(),
                log_callback=self._post_log,
            )
        except Exception as error:
            raise RuntimeError(f"Install failed: {error}") from error
        self._defer(lambda: self._report_install(result))

    def _launch(self) -> None:
        application_id = self._resolve_application_id()
        self._post_log(f"Launch: {application_id}")
        from termin.project_build import launch_quest_openxr_app

        try:
            launch_quest_openxr_app(
                application_id,
                log_path=self._deploy_log_path(),
                log_callback=self._post_log,
            )
        except Exception as error:
            raise RuntimeError(f"Launch failed: {error}") from error
        self._defer(self._report_launch)

    def _resolve_application_id(self) -> str:
        if self._last_application_id is not None:
            return self._last_application_id
        from termin.project.settings import load_project_settings

        return load_project_settings(self.project_root).application.application_id

    def _resolve_apk_path(self) -> Path:
        if self._last_apk_path is not None:
            return self._last_apk_path
        from termin.project_build import default_quest_openxr_apk_path

        return Path(default_quest_openxr_apk_path(self.project_root, self.output_dir))

    def _deploy_log_path(self) -> Path:
        from termin.project_build import default_quest_openxr_log_path

        return Path(default_quest_openxr_log_path(self.project_root, self.output_dir))

    def _post_log(self, message: str) -> None:
        self._defer(lambda: self._append_log(message))

    def _append_log(self, message: str) -> None:
        self._lines.append(str(message))
        if self._on_log is not None:
            self._on_log(str(message))
        self._publish()

    def _report_build(self, result) -> None:
        self._status = "Build complete"
        self._append_log(f"APK: {result.apk_path}")
        self._append_log(
            f"Identity: {result.application_id}/{result.launch_activity}; "
            f"{result.application_label} {result.version_name} ({result.version_code})"
        )
        self._append_log(f"Package: {result.package_result.package_dir}")
        self._append_log(f"Build log: {result.log_path}")
        for diagnostic in result.diagnostics:
            self._append_log(
                f"Build {diagnostic.level}: {diagnostic.path}: {diagnostic.message}"
            )

    def _report_install(self, result) -> None:
        self._status = "Install complete"
        if result.log_path is not None:
            self._append_log(f"Deploy log: {result.log_path}")
        else:
            self._publish()

    def _report_launch(self) -> None:
        self._status = "Launch complete"
        self._append_log("Launch command sent.")

    def _finish_failed(self, label: str, message: str) -> None:
        self._status = f"{label} failed"
        self._busy = False
        self._append_log(f"{label} failed: {message}")

    def _finish_complete(self) -> None:
        self._busy = False
        self._publish()

    def _publish(self) -> None:
        self.changed.emit(self.snapshot)

    @staticmethod
    def _start_thread(label: str, worker: Callable[[], None]) -> None:
        threading.Thread(
            target=worker,
            name=f"QuestOpenXR-{label}",
            daemon=True,
        ).start()


__all__ = ["QuestOpenXRBuildController", "QuestOpenXRBuildSnapshot"]
