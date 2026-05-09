"""Project build manifest generation."""

from termin.project_builder.builder import build_project
from termin.project_builder.manifest import (
    BuildDescription,
    BuildDiagnostic,
    BuildProjectResult,
    BuildResource,
    ProjectBuildManifest,
)

__all__ = [
    "BuildDescription",
    "BuildDiagnostic",
    "BuildProjectResult",
    "BuildResource",
    "ProjectBuildManifest",
    "build_project",
]
