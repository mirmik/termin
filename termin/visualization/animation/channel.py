# Re-export native AnimationChannel
from __future__ import annotations

import numpy as np

from ._animation_native import AnimationChannel, AnimationKeyframe, deserialize_channel


def channel_from_fbx(ch) -> AnimationChannel:
    """
    Создаёт AnimationChannel из FBXAnimationChannel.

    Args:
        ch: FBXAnimationChannel с pos_keys, rot_keys, scale_keys в тиках
            rot_keys содержат Euler углы (в градусах) которые конвертируются в кватернионы
    """
    from termin.geombase import Pose3

    tr_keys = []
    for (t, v) in ch.pos_keys:
        tr_keys.append((t, np.array(v, dtype=np.float64)))

    rot_keys = []
    for (t, v) in ch.rot_keys:
        rad = np.radians(v)
        pose = Pose3.from_euler(rad[0], rad[1], rad[2], order='xyz')
        rot_keys.append((t, pose.ang))

    sc_keys = [(t, float(np.mean(v))) for (t, v) in ch.scale_keys]

    return AnimationChannel(tr_keys, rot_keys, sc_keys)


def channel_from_glb(ch) -> AnimationChannel:
    """
    Создаёт AnimationChannel из GLBAnimationChannel.

    Args:
        ch: GLBAnimationChannel с pos_keys, rot_keys, scale_keys
            Время уже в секундах, кватернионы в формате XYZW
    """
    tr_keys = [(t, np.array(v, dtype=np.float64)) for (t, v) in ch.pos_keys]
    rot_keys = [(t, np.array(v, dtype=np.float64)) for (t, v) in ch.rot_keys]
    sc_keys = [(t, float(np.mean(v))) for (t, v) in ch.scale_keys]

    return AnimationChannel(tr_keys, rot_keys, sc_keys)


__all__ = ["AnimationChannel", "AnimationKeyframe", "channel_from_fbx", "channel_from_glb", "deserialize_channel"]
