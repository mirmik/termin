"""Compatibility re-export for project asset watching.

New code should import from termin.assets.project_file_watcher.
"""

from termin.assets.project_file_watcher import (
    DEBOUNCE_DELAY_S,
    FilePreLoader,
    PreLoadResult,
    ProjectFileWatcher,
)

__all__ = [
    "DEBOUNCE_DELAY_S",
    "FilePreLoader",
    "PreLoadResult",
    "ProjectFileWatcher",
]
