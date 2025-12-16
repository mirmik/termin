"""File pre-loaders for ProjectFileWatcher."""

from termin.editor.file_processors.material_processor import MaterialPreLoader
from termin.editor.file_processors.mesh_processor import MeshFileProcessor
from termin.editor.file_processors.shader_processor import ShaderFileProcessor
from termin.editor.file_processors.texture_processor import TextureFileProcessor
from termin.editor.file_processors.component_processor import ComponentFileProcessor
from termin.editor.file_processors.pipeline_processor import PipelineFileProcessor
from termin.editor.file_processors.voxel_grid_processor import VoxelGridProcessor
from termin.editor.file_processors.navmesh_processor import NavMeshProcessor
from termin.editor.file_processors.glb_processor import GLBPreLoader

# Backward compatibility aliases
MaterialFileProcessor = MaterialPreLoader

__all__ = [
    "MaterialPreLoader",
    "MaterialFileProcessor",  # backward compat
    "MeshFileProcessor",
    "ShaderFileProcessor",
    "TextureFileProcessor",
    "ComponentFileProcessor",
    "PipelineFileProcessor",
    "VoxelGridProcessor",
    "NavMeshProcessor",
    "GLBPreLoader",
]
