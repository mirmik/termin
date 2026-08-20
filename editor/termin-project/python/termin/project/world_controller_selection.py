"""Canonical optional WorldController selection stored in project settings."""

from __future__ import annotations

from dataclasses import dataclass


class WorldControllerSelectionError(ValueError):
    """An explicit WorldController selection does not match its strict schema."""


@dataclass(frozen=True)
class ProjectWorldControllerSelection:
    """Exact project module and runtime type used to create a WorldController."""

    module: str
    type_name: str

    def __post_init__(self) -> None:
        _require_normalized_nonempty_string(
            self.module,
            field_name="world_controller.module",
        )
        _require_normalized_nonempty_string(
            self.type_name,
            field_name="world_controller.type",
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "module": self.module,
            "type": self.type_name,
        }

    @staticmethod
    def from_dict(data: object) -> "ProjectWorldControllerSelection | None":
        if data is None:
            return None
        if not isinstance(data, dict):
            raise WorldControllerSelectionError(
                "world_controller must be null or an object"
            )

        required = {"module", "type"}
        actual = set(data)
        missing = sorted(required - actual)
        unexpected = sorted(actual - required)
        if missing:
            raise WorldControllerSelectionError(
                "world_controller is missing required field(s): " + ", ".join(missing)
            )
        if unexpected:
            raise WorldControllerSelectionError(
                "world_controller has unexpected field(s): " + ", ".join(unexpected)
            )

        return ProjectWorldControllerSelection(
            module=_normalized_nonempty_string(
                data["module"],
                field_name="world_controller.module",
            ),
            type_name=_normalized_nonempty_string(
                data["type"],
                field_name="world_controller.type",
            ),
        )


def create_selected_world_controller(
    selection: ProjectWorldControllerSelection | None,
):
    """Create the exact selected controller, or return ``None`` for absence.

    Module publication must already be complete. An explicit selection is
    strict: a same-named type owned by another module is an error.
    """
    if selection is None:
        return None
    if not isinstance(selection, ProjectWorldControllerSelection):
        raise TypeError(
            "selection must be ProjectWorldControllerSelection or None"
        )
    from termin.engine import create_world_controller

    return create_world_controller(selection.type_name, selection.module)


def _normalized_nonempty_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise WorldControllerSelectionError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise WorldControllerSelectionError(
            f"{field_name} must be a non-empty string"
        )
    return normalized


def _require_normalized_nonempty_string(value: object, *, field_name: str) -> None:
    normalized = _normalized_nonempty_string(value, field_name=field_name)
    if value != normalized:
        raise WorldControllerSelectionError(
            f"{field_name} must not have leading or trailing whitespace"
        )


__all__ = [
    "ProjectWorldControllerSelection",
    "WorldControllerSelectionError",
    "create_selected_world_controller",
]
