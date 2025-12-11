"""File type processors for ProjectFileWatcher."""

from termin.editor.file_processors.material_processor import MaterialFileProcessor
from termin.editor.file_processors.shader_processor import ShaderFileProcessor
from termin.editor.file_processors.texture_processor import TextureFileProcessor

__all__ = [
    "MaterialFileProcessor",
    "ShaderFileProcessor",
    "TextureFileProcessor",
]
