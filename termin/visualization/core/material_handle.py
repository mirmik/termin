"""
MaterialKeeper и MaterialHandle — управление ссылками на материалы.

Наследуются от ResourceKeeper/ResourceHandle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.visualization.core.resource_handle import ResourceHandle, ResourceKeeper

if TYPE_CHECKING:
    from termin.visualization.core.material import Material


class MaterialKeeper(ResourceKeeper["Material"]):
    """
    Владелец материала по имени.

    Особенности:
    - Не требует GPU cleanup
    - update_resource использует update_from() для сохранения identity
    - Проверяет конфликты source_path при set_resource
    """

    def _on_cleanup(self, resource: "Material") -> None:
        """Материалы не требуют GPU cleanup."""
        pass

    @property
    def material(self) -> "Material | None":
        """Алиас для resource."""
        return self._resource

    @property
    def has_material(self) -> bool:
        """Алиас для has_resource."""
        return self.has_resource

    def set_material(self, material: "Material", source_path: str | None = None) -> None:
        """
        Установить материал.

        Raises:
            ValueError: Если материал уже установлен из другого источника
        """
        if self._resource is not None and self._source_path is not None:
            if source_path is not None and source_path != self._source_path:
                raise ValueError(
                    f"Material name conflict: '{self.name}' already loaded from "
                    f"'{self._source_path}', cannot load from '{source_path}'"
                )

        self._resource = material
        if source_path is not None:
            self._source_path = source_path

    def update_material(self, material: "Material") -> None:
        """
        Обновить материал (hot-reload).

        Использует update_from() для сохранения identity объекта.
        """
        if self._resource is None:
            self._resource = material
        else:
            self._resource.update_from(material)


class MaterialHandle(ResourceHandle["Material"]):
    """
    Умная ссылка на материал.

    Использование:
        handle = MaterialHandle.from_material(mat)  # прямая ссылка
        handle = MaterialHandle.from_name("Metal")  # по имени (hot-reload)
    """

    @classmethod
    def from_material(cls, material: "Material") -> "MaterialHandle":
        """Создать handle с прямой ссылкой на материал."""
        handle = cls()
        handle._init_direct(material)
        return handle

    @classmethod
    def from_name(cls, name: str) -> "MaterialHandle":
        """Создать handle по имени материала."""
        from termin.visualization.core.resources import ResourceManager

        handle = cls()
        keeper = ResourceManager.instance().get_or_create_keeper(name)
        handle._init_named(name, keeper)
        return handle

    def get(self) -> "Material":
        """
        Получить материал.

        Returns:
            Material или ErrorMaterial если материал недоступен
        """
        if self._direct is not None:
            return self._direct

        if self._keeper is not None and self._keeper.has_resource:
            return self._keeper.resource  # type: ignore

        from termin.visualization.core.material import get_error_material

        return get_error_material()

    def get_or_none(self) -> "Material | None":
        """Получить материал или None если недоступен."""
        if self._direct is not None:
            return self._direct

        if self._keeper is not None:
            return self._keeper.resource

        return None

    def serialize(self) -> dict:
        """Сериализация."""
        if self._direct is not None:
            return {
                "type": "direct",
                "material": self._direct.serialize(),
            }
        elif self._name is not None:
            return {
                "type": "named",
                "name": self._name,
            }
        else:
            return {"type": "none"}

    @classmethod
    def deserialize(cls, data: dict) -> "MaterialHandle":
        """Десериализация."""
        handle_type = data.get("type", "none")

        if handle_type == "named":
            name = data.get("name")
            if name:
                return cls.from_name(name)
        elif handle_type == "direct":
            from termin.visualization.core.material import Material

            mat_data = data.get("material")
            if mat_data:
                material = Material.deserialize(mat_data)
                return cls.from_material(material)

        return cls()
