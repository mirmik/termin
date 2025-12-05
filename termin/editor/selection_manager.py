"""Selection manager - handles entity selection and hover state."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from termin.visualization.core.entity import Entity


class SelectionManager:
    """
    Управляет выделением и подсветкой объектов.

    Ответственности:
    - Хранение текущего выделенного объекта
    - Хранение текущего hover объекта
    - ID для подсветки в рендере
    - Уведомление подписчиков об изменениях
    """

    def __init__(
        self,
        get_pick_id: Callable[["Entity | None"], int],
        on_selection_changed: Optional[Callable[["Entity | None"], None]] = None,
        on_hover_changed: Optional[Callable[["Entity | None"], None]] = None,
    ):
        """
        Args:
            get_pick_id: Функция для получения pick ID сущности
            on_selection_changed: Колбэк при изменении выделения
            on_hover_changed: Колбэк при изменении hover
        """
        self._get_pick_id = get_pick_id
        self._on_selection_changed = on_selection_changed
        self._on_hover_changed = on_hover_changed

        self._selected_entity: "Entity | None" = None
        self._hover_entity: "Entity | None" = None

        # ID для рендера подсветки
        self.selected_entity_id: int = 0
        self.hover_entity_id: int = 0

    @property
    def selected(self) -> "Entity | None":
        """Текущий выделенный объект."""
        return self._selected_entity

    @property
    def hovered(self) -> "Entity | None":
        """Текущий hover объект."""
        return self._hover_entity

    def select(self, entity: "Entity | None") -> None:
        """
        Выделяет сущность.

        Args:
            entity: Сущность для выделения или None для снятия выделения
        """
        # Фильтруем non-selectable
        if entity is not None and not entity.selectable:
            return

        if entity is self._selected_entity:
            return

        self._selected_entity = entity
        self.selected_entity_id = self._get_pick_id(entity)

        if self._on_selection_changed:
            self._on_selection_changed(entity)

    def hover(self, entity: "Entity | None") -> None:
        """
        Устанавливает hover на сущность.

        Args:
            entity: Сущность для hover или None для снятия
        """
        # Фильтруем non-selectable
        if entity is not None and not entity.selectable:
            entity = None

        if entity is self._hover_entity:
            return

        self._hover_entity = entity
        self.hover_entity_id = self._get_pick_id(entity)

        if self._on_hover_changed:
            self._on_hover_changed(entity)

    def clear(self) -> None:
        """Сбрасывает выделение и hover."""
        self.select(None)
        self.hover(None)

    def deselect(self) -> None:
        """Снимает выделение."""
        self.select(None)
