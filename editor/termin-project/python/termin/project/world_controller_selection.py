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
]
