"""Editor-specific file processors for ProjectFileWatcher."""

from termin.editor_core.file_processors.component_processor import ComponentFileProcessor
from termin.editor_core.file_processors.module_processor import (
    ModuleFileProcessor,
    ModuleInputFileProcessor,
)

__all__ = [
    "ComponentFileProcessor",
    "ModuleFileProcessor",
    "ModuleInputFileProcessor",
]
