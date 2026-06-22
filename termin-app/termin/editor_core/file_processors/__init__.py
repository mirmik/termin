"""File pre-loaders for ProjectFileWatcher."""

from termin.editor_core.file_processors.material_processor import MaterialPreLoader
from termin.editor_core.file_processors.mesh_processor import MeshPreLoader
from termin.editor_core.file_processors.shader_processor import ShaderPreLoader
from termin.editor_core.file_processors.texture_processor import TexturePreLoader
from termin.editor_core.file_processors.component_processor import ComponentFileProcessor
from termin.editor_core.file_processors.module_processor import ModuleFileProcessor
from termin.editor_core.file_processors.pipeline_preloader import PipelinePreLoader
from termin.editor_core.file_processors.scene_pipeline_preloader import ScenePipelinePreLoader
from termin.editor_core.file_processors.voxel_grid_processor import VoxelGridPreLoader
from termin.editor_core.file_processors.navmesh_processor import NavMeshPreLoader
from termin.editor_core.file_processors.glb_processor import GLBPreLoader
from termin.editor_core.file_processors.glsl_processor import GlslPreLoader
from termin.editor_core.file_processors.prefab_processor import PrefabPreLoader
from termin.editor_core.file_processors.audio_processor import AudioPreLoader
from termin.editor_core.file_processors.ui_processor import UIPreLoader

__all__ = [
    "MaterialPreLoader",
    "MeshPreLoader",
    "ShaderPreLoader",
    "TexturePreLoader",
    "ComponentFileProcessor",
    "ModuleFileProcessor",
    "PipelinePreLoader",
    "ScenePipelinePreLoader",
    "VoxelGridPreLoader",
    "NavMeshPreLoader",
    "GLBPreLoader",
    "GlslPreLoader",
    "PrefabPreLoader",
    "AudioPreLoader",
    "UIPreLoader",
]
