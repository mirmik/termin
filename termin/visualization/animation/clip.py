# Re-export native AnimationClip
from __future__ import annotations

from ._animation_native import AnimationClip, deserialize_clip
from .channel import channel_from_fbx, channel_from_glb


def clip_from_fbx(fbx_clip) -> AnimationClip:
    """
    Создаёт AnimationClip из FBXAnimationClip.

    Args:
        fbx_clip: FBXAnimationClip из fbx_loader
    """
    channels = {}
    for ch in fbx_clip.channels:
        channels[ch.node_name] = channel_from_fbx(ch)

    return AnimationClip(
        fbx_clip.name,
        channels,
        fbx_clip.ticks_per_second or 30.0,
        True,  # loop
    )


def clip_from_glb(glb_clip) -> AnimationClip:
    """
    Создаёт AnimationClip из GLBAnimationClip.

    Args:
        glb_clip: GLBAnimationClip из glb_loader
    """
    channels = {}
    for ch in glb_clip.channels:
        channels[ch.node_name] = channel_from_glb(ch)

    return AnimationClip(
        glb_clip.name,
        channels,
        1.0,  # GLB использует секунды напрямую
        True,  # loop
    )


__all__ = ["AnimationClip", "clip_from_fbx", "clip_from_glb", "deserialize_clip"]
