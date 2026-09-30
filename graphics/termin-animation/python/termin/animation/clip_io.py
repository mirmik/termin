"""Versioned, self-contained .tanim files (distinct from resource references)."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import tempfile
from typing import TYPE_CHECKING

from termin.base import log

if TYPE_CHECKING:
    from ._animation_native import TcAnimationClip


_FORMAT = "termin.animation"
_VERSION = 1
_METADATA = {"format", "version", "uuid", "name", "tps", "loop"}
_TRACK_FIELDS = {"target_node_index", "path", "interpolation", "components", "times", "values"}
_CHANNEL_FIELDS = {"target_name", "translation_keys", "rotation_keys", "scale_keys"}


def _object_fields(value: object, fields: set[str], location: str) -> dict:
    if type(value) is not dict or value.keys() != fields:
        raise ValueError(f"{location} must be an object with exactly these fields: {', '.join(sorted(fields))}")
    return value


def _text(value: object, location: str, *, max_bytes: int | None = None, nonempty: bool = False) -> str:
    if type(value) is not str or "\0" in value or (nonempty and not value):
        raise ValueError(f"{location} must be {'a nonempty' if nonempty else 'a'} string without NUL")
    encoded = value.encode("utf-8")
    if max_bytes is not None and len(encoded) > max_bytes:
        raise ValueError(f"{location} exceeds {max_bytes} UTF-8 bytes")
    return value


def _number(value: object, location: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{location} must be a finite number")
    return value


def _array(value: object, location: str) -> list:
    if type(value) is not list:
        raise ValueError(f"{location} must be an array")
    return value


def _numbers(value: object, location: str, count: int | None = None) -> list:
    result = _array(value, location)
    if count is not None and len(result) != count:
        raise ValueError(f"{location} must contain {count} numbers")
    for number in result:
        _number(number, location)
    return result


def _tracks(data: object) -> list:
    tracks = _array(data, "tracks")
    for index, track in enumerate(tracks):
        location = f"tracks[{index}]"
        _object_fields(track, _TRACK_FIELDS, location)
        target = track["target_node_index"]
        if type(target) is not int or not 0 <= target <= 2**31 - 1:
            raise ValueError(f"{location}.target_node_index must be a nonnegative int32")
        components = track["components"]
        if type(components) is not int or not 1 <= components <= 2**32 - 1:
            raise ValueError(f"{location}.components must be a positive uint32")
        _text(track["path"], f"{location}.path")
        _text(track["interpolation"], f"{location}.interpolation")
        _numbers(track["times"], f"{location}.times")
        _numbers(track["values"], f"{location}.values")
    # Native publication validates layout, enums, key ordering and rotations.
    return tracks


def _channels(data: object) -> list:
    from termin.geombase import Quat, Vec3

    channels = []
    for index, channel in enumerate(_array(data, "channels")):
        location = f"channels[{index}]"
        _object_fields(channel, _CHANNEL_FIELDS, location)
        result = {"target_name": _text(channel["target_name"], f"{location}.target_name", max_bytes=63)}
        for field, components, constructor in (
            ("translation_keys", 3, Vec3), ("rotation_keys", 4, Quat), ("scale_keys", None, None),
        ):
            keys = []
            for key in _array(channel[field], f"{location}.{field}"):
                _array(key, f"{location}.{field} key")
                if len(key) != 2:
                    raise ValueError(f"{location}.{field} key must contain time and value")
                time = _number(key[0], f"{location}.{field} time")
                if constructor is None:
                    value = _number(key[1], f"{location}.{field} value")
                else:
                    value = constructor(*_numbers(key[1], f"{location}.{field} value", components))
                keys.append((time, value))
            result[field] = keys
        channels.append(result)
    return channels


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def _decode(content: str, uuid_hint: str) -> "TcAnimationClip":
    from ._animation_native import TcAnimationClip

    data = json.loads(content, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    if type(data) is not dict or data.get("format") != _FORMAT:
        raise ValueError("expected a versioned .tanim payload; resource references cannot restore animation data; re-extract the source")
    if type(data.get("version")) is not int or data["version"] != _VERSION:
        raise ValueError(f"unsupported .tanim version: {data.get('version')!r}")
    payload = "tracks" if "tracks" in data else "channels"
    _object_fields(data, _METADATA | {payload}, ".tanim")
    uuid = _text(data["uuid"], "uuid", max_bytes=63, nonempty=True)
    name = _text(data["name"], "name")
    tps = _number(data["tps"], "tps")
    if tps <= 0:
        raise ValueError("tps must be positive")
    if type(data["loop"]) is not bool:
        raise ValueError("loop must be a boolean")
    _text(uuid_hint, "uuid_hint", max_bytes=63)
    uuid = uuid_hint or uuid
    if payload == "tracks":
        return TcAnimationClip.publish_tracks(name, uuid, tps, data["loop"], _tracks(data[payload]))
    return TcAnimationClip.publish_channels(name, uuid, tps, data["loop"], _channels(data[payload]))


def save_animation_clip(clip: "TcAnimationClip", path: str | Path) -> None:
    """Save the full loaded clip, replacing the file only after encoding succeeds."""
    path = Path(path)
    temporary = None
    try:
        if not clip.ensure_loaded():
            raise ValueError("cannot save an invalid or unloaded animation clip")
        data = {
            "format": _FORMAT, "version": _VERSION, "uuid": clip.uuid,
            "name": clip.name, "tps": clip.tps, "loop": clip.loop,
        }
        if clip.channel_count:
            data["channels"] = clip.channels
        else:
            data["tracks"] = clip.tracks
        content = json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            output.write(content)
        os.replace(temporary, path)
        temporary = None
    except Exception as exc:
        log.error(f"[AnimationClipIO] Failed to save '{path}': {exc}")
        raise
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_animation_clip(path: str | Path, *, uuid_hint: str = "") -> "TcAnimationClip":
    """Load a complete file, updating an existing UUID only after full validation."""
    path = Path(path)
    try:
        return _decode(path.read_text(encoding="utf-8"), uuid_hint)
    except Exception as exc:
        log.error(f"[AnimationClipIO] Failed to load '{path}': {exc}")
        raise ValueError(f"Invalid .tanim file '{path}': {exc}") from exc


def parse_animation_content(content: str, *, uuid_hint: str = "") -> "TcAnimationClip":
    """Parse a full payload; uuid_hint is the authoritative identity of an asset."""
    try:
        return _decode(content, uuid_hint)
    except Exception as exc:
        log.error(f"[AnimationClipIO] Failed to parse .tanim: {exc}")
        raise ValueError(f"Invalid .tanim content: {exc}") from exc


__all__ = ["save_animation_clip", "load_animation_clip", "parse_animation_content"]
