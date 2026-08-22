# Animation channel helpers for creating TcAnimationClip from FBX/GLB data
from __future__ import annotations

import math

from termin.geombase import Quat, Vec3


def _vec3(value) -> Vec3:
    return Vec3(value)


def _quat(value) -> Quat:
    return Quat(value)


def _mean3(value) -> float:
    return sum(_vec3(value)) / 3.0


def channel_data_from_fbx(ch) -> dict:
    """
    Create channel data dict from FBXAnimationChannel.

    Args:
        ch: FBXAnimationChannel with pos_keys, rot_keys, scale_keys in ticks
            rot_keys contain Euler angles (in degrees) which are converted to quaternions

    Returns:
        dict with target_name, translation_keys, rotation_keys, scale_keys
    """
    tr_keys = []
    for t, v in ch.pos_keys:
        tr_keys.append((t, _vec3(v)))

    rot_keys = []
    for t, v in ch.rot_keys:
        radians = Vec3(v) * (math.pi / 180.0)
        rot_keys.append((t, Quat.from_euler(radians)))

    sc_keys = [(t, _mean3(v)) for (t, v) in ch.scale_keys]

    return {
        "target_name": ch.node_name,
        "translation_keys": tr_keys,
        "rotation_keys": rot_keys,
        "scale_keys": sc_keys,
    }


def channel_data_from_glb(ch) -> dict:
    """
    Create channel data dict from GLBAnimationChannel.

    Args:
        ch: GLBAnimationChannel with pos_keys, rot_keys, scale_keys
            Time is in seconds, quaternions in XYZW format

    Returns:
        dict with target_name, translation_keys, rotation_keys, scale_keys
    """
    tr_keys = [(t, _vec3(v)) for (t, v) in ch.pos_keys]
    rot_keys = [(t, _quat(v)) for (t, v) in ch.rot_keys]
    sc_keys = [(t, _mean3(v)) for (t, v) in ch.scale_keys]

    return {
        "target_name": ch.node_name,
        "translation_keys": tr_keys,
        "rotation_keys": rot_keys,
        "scale_keys": sc_keys,
    }


__all__ = ["channel_data_from_fbx", "channel_data_from_glb"]
