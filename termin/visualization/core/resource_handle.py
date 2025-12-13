"""
ResourceKeeper и ResourceHandle — базовые классы для управления ресурсами.

ResourceKeeper[T] — владелец ресурса по имени, управляет жизненным циклом.
ResourceHandle[T] — легковесная ссылка на ресурс (прямая или по имени).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Generic, TypeVar

if TYPE_CHECKING:
    pass

T = TypeVar("T")


class ResourceKeeper(Generic[T]):
    """
    Базовый владелец ресурса по имени.

    Создаётся ResourceManager'ом при первом обращении к имени.
    Хранит ресурс, знает источник (файл), контролирует жизненный цикл.
    """

    def __init__(self, name: str):
        self.name = name
        self._resource: T | None = None
        self._source_path: str | None = None

    @property
    def resource(self) -> T | None:
        """Текущий ресурс или None если не загружен."""
        return self._resource

    @property
    def source_path(self) -> str | None:
        """Путь к файлу-источнику ресурса."""
        return self._source_path

    @property
    def has_resource(self) -> bool:
        """Есть ли ресурс."""
        return self._resource is not None

    def _on_cleanup(self, resource: T) -> None:
        """
        Вызывается перед заменой/удалением ресурса.

        Override для очистки GPU памяти и т.д.
        По умолчанию вызывает resource.delete() если метод существует.
        """
        if hasattr(resource, "delete"):
            resource.delete()  # type: ignore

    def set_resource(self, resource: T, source_path: str | None = None) -> None:
        """
        Установить ресурс.

        Args:
            resource: Ресурс
            source_path: Путь к файлу-источнику
        """
        if self._resource is not None:
            self._on_cleanup(self._resource)

        self._resource = resource
        if source_path is not None:
            self._source_path = source_path

    def update_resource(self, resource: T) -> None:
        """
        Обновить ресурс (hot-reload).

        По умолчанию просто заменяет ресурс.
        Override для сохранения identity (например, update_from).
        """
        if self._resource is not None:
            self._on_cleanup(self._resource)
        self._resource = resource

    def clear(self) -> None:
        """Удалить ресурс из keeper'а."""
        if self._resource is not None:
            self._on_cleanup(self._resource)
        self._resource = None
        self._source_path = None


class ResourceHandle(Generic[T]):
    """
    Базовая умная ссылка на ресурс.

    Два режима работы:
    1. Direct — хранит прямую ссылку на ресурс (создан из кода)
    2. Named — хранит ссылку на ResourceKeeper (по имени из ResourceManager)
    """

    def __init__(self):
        self._direct: T | None = None
        self._keeper: ResourceKeeper[T] | None = None
        self._name: str | None = None

    @property
    def is_direct(self) -> bool:
        """True если это прямая ссылка на ресурс."""
        return self._direct is not None

    @property
    def is_named(self) -> bool:
        """True если это ссылка по имени."""
        return self._keeper is not None

    @property
    def name(self) -> str | None:
        """Имя ресурса."""
        if self._direct is not None and hasattr(self._direct, "name"):
            return self._direct.name  # type: ignore
        return self._name

    def get(self) -> T | None:
        """
        Получить ресурс.

        Returns:
            Ресурс или None если недоступен
        """
        if self._direct is not None:
            return self._direct

        if self._keeper is not None and self._keeper.has_resource:
            return self._keeper.resource

        return None

    def get_or_none(self) -> T | None:
        """Алиас для get()."""
        return self.get()

    def _init_direct(self, resource: T) -> None:
        """Инициализировать как прямую ссылку."""
        self._direct = resource
        self._keeper = None
        self._name = None

    def _init_named(self, name: str, keeper: ResourceKeeper[T]) -> None:
        """Инициализировать как ссылку по имени."""
        self._direct = None
        self._keeper = keeper
        self._name = name

    def serialize(self) -> dict:
        """Сериализация для сохранения сцены."""
        if self._direct is not None:
            if hasattr(self._direct, "serialize"):
                return {
                    "type": "direct",
                    "data": self._direct.serialize(),  # type: ignore
                }
            return {"type": "direct_unsupported"}
        elif self._name is not None:
            return {
                "type": "named",
                "name": self._name,
            }
        else:
            return {"type": "none"}
