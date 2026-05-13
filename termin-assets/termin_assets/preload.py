"""File preload data shared by watchers and asset plugins."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PreLoadResult:
    """Result of pre-loading a file before asset registration."""

    resource_type: str
    path: str
    content: str | bytes | None = None
    uuid: str | None = None
    spec_data: dict | None = None
    extra: dict = field(default_factory=dict)
