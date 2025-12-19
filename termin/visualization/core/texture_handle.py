"""
TextureHandle — умная ссылка на текстуру.

Два режима:
1. Direct — хранит TextureData напрямую
2. Asset — хранит TextureAsset (lookup по имени через ResourceManager)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.visualization.core.resource_handle import ResourceHandle

if TYPE_CHECKING:
    from termin.visualization.render.texture_data import TextureData
    from termin.visualization.render.texture_asset import TextureAsset
    from termin.visualization.render.texture_gpu import TextureGPU
    from termin.visualization.platform.backends.base import GraphicsBackend


class TextureHandle(ResourceHandle["TextureData", "TextureAsset"]):
    """
    Умная ссылка на текстуру.

    Использование:
        handle = TextureHandle.from_direct(texture_data)  # raw TextureData
        handle = TextureHandle.from_asset(asset)          # TextureAsset
        handle = TextureHandle.from_name("wood")          # lookup в ResourceManager
    """

    @classmethod
    def from_direct(cls, texture_data: "TextureData") -> "TextureHandle":
        """Создать handle с raw TextureData."""
        handle = cls()
        handle._init_direct(texture_data)
        return handle

    @classmethod
    def from_asset(cls, asset: "TextureAsset") -> "TextureHandle":
        """Создать handle с TextureAsset."""
        handle = cls()
        handle._init_asset(asset)
        return handle

    @classmethod
    def from_name(cls, name: str) -> "TextureHandle":
        """Создать handle по имени (lookup в ResourceManager)."""
        from termin.visualization.core.resources import ResourceManager

        asset = ResourceManager.instance().get_texture_asset(name)
        if asset is not None:
            return cls.from_asset(asset)
        return cls()

    @classmethod
    def from_texture_data(cls, texture_data: "TextureData", name: str = "texture") -> "TextureHandle":
        """Create handle from TextureData."""
        from termin.visualization.render.texture_asset import TextureAsset
        asset = TextureAsset(texture_data=texture_data, name=name)
        return cls.from_asset(asset)

    @classmethod
    def from_file(cls, path: str, name: str | None = None) -> "TextureHandle":
        """Create handle from image file."""
        from termin.visualization.render.texture_asset import TextureAsset
        asset = TextureAsset.from_file(path, name=name)
        return cls.from_asset(asset)

    # --- Resource extraction ---

    def _get_resource_from_asset(self, asset: "TextureAsset") -> "TextureData | None":
        """Извлечь TextureData из TextureAsset (lazy loading)."""
        asset.ensure_loaded()
        return asset.texture_data

    # --- Convenience accessors ---

    @property
    def texture_data(self) -> "TextureData | None":
        """Получить TextureData."""
        return self.get()

    @property
    def asset(self) -> "TextureAsset | None":
        """Получить TextureAsset."""
        return self.get_asset()

    def get_texture_data(self) -> "TextureData | None":
        """Получить TextureData."""
        return self.get()

    @property
    def gpu(self) -> "TextureGPU | None":
        """Get TextureGPU for rendering."""
        if self._asset is not None:
            return self._asset.gpu
        return None

    @property
    def version(self) -> int:
        """Version of texture data for tracking changes."""
        if self._asset is not None:
            return self._asset.version
        return 0

    @property
    def source_path(self) -> str | None:
        """Source path of the texture."""
        if self._asset is not None and self._asset.source_path is not None:
            return str(self._asset.source_path)
        return None

    def bind(
        self,
        graphics: "GraphicsBackend",
        unit: int = 0,
        context_key: int | None = None,
    ) -> None:
        """Bind texture to specified unit (convenience method)."""
        texture_data = self.get()
        if texture_data is None:
            return
        gpu = self.gpu
        if gpu is None:
            return
        gpu.bind(
            graphics=graphics,
            texture_data=texture_data,
            version=self.version,
            unit=unit,
            context_key=context_key,
        )

    def delete(self) -> None:
        """Delete GPU resources."""
        if self._asset is not None:
            self._asset.delete_gpu()

    # --- Serialization ---

    def _serialize_direct(self) -> dict:
        """Сериализовать raw TextureData."""
        if self._direct is not None:
            return self._direct.direct_serialize()
        return {"type": "direct_unsupported"}

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "TextureHandle":
        """Десериализация."""
        from termin.visualization.render.texture_asset import TextureAsset

        handle_type = data.get("type", "none")

        if handle_type == "named":
            name = data.get("name")
            if name:
                return cls.from_name(name)
        elif handle_type == "path":
            path = data.get("path")
            if path:
                asset = TextureAsset.from_file(path)
                return cls.from_asset(asset)

        return cls()


# --- White 1x1 Texture Handle Singleton ---

_white_texture_handle: TextureHandle | None = None


def get_white_texture_handle() -> TextureHandle:
    """
    Returns a white 1x1 texture handle.

    Used as default for optional texture slots.
    Singleton — created once.
    """
    global _white_texture_handle

    if _white_texture_handle is None:
        from termin.visualization.render.texture_asset import TextureAsset
        asset = TextureAsset.white_1x1()
        _white_texture_handle = TextureHandle.from_asset(asset)

    return _white_texture_handle
