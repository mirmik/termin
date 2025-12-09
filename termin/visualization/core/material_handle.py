"""
MaterialHandle и MaterialKeeper — система управления ссылками на материалы.

MaterialHandle — легковесная ссылка на материал для MeshRenderer.
MaterialKeeper — владелец материала по имени, управляет жизненным циклом.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from termin.visualization.core.material import Material


class MaterialKeeper:
    """
    Владелец материала по имени.

    Создаётся ResourceManager'ом при первом обращении к имени.
    Хранит материал, знает источник (файл), контролирует конфликты.
    """

    def __init__(self, name: str):
        self.name = name
        self._material: Material | None = None
        self._source_path: str | None = None

    @property
    def material(self) -> Material | None:
        """Текущий материал или None если не загружен."""
        return self._material

    @property
    def source_path(self) -> str | None:
        """Путь к файлу-источнику материала."""
        return self._source_path

    @property
    def has_material(self) -> bool:
        """Есть ли материал."""
        return self._material is not None

    def set_material(self, material: Material, source_path: str | None = None) -> None:
        """
        Установить материал.

        Args:
            material: Материал
            source_path: Путь к файлу-источнику (для контроля конфликтов)

        Raises:
            ValueError: Если материал уже установлен из другого источника
        """
        if self._material is not None and self._source_path is not None:
            if source_path is not None and source_path != self._source_path:
                raise ValueError(
                    f"Material name conflict: '{self.name}' already loaded from "
                    f"'{self._source_path}', cannot load from '{source_path}'"
                )

        self._material = material
        if source_path is not None:
            self._source_path = source_path

    def update_material(self, material: Material) -> None:
        """
        Обновить материал (hot-reload).

        Обновляет данные существующего материала, сохраняя идентичность объекта.
        Если материала ещё нет — просто устанавливает.
        """
        if self._material is None:
            self._material = material
        else:
            self._material.update_from(material)

    def clear(self) -> None:
        """Удалить материал из keeper'а."""
        self._material = None
        self._source_path = None


class MaterialHandle:
    """
    Умная ссылка на материал.

    Два режима работы:
    1. Direct — хранит прямую ссылку на Material (создан из кода)
    2. Named — хранит ссылку на MaterialKeeper (по имени из ResourceManager)

    MeshRenderer хранит MaterialHandle, а не Material напрямую.
    """

    def __init__(self):
        self._direct_material: Material | None = None
        self._keeper: MaterialKeeper | None = None
        self._name: str | None = None

    @classmethod
    def from_material(cls, material: Material) -> "MaterialHandle":
        """Создать handle с прямой ссылкой на материал."""
        handle = cls()
        handle._direct_material = material
        return handle

    @classmethod
    def from_name(cls, name: str) -> "MaterialHandle":
        """Создать handle по имени материала."""
        from termin.visualization.core.resources import ResourceManager

        handle = cls()
        handle._name = name
        handle._keeper = ResourceManager.instance().get_or_create_keeper(name)
        return handle

    @property
    def is_direct(self) -> bool:
        """True если это прямая ссылка на материал."""
        return self._direct_material is not None

    @property
    def is_named(self) -> bool:
        """True если это ссылка по имени."""
        return self._keeper is not None

    @property
    def name(self) -> str | None:
        """Имя материала (для named) или None (для direct)."""
        if self._direct_material is not None:
            return self._direct_material.name
        return self._name

    def get(self) -> Material:
        """
        Получить материал.

        Returns:
            Material или ErrorMaterial если материал недоступен
        """
        # Direct mode
        if self._direct_material is not None:
            return self._direct_material

        # Named mode
        if self._keeper is not None and self._keeper.has_material:
            return self._keeper.material  # type: ignore

        # Fallback to ErrorMaterial
        from termin.visualization.core.material import get_error_material
        return get_error_material()

    def get_or_none(self) -> Material | None:
        """Получить материал или None если недоступен."""
        if self._direct_material is not None:
            return self._direct_material

        if self._keeper is not None:
            return self._keeper.material

        return None

    def serialize(self) -> dict:
        """Сериализация для сохранения сцены."""
        if self._direct_material is not None:
            # Direct material — сериализуем сам материал
            return {
                "type": "direct",
                "material": self._direct_material.serialize(),
            }
        elif self._name is not None:
            # Named — сохраняем только имя
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

        # Fallback — пустой handle
        return cls()
