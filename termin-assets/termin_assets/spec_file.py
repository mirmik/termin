"""Helpers for asset .meta sidecar files."""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)


def read_spec_file(path: str) -> dict | None:
    """Read a resource .meta sidecar file."""
    meta_path = path + ".meta"
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            logger.warning("Failed to read asset meta file: %s", meta_path, exc_info=True)

    return None


def write_spec_file(path: str, data: dict) -> bool:
    """Write a resource .meta sidecar and remove a legacy .spec sidecar."""
    meta_path = path + ".meta"
    try:
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        old_spec_path = path + ".spec"
        if os.path.exists(old_spec_path):
            try:
                os.remove(old_spec_path)
            except Exception:
                logger.warning(
                    "Failed to remove legacy asset spec file: %s",
                    old_spec_path,
                    exc_info=True,
                )

        return True
    except Exception:
        logger.error("Failed to write asset meta file: %s", meta_path, exc_info=True)
        return False


def get_uuid_from_spec(path: str) -> str | None:
    """Read a resource UUID from its .meta sidecar."""
    spec_data = read_spec_file(path)
    if spec_data:
        uuid = spec_data.get("uuid")
        if isinstance(uuid, str):
            return uuid
    return None
