"""File preload data shared by watchers and asset plugins."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AssetIdentityPolicy(Enum):
    """How an import result obtains its persistent file identity."""

    REQUIRE_EXISTING = "require_existing"
    GENERATE_SIDECAR = "generate_sidecar"


@dataclass(frozen=True, slots=True)
class AssetRegistration:
    """Canonical identity owned by one registered source file."""

    type_id: str
    uuid: str
    name: str


@dataclass
class PreLoadResult:
    """Result of pre-loading a file before asset registration."""

    resource_type: str
    path: str
    content: str | bytes | None = None
    uuid: str | None = None
    spec_data: dict | None = None
    identity_policy: AssetIdentityPolicy = AssetIdentityPolicy.REQUIRE_EXISTING
    extra: dict = field(default_factory=dict)
