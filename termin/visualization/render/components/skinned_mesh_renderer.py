"""SkinnedMeshRenderer - Renderer component for skinned meshes with skeletal animation."""

from __future__ import annotations

from typing import List, TYPE_CHECKING

import numpy as np

from termin.editor.inspect_field import InspectField
from termin.mesh.skinned_mesh import SkinnedMesh3
from termin.visualization.core.entity import RenderContext
from termin.visualization.core.material import Material
from termin.visualization.core.mesh_handle import MeshHandle
from termin.visualization.core.resources import ResourceManager
from termin.visualization.render.components.mesh_renderer import MeshRenderer
from termin.visualization.render.drawable import GeometryDrawCall

if TYPE_CHECKING:
    from termin.skeleton.skeleton import SkeletonInstance
    from termin.visualization.render.components.skeleton_controller import SkeletonController


class SkinnedMeshRenderer(MeshRenderer):
    """
    Renderer component for skinned meshes with skeletal animation.

    Extends MeshRenderer with:
    - skeleton_controller: Reference to SkeletonController for bone matrices
    - Automatic skinning injection into any material shader
    - Automatic upload of u_bone_matrices uniform before drawing
    """

    inspect_fields = {
        **MeshRenderer.inspect_fields,
        # skeleton_controller is typically set programmatically, not in inspector
    }

    _DEBUG_INIT = False
    _DEBUG_LIFECYCLE = False
    _DEBUG_SHADER_INJECTION = False

    def __init__(
        self,
        mesh: MeshHandle | SkinnedMesh3 | None = None,
        material: Material | None = None,
        skeleton_controller: "SkeletonController | None" = None,
        cast_shadow: bool = True,
    ):
        """
        Initialize SkinnedMeshRenderer.

        Args:
            mesh: Skinned mesh (MeshHandle or SkinnedMesh3)
            material: Material to use for rendering (will be auto-converted to skinned variant)
            skeleton_controller: Controller that provides skeleton instance
            cast_shadow: Whether this object casts shadows
        """
        if self._DEBUG_INIT:
            print(f"[SkinnedMeshRenderer.__init__] mesh={mesh}, material={material}")
            if material:
                print(f"  material type: {type(material).__name__}")
                print(f"  material phases: {len(material.phases) if hasattr(material, 'phases') else 'N/A'}")
        super().__init__(mesh=mesh, material=material, cast_shadow=cast_shadow)
        self._skeleton_controller: "SkeletonController | None" = skeleton_controller
        self._skinned_material_cache: Material | None = None  # Cached skinned variant
        self._cached_base_material_id: int | None = None  # Track which base material was cached
        if self._DEBUG_INIT:
            print(f"  After super().__init__: _material_handle._direct={self._material_handle._direct}")

    @property
    def skeleton_controller(self) -> "SkeletonController | None":
        """Get the skeleton controller."""
        return self._skeleton_controller

    @skeleton_controller.setter
    def skeleton_controller(self, value: "SkeletonController | None"):
        """Set the skeleton controller."""
        self._skeleton_controller = value

    @MeshRenderer.material.setter
    def material(self, value: Material | None):
        """Set material and invalidate skinned cache."""
        MeshRenderer.material.fset(self, value)
        self._skinned_material_cache = None  # Invalidate cache
        self._cached_base_material_id = None

    def set_material(self, material: Material | None):
        """Set material and invalidate skinned cache."""
        self.material = material

    def start(self, scene) -> None:
        """Called once before the first update. Re-acquire skeleton_controller if needed."""
        super().start(scene)

        # After deserialization, skeleton_controller may be None - try to find it
        if self._skeleton_controller is None and self.entity is not None:
            from termin.visualization.render.components.skeleton_controller import SkeletonController
            # Look for SkeletonController on parent entity (typical for GLB structure)
            parent = self.entity.transform.parent
            if parent is not None and parent.entity is not None:
                self._skeleton_controller = parent.entity.get_component(SkeletonController)
            # Also check current entity
            if self._skeleton_controller is None:
                self._skeleton_controller = self.entity.get_component(SkeletonController)

        if self._DEBUG_LIFECYCLE:
            print(f"[SkinnedMeshRenderer.start] entity={self.entity.name if self.entity else 'None'}")
            print(f"  skeleton_controller={self._skeleton_controller is not None}")
            if self._skeleton_controller:
                print(f"  skeleton_instance={self._skeleton_controller.skeleton_instance is not None}")

    def on_editor_start(self):
        """Called when scene starts in editor mode. Refresh bone matrices from skeleton."""
        # Re-acquire skeleton_controller if needed (may not be set after deserialization)
        if self._skeleton_controller is None and self.entity is not None:
            from termin.visualization.render.components.skeleton_controller import SkeletonController
            parent = self.entity.transform.parent
            if parent is not None and parent.entity is not None:
                self._skeleton_controller = parent.entity.get_component(SkeletonController)
            if self._skeleton_controller is None:
                self._skeleton_controller = self.entity.get_component(SkeletonController)

        skeleton_instance = self.skeleton_instance
        if skeleton_instance is not None:
            skeleton_instance.update()

    @property
    def skeleton_instance(self) -> "SkeletonInstance | None":
        """Get the skeleton instance from controller."""
        if self._skeleton_controller is not None:
            return self._skeleton_controller.skeleton_instance
        return None

    def _get_skinned_material(self) -> Material | None:
        """
        Get skinned variant of the current material.

        Automatically injects skinning code into the shader if needed.
        Caches the result for performance.
        """
        if self._DEBUG_SHADER_INJECTION:
            print(f"[SkinnedMeshRenderer._get_skinned_material] called, entity={self.entity.name if self.entity else 'None'}")

        base_mat = self._material_handle.get_material_or_none()
        if base_mat is None:
            if self._DEBUG_SHADER_INJECTION:
                print(f"  base_mat is None")
            return None

        # Check if cache is still valid (same base material object)
        base_mat_id = id(base_mat)
        if self._skinned_material_cache is not None and self._cached_base_material_id == base_mat_id:
            return self._skinned_material_cache

        # Check if shader already has skinning (e.g., SkinnedMaterial)
        if base_mat.phases:
            shader_source = base_mat.phases[0].shader_programm.vertex_source
            if 'u_bone_matrices' in shader_source:
                # Already has skinning, use as-is
                if self._DEBUG_SHADER_INJECTION:
                    print(f"[SkinnedMeshRenderer] Material '{base_mat.name}' already has skinning")
                self._skinned_material_cache = base_mat
                self._cached_base_material_id = base_mat_id
                return base_mat

        # Create skinned variant
        if self._DEBUG_SHADER_INJECTION:
            print(f"[SkinnedMeshRenderer] Injecting skinning into material '{base_mat.name}'")
            if base_mat.phases:
                original_vert = base_mat.phases[0].shader_programm.vertex_source
                print(f"  === Original vertex shader ({len(original_vert)} chars) ===")
                print(original_vert)
                print(f"  === End original vertex shader ===")

        from termin.visualization.render.shader_skinning import get_skinned_material
        self._skinned_material_cache = get_skinned_material(base_mat)
        self._cached_base_material_id = base_mat_id

        if self._DEBUG_SHADER_INJECTION:
            if self._skinned_material_cache and self._skinned_material_cache.phases:
                skinned_vert = self._skinned_material_cache.phases[0].shader_programm.vertex_source
                print(f"  === Skinned vertex shader ({len(skinned_vert)} chars) ===")
                print(skinned_vert)
                print(f"  === End skinned vertex shader ===")

        return self._skinned_material_cache

    def get_geometry_draws(self, phase_mark: str | None = None) -> List[GeometryDrawCall]:
        """
        Returns GeometryDrawCalls with skinned material variant.

        Overrides MeshRenderer to use automatically skinned shader.
        """
        mat = self._get_skinned_material()
        if mat is None:
            return []

        if phase_mark is None:
            phases = list(mat.phases)
        else:
            phases = [p for p in mat.phases if p.phase_mark == phase_mark]

        phases.sort(key=lambda p: p.priority)
        return [GeometryDrawCall(phase=p) for p in phases]

    _DEBUG_SKINNING = False  # Temporary debug flag
    _debug_skinning_frame = 0

    def draw_geometry(self, context: RenderContext, geometry_id: str = "") -> None:
        """
        Draw skinned geometry with bone matrices.

        Uploads u_bone_matrices uniform to the currently bound shader
        before drawing the mesh.
        """
        mesh_data = self._mesh_handle.mesh
        gpu = self._mesh_handle.gpu
        if mesh_data is None or gpu is None:
            return

        # Upload bone matrices if we have a skeleton
        skeleton_instance = self.skeleton_instance
        if skeleton_instance is not None:
            bone_matrices = skeleton_instance.get_bone_matrices()
            bone_count = len(bone_matrices)

            # Get current shader from context and upload bone matrices
            shader = context.current_shader
            if self._DEBUG_SKINNING and SkinnedMeshRenderer._debug_skinning_frame < 5:
                SkinnedMeshRenderer._debug_skinning_frame += 1
                print(f"[SkinnedMeshRenderer] bone_count={bone_count}, shader={shader}")
                if bone_count > 0:
                    # Check if any bone matrix is non-identity
                    identity = np.eye(4, dtype=np.float32)
                    non_identity_count = sum(1 for m in bone_matrices if not np.allclose(m, identity, atol=1e-4))
                    print(f"  non_identity_matrices: {non_identity_count}/{bone_count}")
                    print(f"  bone_matrix[0] diagonal: {bone_matrices[0].diagonal()}")

            if shader is not None:
                shader.set_uniform_matrix4_array("u_bone_matrices", bone_matrices, bone_count)
                shader.set_uniform_int("u_bone_count", bone_count)

        # Draw the mesh via GPU
        gpu.draw(context, mesh_data, self._mesh_handle.version)

    def serialize_data(self) -> dict:
        """Serialize SkinnedMeshRenderer."""
        data = super().serialize_data()
        # skeleton_instance is runtime state, not serialized
        # It's linked via SkeletonAsset UUID in the scene
        return data
