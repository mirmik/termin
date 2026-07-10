"""Toolkit-neutral registry collection and inspection models."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import logging
from typing import Protocol


_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RegistryRow:
    stable_id: str
    cells: tuple[str, ...]
    details: str
    parent_id: str | None = None


@dataclass(frozen=True)
class RegistrySnapshot:
    rows: tuple[RegistryRow, ...]
    total_count: int
    filter_text: str
    selected_id: str | None
    selected_details: str
    revision: int

    @property
    def status(self) -> str:
        visible = len(self.rows)
        if self.filter_text:
            return f"Registry entries: {visible} of {self.total_count}"
        return f"Registry entries: {visible}"


@dataclass(frozen=True)
class RegistryContextAction:
    stable_id: str
    label: str
    enabled: bool = True


@dataclass(frozen=True)
class RegistryColumn:
    stable_id: str
    label: str
    width: float | None = None
    stretch: float = 1.0


@dataclass(frozen=True)
class RegistryPage:
    stable_id: str
    label: str
    columns: tuple[RegistryColumn, ...]
    source: "RegistrySource"
    activate: Callable[[RegistryRow], None] | None = None
    hierarchical: bool = False


class RegistrySource(Protocol):
    def load_rows(self) -> Iterable[RegistryRow]: ...


class RegistryCollectionController:
    def __init__(
        self,
        source: RegistrySource,
        *,
        copy_text: Callable[[str], None] | None = None,
        activate: Callable[[RegistryRow], None] | None = None,
    ) -> None:
        self.source = source
        self._copy_text = copy_text
        self._activate = activate
        self._all_rows: tuple[RegistryRow, ...] = ()
        self._filter_text = ""
        self._selected_id: str | None = None
        self._revision = 0

    def refresh(self) -> RegistrySnapshot:
        try:
            rows = tuple(self.source.load_rows())
        except Exception:
            _logger.exception("Failed to refresh registry viewer source")
            raise
        identifiers = [row.stable_id for row in rows]
        if any(not identifier for identifier in identifiers):
            _logger.error("Registry source returned an empty stable id")
            raise ValueError("registry rows require non-empty stable ids")
        if len(set(identifiers)) != len(identifiers):
            _logger.error("Registry source returned duplicate stable ids")
            raise ValueError("registry rows require unique stable ids")
        by_id = {row.stable_id: row for row in rows}
        for row in rows:
            if row.parent_id is not None and row.parent_id not in by_id:
                _logger.error(
                    "Registry row %s references missing parent %s",
                    row.stable_id,
                    row.parent_id,
                )
                raise ValueError("registry row parent must exist in the same snapshot")
            ancestor_ids: set[str] = set()
            current = row
            while current.parent_id is not None:
                if current.parent_id == row.stable_id or current.parent_id in ancestor_ids:
                    _logger.error("Registry hierarchy contains a cycle at %s", row.stable_id)
                    raise ValueError("registry row hierarchy must be acyclic")
                ancestor_ids.add(current.parent_id)
                current = by_id[current.parent_id]
        self._all_rows = rows
        if self._selected_id not in set(identifiers):
            self._selected_id = None
        self._revision += 1
        return self.snapshot()

    def set_filter(self, text: str) -> RegistrySnapshot:
        normalized = text.strip().casefold()
        if normalized != self._filter_text:
            self._filter_text = normalized
            visible = {row.stable_id for row in self._visible_rows()}
            if self._selected_id not in visible:
                self._selected_id = None
            self._revision += 1
        return self.snapshot()

    def select_index(self, index: int) -> RegistrySnapshot:
        rows = self._visible_rows()
        self._selected_id = rows[index].stable_id if 0 <= index < len(rows) else None
        self._revision += 1
        return self.snapshot()

    def activate_index(self, index: int) -> RegistrySnapshot:
        rows = self._visible_rows()
        if not 0 <= index < len(rows):
            return self.select_index(-1)
        row = rows[index]
        self._selected_id = row.stable_id
        if self._activate is not None:
            self._activate(row)
            return self.refresh()
        self._revision += 1
        return self.snapshot()

    def context_actions(self, index: int) -> tuple[RegistryContextAction, ...]:
        valid = 0 <= index < len(self._visible_rows())
        return (
            RegistryContextAction("copy-name", "Copy Name", valid and self._copy_text is not None),
            RegistryContextAction("copy-details", "Copy Details", valid and self._copy_text is not None),
            RegistryContextAction("refresh", "Refresh"),
        )

    def execute_context_action(self, action_id: str, index: int) -> RegistrySnapshot:
        if action_id == "refresh":
            return self.refresh()
        rows = self._visible_rows()
        if not 0 <= index < len(rows):
            _logger.error("Registry context action %s has invalid row %d", action_id, index)
            raise IndexError("registry context action requires a valid row")
        if self._copy_text is None:
            _logger.error("Registry context action %s has no clipboard boundary", action_id)
            raise RuntimeError("registry context action has no clipboard boundary")
        row = rows[index]
        if action_id == "copy-name":
            self._copy_text(row.stable_id)
        elif action_id == "copy-details":
            self._copy_text(row.details)
        else:
            _logger.error("Unknown registry context action: %s", action_id)
            raise ValueError(f"unknown registry context action: {action_id}")
        return self.snapshot()

    def snapshot(self) -> RegistrySnapshot:
        rows = self._visible_rows()
        selected = next(
            (row for row in rows if row.stable_id == self._selected_id),
            None,
        )
        return RegistrySnapshot(
            rows=rows,
            total_count=len(self._all_rows),
            filter_text=self._filter_text,
            selected_id=selected.stable_id if selected is not None else None,
            selected_details=selected.details if selected is not None else "",
            revision=self._revision,
        )

    def _visible_rows(self) -> tuple[RegistryRow, ...]:
        if not self._filter_text:
            return self._all_rows
        matching = {
            row.stable_id
            for row in self._all_rows
            if self._filter_text in "\n".join((row.stable_id, *row.cells, row.details)).casefold()
        }
        if any(row.parent_id is not None for row in self._all_rows):
            by_id = {row.stable_id: row for row in self._all_rows}
            for stable_id in tuple(matching):
                parent_id = by_id[stable_id].parent_id
                while parent_id is not None:
                    matching.add(parent_id)
                    parent_id = by_id[parent_id].parent_id
        return tuple(row for row in self._all_rows if row.stable_id in matching)


class RegistryCatalogController:
    """Coordinates multiple registry collections without depending on a UI toolkit."""

    def __init__(
        self,
        pages: Iterable[RegistryPage],
        *,
        copy_text: Callable[[str], None] | None = None,
    ) -> None:
        self.pages = tuple(pages)
        if not self.pages:
            raise ValueError("registry catalog requires at least one page")
        identifiers = [page.stable_id for page in self.pages]
        if any(not identifier for identifier in identifiers) or len(set(identifiers)) != len(identifiers):
            raise ValueError("registry catalog pages require unique non-empty stable ids")
        for page in self.pages:
            if not page.columns:
                raise ValueError(f"registry catalog page '{page.stable_id}' requires columns")
        self._controllers = tuple(
            RegistryCollectionController(
                page.source,
                copy_text=copy_text,
                activate=page.activate,
            )
            for page in self.pages
        )
        self._current_index = 0

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def current_page(self) -> RegistryPage:
        return self.pages[self._current_index]

    @property
    def current_controller(self) -> RegistryCollectionController:
        return self._controllers[self._current_index]

    def select_page(self, index: int) -> RegistrySnapshot:
        if not 0 <= index < len(self.pages):
            _logger.error("Registry catalog page index is invalid: %d", index)
            raise IndexError("registry catalog page index is invalid")
        self._current_index = index
        return self.current_controller.refresh()

    def refresh(self) -> RegistrySnapshot:
        return self.current_controller.refresh()

    def set_filter(self, text: str) -> RegistrySnapshot:
        return self.current_controller.set_filter(text)

    def select_index(self, index: int) -> RegistrySnapshot:
        return self.current_controller.select_index(index)

    def activate_index(self, index: int) -> RegistrySnapshot:
        return self.current_controller.activate_index(index)

    def context_actions(self, index: int) -> tuple[RegistryContextAction, ...]:
        return self.current_controller.context_actions(index)

    def execute_context_action(self, action_id: str, index: int) -> RegistrySnapshot:
        return self.current_controller.execute_context_action(action_id, index)

    def snapshot(self) -> RegistrySnapshot:
        return self.current_controller.snapshot()


class InspectRegistrySource:
    """Public InspectRegistry adapter used by both native and testable core paths."""

    def __init__(self, registry) -> None:
        self.registry = registry

    def load_rows(self) -> Iterable[RegistryRow]:
        for type_name in sorted(self.registry.types()):
            backend = self.registry.get_type_backend(type_name)
            parent = self.registry.get_type_parent(type_name) or "-"
            own_fields = list(self.registry.fields(type_name))
            all_fields = list(self.registry.all_fields(type_name))
            yield RegistryRow(
                stable_id=type_name,
                cells=(type_name, backend.name, parent, f"{len(own_fields)}/{len(all_fields)}"),
                details=self._format_details(
                    type_name,
                    backend.name,
                    parent,
                    own_fields,
                    all_fields,
                ),
            )

    @staticmethod
    def _format_details(
        type_name: str,
        backend: str,
        parent: str,
        own_fields: list,
        all_fields: list,
    ) -> str:
        lines = [
            type_name,
            "",
            f"Backend: {backend}",
            f"Parent: {parent}",
            f"Own fields: {len(own_fields)}",
            f"Total fields: {len(all_fields)}",
            "",
            "Own Fields",
        ]
        if not own_fields:
            lines.append("  (none)")
        for field in own_fields:
            lines.extend(
                [
                    f"  {field.path}",
                    f"    label: {field.label}",
                    f"    kind: {field.kind}",
                ]
            )
            if field.min is not None or field.max is not None:
                lines.append(f"    range: [{field.min}, {field.max}]")
            if field.step is not None:
                lines.append(f"    step: {field.step}")
            if field.choices:
                choices = ", ".join(f"{choice.value}={choice.label}" for choice in field.choices)
                lines.append(f"    choices: {choices}")
            if not field.is_serializable:
                lines.append("    serializable: no")
            if not field.is_inspectable:
                lines.append("    inspectable: no")
        inherited = [field for field in all_fields if field not in own_fields]
        if inherited:
            lines.extend(("", "Inherited Fields"))
            lines.extend(f"  {field.path} ({field.kind})" for field in inherited)
        return "\n".join(lines)


__all__ = [
    "InspectRegistrySource",
    "RegistryCollectionController",
    "RegistryCatalogController",
    "RegistryColumn",
    "RegistryContextAction",
    "RegistryPage",
    "RegistryRow",
    "RegistrySnapshot",
    "RegistrySource",
]
