"""
TextureKeeper и TextureHandle — управление ссылками на текстуры.

Наследуются от ResourceKeeper/ResourceHandle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.visualization.core.resource_handle import ResourceHandle, ResourceKeeper

if TYPE_CHECKING:
    from termin.visualization.render.texture import Texture


class TextureKeeper(ResourceKeeper["Texture"]):
    """
    Владелец текстуры по имени.

    Особенности:
    - Не требует явного GPU cleanup (текстура сама управляет)
    - Hot-reload через invalidate() - текстура перезагрузится при следующем использовании
    """

    def _on_cleanup(self, resource: "Texture") -> None:
        """Текстуры не требуют явного cleanup при замене."""
        pass

    @property
    def texture(self) -> "Texture | None":
        """Алиас для resource."""
        return self._resource

    @property
    def has_texture(self) -> bool:
        """Алиас для has_resource."""
        return self.has_resource

    def set_texture(self, texture: "Texture", source_path: str | None = None) -> None:
        """Алиас для set_resource."""
        self.set_resource(texture, source_path)

    def invalidate(self) -> None:
        """
        Инвалидировать текстуру для hot-reload.

        Текстура перезагрузится из файла при следующем использовании.
        """
        if self._resource is not None:
            self._resource.invalidate()


class TextureHandle(ResourceHandle["Texture"]):
    """
    Умная ссылка на текстуру.

    Использование:
        handle = TextureHandle.from_texture(tex)   # прямая ссылка
        handle = TextureHandle.from_name("wood")   # по имени (hot-reload)
    """

    @classmethod
    def from_texture(cls, texture: "Texture") -> "TextureHandle":
        """Создать handle с прямой ссылкой на текстуру."""
        handle = cls()
        handle._init_direct(texture)
        return handle

    @classmethod
    def from_name(cls, name: str) -> "TextureHandle":
        """Создать handle по имени текстуры."""
        from termin.visualization.core.resources import ResourceManager

        handle = cls()
        keeper = ResourceManager.instance().get_or_create_texture_keeper(name)
        handle._init_named(name, keeper)
        return handle

    def serialize(self) -> dict:
        """Сериализация."""
        if self._direct is not None:
            # Direct текстуры обычно не сериализуются (созданы из кода)
            if self._direct.source_path:
                return {
                    "type": "path",
                    "path": self._direct.source_path,
                }
            return {"type": "direct_unsupported"}
        elif self._name is not None:
            return {
                "type": "named",
                "name": self._name,
            }
        else:
            return {"type": "none"}

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "TextureHandle":
        """Десериализация."""
        handle_type = data.get("type", "none")

        if handle_type == "named":
            name = data.get("name")
            if name:
                return cls.from_name(name)
        elif handle_type == "path":
            from termin.visualization.render.texture import Texture

            path = data.get("path")
            if path:
                texture = Texture.from_file(path)
                return cls.from_texture(texture)

        return cls()
