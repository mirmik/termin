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
    uuid_only: bool = False

    @property
    def value(self) -> dict[str, str | None] | str | None:
        if self.uuid_only:
            return self.uuid or ""
        if self.name is None:
            return None
        return {"uuid": self.uuid, "name": self.name}


@dataclass(frozen=True)
class InspectorResourceChoices:
    kind: str
    items: tuple[InspectorResourceChoice, ...]
    can_create: bool

    def index_for_value(self, value: Any) -> int:
        if value is None or value == "":
            return next((index for index, item in enumerate(self.items) if item.name is None), -1)
        if isinstance(value, str):
            uuid = value
        elif isinstance(value, dict):
            uuid = value.get("uuid")
        else:
            return -1
        if uuid:
            for index, item in enumerate(self.items):
                if item.uuid == uuid:
                    return index
            _logger.warning("Stale inspector resource UUID '%s' for kind '%s'", uuid, self.kind)
            return -1
        _logger.warning("Inspector resource selection for kind '%s' has no UUID", self.kind)
        return -1


class InspectorResourceCatalog:
    def __init__(self, resource_manager) -> None:
        self._resource_manager = resource_manager

    @property
    def resource_manager(self):
        return self._resource_manager

    def choices(self, kind: str) -> InspectorResourceChoices | None:
        uuid_only = kind in ("sprite_asset", "sprite_animation_clip")
        if uuid_only:
            # These native component fields expose UUID strings to the inspector.
            records = self._resource_manager.external_assets.iter_records(kind)
            resources = sorted((record.name, record.uuid) for record in records)
            allow_none, can_create = True, False
        else:
            accessors = self._resource_manager.get_handle_accessors(kind)
            if accessors is None:
                return None
            try:
                resources = accessors.list_items()
            except Exception:
                _logger.exception("Failed to list inspector resources for kind '%s'", kind)
                raise
            allow_none, can_create = accessors.allow_none, accessors.create_item is not None
        items = []
        if allow_none:
            items.append(InspectorResourceChoice("(None)", None, None, uuid_only))
        name_counts: dict[str, int] = {}
        for name, _uuid in resources:
            name_counts[name] = name_counts.get(name, 0) + 1
        for name, uuid in resources:
            if not uuid:
                _logger.error("Skipping inspector resource '%s' for kind '%s': missing UUID", name, kind)
                continue
            label = name if name_counts[name] == 1 else f"{name} — {uuid[:8]}"
            items.append(InspectorResourceChoice(label, name, uuid, uuid_only))
        return InspectorResourceChoices(
            kind=kind,
            items=tuple(items),
            can_create=can_create,
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
        if not uuid:
            _logger.error("Created inspector resource '%s' for kind '%s' has no UUID", name, kind)
            return None
        return InspectorResourceChoice(name, name, uuid)


__all__ = [
    "InspectorResourceCatalog",
    "InspectorResourceChoice",
    "InspectorResourceChoices",
]
