"""File type processors for ProjectFileWatcher."""

from termin.editor.file_processors.material_processor import MaterialFileProcessor
from termin.editor.file_processors.mesh_processor import MeshFileProcessor
from termin.editor.file_processors.shader_processor import ShaderFileProcessor
from termin.editor.file_processors.texture_processor import TextureFileProcessor
from termin.editor.file_processors.component_processor import ComponentFileProcessor
from termin.editor.file_processors.pipeline_processor import PipelineFileProcessor

__all__ = [
    "MaterialFileProcessor",
    "MeshFileProcessor",
    "ShaderFileProcessor",
    "TextureFileProcessor",
    "ComponentFileProcessor",
    "PipelineFileProcessor",
]
