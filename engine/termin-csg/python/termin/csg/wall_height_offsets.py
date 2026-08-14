"""Helpers for variable-height wall corner offsets."""

from __future__ import annotations

from tcbase import log

from termin.csg.procedural_document import OPERATION_KIND_WALL, OperationDocument, ProceduralMeshDocument

CORNER_HEIGHT_OFFSETS_PARAM = "corner_height_offsets"
MIN_WALL_CORNER_HEIGHT = 0.001


def wall_corner_height_offsets(
    params: dict,
    source_id: str,
    point_count: int,
    *,
    operation_id: str = "",
) -> list[float]:
    count = int(point_count)
    if count <= 0:
        return []
    raw_offsets = params.get(CORNER_HEIGHT_OFFSETS_PARAM)
    if raw_offsets is None:
        return [0.0] * count
    if not isinstance(raw_offsets, dict):
        log.error(
            "[CsgWallHeightOffsets] invalid corner height offsets: "
            f"expected dict operation='{operation_id}'"
        )
        return [0.0] * count
    source_offsets = raw_offsets.get(str(source_id))
    if source_offsets is None:
        return [0.0] * count
    if not isinstance(source_offsets, list):
        log.error(
            "[CsgWallHeightOffsets] invalid source corner height offsets: "
            f"expected list operation='{operation_id}' source='{source_id}'"
        )
        return [0.0] * count

    offsets: list[float] = []
    for index in range(count):
        if index >= len(source_offsets):
            offsets.append(0.0)
            continue
        try:
            offsets.append(float(source_offsets[index]))
        except Exception as e:
            log.error(
                "[CsgWallHeightOffsets] invalid corner height offset: "
                f"operation='{operation_id}' source='{source_id}' index={index}: {e}"
            )
            offsets.append(0.0)
    if len(source_offsets) != count:
        log.error(
            "[CsgWallHeightOffsets] corner height offset count mismatch: "
            f"operation='{operation_id}' source='{source_id}' offsets={len(source_offsets)} points={count}"
        )
    return offsets


def wall_effective_corner_heights(
    params: dict,
    source_id: str,
    point_count: int,
    base_height: float,
    *,
    operation_id: str = "",
) -> list[float]:
    offsets = wall_corner_height_offsets(params, source_id, point_count, operation_id=operation_id)
    return [float(base_height) + offset for offset in offsets]


def set_wall_corner_height_offset(
    document: ProceduralMeshDocument,
    operation_id: str,
    source_id: str,
    point_index: int,
    offset: float,
) -> bool:
    operation = document.find_operation(operation_id)
    if operation is None:
        log.error(f"[CsgWallHeightOffsets] cannot set wall corner offset: operation not found '{operation_id}'")
        return False
    return set_operation_wall_corner_height_offset(operation, source_id, point_index, offset)


def set_operation_wall_corner_height_offset(
    operation: OperationDocument,
    source_id: str,
    point_index: int,
    offset: float,
) -> bool:
    if operation.kind != OPERATION_KIND_WALL:
        log.error(
            "[CsgWallHeightOffsets] cannot set wall corner offset: "
            f"operation '{operation.id}' has kind '{operation.kind}'"
        )
        return False
    index = int(point_index)
    if index < 0:
        log.error(
            "[CsgWallHeightOffsets] cannot set wall corner offset: "
            f"negative index operation='{operation.id}' source='{source_id}' index={index}"
        )
        return False
    base_height = _param_float(operation.params, "height", 3.0)
    next_offset = float(offset)
    if base_height + next_offset < MIN_WALL_CORNER_HEIGHT:
        log.error(
            "[CsgWallHeightOffsets] cannot set wall corner offset: "
            f"effective height must stay positive operation='{operation.id}' "
            f"source='{source_id}' index={index} height={base_height + next_offset:.6f}"
        )
        return False

    raw_offsets = operation.params.get(CORNER_HEIGHT_OFFSETS_PARAM)
    if raw_offsets is None:
        offsets_by_source: dict[str, list[float]] = {}
    elif isinstance(raw_offsets, dict):
        offsets_by_source = _copy_offsets_by_source(raw_offsets, operation.id)
    else:
        log.error(
            "[CsgWallHeightOffsets] replacing invalid corner height offsets container "
            f"operation='{operation.id}'"
        )
        offsets_by_source = {}

    source_key = str(source_id)
    offsets = offsets_by_source.get(source_key, [])
    while len(offsets) <= index:
        offsets.append(0.0)
    offsets[index] = next_offset
    offsets_by_source[source_key] = offsets
    operation.params[CORNER_HEIGHT_OFFSETS_PARAM] = offsets_by_source
    return True


def _param_float(params: dict, key: str, default: float) -> float:
    try:
        return float(params.get(key, default))
    except Exception:
        return float(default)


def _copy_offsets_by_source(raw_offsets: dict, operation_id: str) -> dict[str, list[float]]:
    result: dict[str, list[float]] = {}
    for key, value in raw_offsets.items():
        if not isinstance(value, list):
            log.error(
                "[CsgWallHeightOffsets] skipping invalid source corner height offsets "
                f"operation='{operation_id}' source='{key}'"
            )
            continue
        offsets: list[float] = []
        for index, item in enumerate(value):
            try:
                offsets.append(float(item))
            except Exception as e:
                log.error(
                    "[CsgWallHeightOffsets] replacing invalid corner height offset "
                    f"operation='{operation_id}' source='{key}' index={index}: {e}"
                )
                offsets.append(0.0)
        result[str(key)] = offsets
    return result


__all__ = [
    "CORNER_HEIGHT_OFFSETS_PARAM",
    "MIN_WALL_CORNER_HEIGHT",
    "set_operation_wall_corner_height_offset",
    "set_wall_corner_height_offset",
    "wall_corner_height_offsets",
    "wall_effective_corner_heights",
]
