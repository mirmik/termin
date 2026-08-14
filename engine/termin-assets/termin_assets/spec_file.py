"""Helpers for asset .meta sidecar files."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import uuid as uuid_module
from pathlib import Path

logger = logging.getLogger(__name__)


def read_spec_file(path: str) -> dict | None:
    """Read a resource .meta sidecar file."""
    meta_path = path + ".meta"
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                spec_data = json.load(f)
            if not isinstance(spec_data, dict):
                logger.error("Asset meta file must contain a JSON object: %s", meta_path)
                return None
            return spec_data
        except Exception:
            logger.warning("Failed to read asset meta file: %s", meta_path, exc_info=True)

    return None


def write_spec_file(path: str, data: dict) -> bool:
    """Atomically write a resource .meta sidecar."""
    meta_path = Path(path + ".meta")
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=meta_path.parent,
            prefix=f".{meta_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as output:
            temp_path = Path(output.name)
            json.dump(data, output, indent=2, ensure_ascii=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp_path, meta_path)
        return True
    except Exception:
        logger.error("Failed to write asset meta file: %s", meta_path, exc_info=True)
        return False
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                logger.warning("Failed to remove temporary asset meta file: %s", temp_path)


def ensure_uuid_in_spec(path: str) -> tuple[str, dict] | None:
    """Return a persistent sidecar UUID, creating it when metadata is absent."""
    meta_path = Path(path + ".meta")
    spec_data = read_spec_file(path)
    if meta_path.exists() and spec_data is None:
        logger.error("Cannot assign asset UUID because metadata is invalid: %s", meta_path)
        return None
    if spec_data is None:
        spec_data = {}

    existing_uuid = spec_data.get("uuid")
    if existing_uuid is not None:
        if isinstance(existing_uuid, str) and existing_uuid.strip() == existing_uuid and existing_uuid:
            return existing_uuid, spec_data
        logger.error("Invalid asset UUID in metadata: %s", meta_path)
        return None

    generated_uuid = str(uuid_module.uuid4())
    updated_spec = dict(spec_data)
    updated_spec["uuid"] = generated_uuid
    if not write_spec_file(path, updated_spec):
        return None
    return generated_uuid, updated_spec


def get_uuid_from_spec(path: str) -> str | None:
    """Read a resource UUID from its .meta sidecar."""
    spec_data = read_spec_file(path)
    if spec_data:
        uuid = spec_data.get("uuid")
        if isinstance(uuid, str):
            return uuid
    return None
