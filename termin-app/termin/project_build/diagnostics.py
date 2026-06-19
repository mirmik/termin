"""Shared diagnostics for project build orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class DiagnosticLike(Protocol):
    level: str
    path: str
    message: str


@dataclass
class BuildDiagnostic:
    level: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "level": self.level,
            "path": self.path,
            "message": self.message,
        }

    @classmethod
    def from_diagnostic(cls, diagnostic: DiagnosticLike) -> "BuildDiagnostic":
        return cls(
            level=diagnostic.level,
            path=diagnostic.path,
            message=diagnostic.message,
        )


def build_error(path: str, message: str) -> BuildDiagnostic:
    return BuildDiagnostic("error", path, message)


def build_warning(path: str, message: str) -> BuildDiagnostic:
    return BuildDiagnostic("warning", path, message)


def format_diagnostics(title: str, diagnostics: list[DiagnosticLike]) -> str:
    lines = [title]
    for diagnostic in diagnostics:
        lines.append(f"- {diagnostic.level}: {diagnostic.path}: {diagnostic.message}")
    return "\n".join(lines)
