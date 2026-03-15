"""Canonical animation core API."""

from termin import _dll_setup  # noqa: F401

_dll_setup.extend_package_path(__path__, "visualization", "animation")

from termin.animation.channel import channel_data_from_fbx, channel_data_from_glb
from termin.animation.clip import TcAnimationClip, clip_from_fbx, clip_from_glb
from termin.animation.clip_io import load_animation_clip, parse_animation_content, save_animation_clip

__all__ = [
    "TcAnimationClip",
    "clip_from_fbx",
    "clip_from_glb",
    "channel_data_from_fbx",
    "channel_data_from_glb",
    "save_animation_clip",
    "load_animation_clip",
    "parse_animation_content",
]
