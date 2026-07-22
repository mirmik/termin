"""Canonical application identity shared by project product builds."""

from __future__ import annotations

import re
from dataclasses import dataclass


DEFAULT_APPLICATION_VERSION_CODE = 1
DEFAULT_APPLICATION_VERSION_NAME = "0.1.0"
_APPLICATION_ID_PATTERN = re.compile(
    r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+$"
)
_MAX_ANDROID_VERSION_CODE = 2_100_000_000


@dataclass(frozen=True)
class ProjectApplicationIdentity:
    application_id: str
    label: str
    version_code: int = DEFAULT_APPLICATION_VERSION_CODE
    version_name: str = DEFAULT_APPLICATION_VERSION_NAME

    def to_dict(self) -> dict:
        return {
            "id": self.application_id,
            "label": self.label,
            "version_code": self.version_code,
            "version_name": self.version_name,
        }

    @staticmethod
    def from_dict(
        data: object,
        *,
        project_name: str,
    ) -> "ProjectApplicationIdentity":
        defaults = default_project_application_identity(project_name)
        if data is None:
            return defaults
        if not isinstance(data, dict):
            raise ValueError("application must be an object")

        application_id = data.get("id", defaults.application_id)
        label = data.get("label", defaults.label)
        version_code = data.get("version_code", defaults.version_code)
        version_name = data.get("version_name", defaults.version_name)
        return ProjectApplicationIdentity(
            application_id=_validate_application_id(application_id),
            label=_validate_nonempty_text(label, field_name="application.label"),
            version_code=_validate_version_code(version_code),
            version_name=_validate_nonempty_text(
                version_name,
                field_name="application.version_name",
            ),
        )


def default_project_application_identity(project_name: str) -> ProjectApplicationIdentity:
    label = project_name.strip() or "Termin Project"
    slug = label.lower()
    slug = re.sub(r"[^a-z0-9_]+", ".", slug)
    slug = re.sub(r"\.+", ".", slug).strip(".")
    parts: list[str] = []
    for part in slug.split("."):
        if not part:
            continue
        parts.append(f"p{part}" if part[0].isdigit() else part)
    if not parts:
        parts = ["project"]
    return ProjectApplicationIdentity(
        application_id="org.termin.builds." + ".".join(parts),
        label=label,
    )


def _validate_application_id(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("application.id must be a string")
    application_id = value.strip()
    if not _APPLICATION_ID_PATTERN.fullmatch(application_id):
        raise ValueError(
            "application.id must contain at least two dot-separated Java identifiers"
        )
    return application_id


def _validate_nonempty_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _validate_version_code(value: object) -> int:
    if type(value) is not int or not 1 <= value <= _MAX_ANDROID_VERSION_CODE:
        raise ValueError(
            f"application.version_code must be an integer from 1 to {_MAX_ANDROID_VERSION_CODE}"
        )
    return value
