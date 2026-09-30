# Animation clip helpers
from __future__ import annotations

from ._animation_native import TcAnimationClip
from .channel import channel_data_from_fbx


def clip_from_fbx(fbx_clip, uuid_hint: str = "") -> TcAnimationClip:
    """
    Create TcAnimationClip from FBXAnimationClip.

    Args:
        fbx_clip: FBXAnimationClip from fbx_loader
        uuid_hint: Optional UUID for the clip

    Returns:
        TcAnimationClip
    """
    channels_data = []
    for ch in fbx_clip.channels:
        channels_data.append(channel_data_from_fbx(ch))

    return TcAnimationClip.publish_channels(
        fbx_clip.name, uuid_hint, fbx_clip.ticks_per_second or 30.0, True, channels_data,
    )


def clip_from_glb(glb_clip, uuid_hint: str = "") -> TcAnimationClip:
    """
    Create TcAnimationClip from GLBAnimationClip.

    Args:
        glb_clip: GLBAnimationClip from glb_loader
        uuid_hint: Optional UUID for the clip

    Returns:
        TcAnimationClip
    """
    tracks = [
        {
            "target_node_index": track.node_index,
            "path": track.path,
            "interpolation": track.interpolation,
            "components": track.components,
            "times": track.times,
            "values": track.values.reshape(-1),
        }
        for track in glb_clip.tracks
    ]

    # GLB uses seconds directly. Publish metadata and tracks together so a bad
    # import cannot partially change an existing resource or lazy declaration.
    return TcAnimationClip.publish_tracks(glb_clip.name, uuid_hint, 1.0, True, tracks)


__all__ = ["TcAnimationClip", "clip_from_fbx", "clip_from_glb"]
