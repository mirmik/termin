"""MeshGPU - GPU resource wrapper for mesh rendering."""

from __future__ import annotations

from typing import Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from termin.mesh.mesh import Mesh3
    from termin.visualization.platform.backends.base import MeshHandle as GPUMeshHandle
    from termin.visualization.render.render_context import RenderContext


class MeshGPU:
    """
    GPU resource wrapper for mesh rendering.

    Handles:
    - GPU buffer upload (VAO/VBO/EBO)
    - Version tracking for automatic re-upload
    - Multi-context support (multiple GL contexts)

    This is a TEMPORARY solution. GPU resource management
    will be refactored later.

    Usage:
        mesh_gpu = MeshGPU()
        # In render loop:
        mesh_gpu.draw(context, mesh_data, version)
    """

    def __init__(self):
        """Initialize MeshGPU with no uploaded data."""
        self._uploaded_version: int = -1
        self._handles: Dict[int, "GPUMeshHandle"] = {}

    @property
    def uploaded_version(self) -> int:
        """Version of currently uploaded data."""
        return self._uploaded_version

    @property
    def is_uploaded(self) -> bool:
        """True if any GPU data is uploaded."""
        return len(self._handles) > 0

    def draw(
        self,
        context: "RenderContext",
        mesh_data: "Mesh3",
        version: int,
    ) -> None:
        """
        Draw mesh, uploading/re-uploading if needed.

        Args:
            context: Render context with graphics backend
            mesh_data: Mesh3 geometry data
            version: Current version of mesh data
        """
        if mesh_data is None:
            return

        # Check if we need to re-upload
        if self._uploaded_version != version:
            self._invalidate()
            self._uploaded_version = version

        # Upload to this context if needed
        ctx_key = context.context_key
        if ctx_key not in self._handles:
            self._upload(context, mesh_data)

        # Draw
        self._handles[ctx_key].draw()

    _DEBUG_UPLOAD = False

    def _upload(self, context: "RenderContext", mesh_data: "Mesh3") -> None:
        """Upload mesh data to GPU for this context."""
        if self._DEBUG_UPLOAD:
            print(f"[MeshGPU._upload] mesh_data type: {type(mesh_data).__name__}")
            layout = mesh_data.get_vertex_layout()
            print(f"  vertex_layout stride={layout.stride}, attrs={[a.name for a in layout.attributes]}")
            buf = mesh_data.interleaved_buffer()
            print(f"  interleaved_buffer shape: {buf.shape}")
            # Check joints/weights for skinned meshes
            if hasattr(mesh_data, 'joint_indices') and hasattr(mesh_data, 'joint_weights'):
                print(f"  joint_indices[0:3]: {mesh_data.joint_indices[:3]}")
                print(f"  joint_weights[0:3]: {mesh_data.joint_weights[:3]}")
                # Check if weights sum to ~1.0
                weight_sums = mesh_data.joint_weights.sum(axis=1)
                print(f"  weight_sums min={weight_sums.min():.3f}, max={weight_sums.max():.3f}, mean={weight_sums.mean():.3f}")
        handle = context.graphics.create_mesh(mesh_data)
        self._handles[context.context_key] = handle

    def _invalidate(self) -> None:
        """Delete all GPU handles (version changed)."""
        from termin.visualization.platform.backends import (
            get_context_make_current,
            get_current_context_key,
        )

        if not self._handles:
            return

        # Save current context
        original_ctx = get_current_context_key()

        # Delete all handles
        for ctx_key, handle in self._handles.items():
            make_current = get_context_make_current(ctx_key)
            if make_current is not None:
                make_current()
            handle.delete()
        self._handles.clear()

        # Restore original context
        if original_ctx is not None:
            restore = get_context_make_current(original_ctx)
            if restore is not None:
                restore()

    def delete(self) -> None:
        """Explicitly delete all GPU resources."""
        self._invalidate()
        self._uploaded_version = -1
