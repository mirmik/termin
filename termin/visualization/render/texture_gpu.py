"""TextureGPU - GPU resource wrapper for texture rendering."""

from __future__ import annotations

from typing import Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend, TextureHandle as GPUTextureHandle
    from termin.visualization.render.texture_data import TextureData


class TextureGPU:
    """
    GPU resource wrapper for texture rendering.

    Handles:
    - GPU texture upload
    - Version tracking for automatic re-upload
    - Multi-context support (multiple GL contexts)

    This is a TEMPORARY solution. GPU resource management
    will be refactored later.

    Usage:
        texture_gpu = TextureGPU()
        # To bind texture:
        texture_gpu.bind(graphics, texture_data, version, unit=0, context_key=ctx)
    """

    def __init__(self):
        """Initialize TextureGPU with no uploaded data."""
        self._uploaded_version: int = -1
        self._handles: Dict[int | None, "GPUTextureHandle"] = {}

    @property
    def uploaded_version(self) -> int:
        """Version of currently uploaded data."""
        return self._uploaded_version

    @property
    def is_uploaded(self) -> bool:
        """True if any GPU data is uploaded."""
        return len(self._handles) > 0

    def bind(
        self,
        graphics: "GraphicsBackend",
        texture_data: "TextureData",
        version: int,
        unit: int = 0,
        context_key: int | None = None,
    ) -> None:
        """
        Bind texture to unit, uploading/re-uploading if needed.

        Args:
            graphics: Graphics backend for GPU operations
            texture_data: TextureData with pixel data
            version: Current version of texture data
            unit: Texture unit to bind to
            context_key: GL context key
        """
        if texture_data is None:
            return

        # Check if we need to re-upload
        if self._uploaded_version != version:
            self._invalidate()
            self._uploaded_version = version

        # Upload to this context if needed
        if context_key not in self._handles:
            self._upload(graphics, texture_data, context_key)

        # Bind
        self._handles[context_key].bind(unit)

    def _upload(
        self,
        graphics: "GraphicsBackend",
        texture_data: "TextureData",
        context_key: int | None,
    ) -> None:
        """Upload texture data to GPU for this context."""
        data, size = texture_data.get_upload_data()
        handle = graphics.create_texture(data, size, channels=texture_data.channels)
        self._handles[context_key] = handle

    def _invalidate(self) -> None:
        """Delete all GPU handles (version changed)."""
        # Note: We don't explicitly delete texture handles here
        # because OpenGL texture cleanup is tricky with multiple contexts.
        # The handles will be garbage collected when Python releases them.
        # This matches the original Texture behavior.
        self._handles.clear()

    def delete(self) -> None:
        """Explicitly delete all GPU resources."""
        self._invalidate()
        self._uploaded_version = -1
