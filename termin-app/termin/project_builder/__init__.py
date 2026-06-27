"""Legacy dev project export compatibility package.

The packaged build pipeline is `termin.project_build`. This package keeps the
old broad-copy build.json/assets export available only under the explicit
`export_legacy_project` name for dev/play-mode flows.
"""

from termin.project_builder.legacy_project_export import export_legacy_project
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
    "export_legacy_project",
]
