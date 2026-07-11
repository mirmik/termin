"""UI-neutral title and status projection for an editor session."""

from __future__ import annotations

from dataclasses import dataclass

from .signal import Signal


@dataclass(frozen=True, slots=True)
class EditorSessionPresentation:
    project_name: str = "No Project"
    scene_label: str = "No Scene"
    playing: bool = False
    message: str = "Ready"

    @property
    def status_text(self) -> str:
        mode = "Play" if self.playing else "Edit"
        return f"{self.project_name} | {self.scene_label} | {mode} | {self.message}"

    @property
    def window_title(self) -> str:
        playing = " - PLAYING" if self.playing else ""
        return f"Termin Editor - {self.project_name} [{self.scene_label}]{playing}"


class EditorSessionPresentationModel:
    def __init__(self) -> None:
        self.changed = Signal()
        self.snapshot = EditorSessionPresentation()

    def update(
        self,
        *,
        project_name: str | None = None,
        scene_label: str | None = None,
        playing: bool | None = None,
        message: str | None = None,
    ) -> EditorSessionPresentation:
        current = self.snapshot
        self.snapshot = EditorSessionPresentation(
            project_name=current.project_name if project_name is None else project_name,
            scene_label=current.scene_label if scene_label is None else scene_label,
            playing=current.playing if playing is None else playing,
            message=current.message if message is None else message,
        )
        self.changed.emit(self.snapshot)
        return self.snapshot


__all__ = ["EditorSessionPresentation", "EditorSessionPresentationModel"]
