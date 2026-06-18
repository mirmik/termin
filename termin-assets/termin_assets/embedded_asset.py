"""Contracts for assets embedded inside container assets."""

from __future__ import annotations

from dataclasses import dataclass

from termin_assets.asset import Asset


@dataclass(frozen=True)
class EmbeddedAssetSpec:
    """Description of a child asset owned by another asset file."""

    type_id: str
    name: str
    parent: Asset
    parent_key: str
    source_path: str | None = None
    uuid: str | None = None
