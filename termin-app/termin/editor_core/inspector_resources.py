"""UI-neutral resource choices for generic inspector handle fields."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any


_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InspectorResourceChoice:
    label: str
    name: str | None
    uuid: str | None

    @property
    def value(self) -> dict[str, str | None] | None:
        if self.name is None:
            return None
        return {"uuid": self.uuid, "name": self.name}


@dataclass(frozen=True)
class InspectorResourceChoices:
    kind: str
    items: tuple[InspectorResourceChoice, ...]
    can_create: bool

    def index_for_value(self, value: Any) -> int:
        if value is None:
            return next((index for index, item in enumerate(self.items) if item.name is None), -1)
        if not isinstance(value, dict):
            return -1
        uuid = value.get("uuid")
        name = value.get("name")
        if uuid:
            for index, item in enumerate(self.items):
                if item.uuid == uuid:
                    return index
        if name:
            for index, item in enumerate(self.items):
                if item.name == name:
                    return index
        return -1


class InspectorResourceCatalog:
    def __init__(self, resource_manager) -> None:
        self._resource_manager = resource_manager

    def choices(self, kind: str) -> InspectorResourceChoices | None:
        accessors = self._resource_manager.get_handle_accessors(kind)
        if accessors is None:
            return None
        items = []
        if accessors.allow_none:
            items.append(InspectorResourceChoice("(None)", None, None))
        try:
            resources = accessors.list_items()
        except Exception:
            _logger.exception("Failed to list inspector resources for kind '%s'", kind)
            raise
        items.extend(
            InspectorResourceChoice(name, name, uuid)
            for name, uuid in resources
        )
        return InspectorResourceChoices(
            kind=kind,
            items=tuple(items),
            can_create=accessors.create_item is not None,
        )

    def create(self, kind: str) -> InspectorResourceChoice | None:
        accessors = self._resource_manager.get_handle_accessors(kind)
        if accessors is None:
            _logger.error("Cannot create inspector resource for unknown kind '%s'", kind)
            raise ValueError(f"unknown inspector resource kind '{kind}'")
        if accessors.create_item is None:
            return None
        try:
            created = accessors.create_item()
        except Exception:
            _logger.exception("Failed to create inspector resource for kind '%s'", kind)
            raise
        if created is None:
            return None
        name, uuid = created
        return InspectorResourceChoice(name, name, uuid)


__all__ = [
    "InspectorResourceCatalog",
    "InspectorResourceChoice",
    "InspectorResourceChoices",
]
