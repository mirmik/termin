"""Identifiable base class for objects with UUID."""

from __future__ import annotations

import uuid as uuid_module


class Identifiable:
    """
    Base class for objects that need unique identification.

    Provides:
    - uuid: str - unique identifier for serialization
    - runtime_id: int - 64-bit hash for fast runtime lookup
    """

    def __init__(self, uuid: str | None = None):
        if uuid is None:
            self._uuid = str(uuid_module.uuid4())
        else:
            self._uuid = uuid
        self._runtime_id = hash(self._uuid) & 0xFFFFFFFFFFFFFFFF
        self._identity_locked = False

    @property
    def uuid(self) -> str:
        """Unique identifier for serialization."""
        return self._uuid

    @property
    def runtime_id(self) -> int:
        """64-bit hash of UUID for fast runtime lookup."""
        return self._runtime_id

    def _adopt_uuid(self, uuid: str) -> None:
        """Set declared identity before registration, or validate it afterwards."""
        if self._identity_locked and uuid != self._uuid:
            raise ValueError(
                f"Registered UUID identity is immutable: {self._uuid} != {uuid}"
            )
        self._uuid = uuid
        self._runtime_id = hash(uuid) & 0xFFFFFFFFFFFFFFFF

    def _lock_identity(self) -> None:
        self._identity_locked = True
