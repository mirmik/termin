from __future__ import annotations

from typing import Dict, Optional, TYPE_CHECKING

import numpy as np

from termin.visualization.core.entity import Component
from termin.geombase.pose3 import Pose3
from .clip import AnimationClip

if TYPE_CHECKING:
    from termin.skeleton.skeleton import SkeletonInstance


class AnimationPlayer(Component):
    """
    Компонент-плеер: хранит набор клипов и проигрывает один из них,
    обновляя локальный Pose3 сущности (и её scale).

    Может также обновлять SkeletonInstance для скелетной анимации.
    """

    _DEBUG_UPDATE = False

    def __init__(self, enabled: bool = True):
        super().__init__(enabled=enabled)
        self.clips: Dict[str, AnimationClip] = {}
        self.current: Optional[AnimationClip] = None
        self.time: float = 0.0
        self.playing: bool = False
        self._target_skeleton: "SkeletonInstance | None" = None

    @property
    def target_skeleton(self) -> "SkeletonInstance | None":
        """Get target skeleton for bone animation."""
        return self._target_skeleton

    @target_skeleton.setter
    def target_skeleton(self, value: "SkeletonInstance | None"):
        """Set target skeleton for bone animation."""
        self._target_skeleton = value

    def add_clip(self, clip: AnimationClip) -> AnimationClip:
        self.clips[clip.name] = clip
        return clip

    def play(self, name: str, restart: bool = True):
        clip = self.clips.get(name)
        if clip is None:
            raise KeyError(f"[AnimationPlayer] clip '{name}' not found")

        if self.current is not clip or restart:
            self.time = 0.0

        self.current = clip
        self.playing = True

    def stop(self):
        self.playing = False

    _debug_frame_count = 0

    def update(self, dt: float):
        if not (self.enabled and self.playing and self.current):
            return

        self.time += dt

        sample = self.current.sample(self.time)

        if self._DEBUG_UPDATE and AnimationPlayer._debug_frame_count < 3:
            AnimationPlayer._debug_frame_count += 1
            print(f"[AnimationPlayer.update] clip={self.current.name!r}, duration={self.current.duration:.3f}s, time={self.time:.3f}")
            print(f"  channels={len(sample)}, target_skeleton={self._target_skeleton is not None}")
            for name, data in list(sample.items())[:3]:
                tr, rot, sc = data
                print(f"  {name}: tr={tr}, rot={rot}")

        # If we have a target skeleton, apply bone transforms
        if self._target_skeleton is not None:
            self._update_skeleton(sample)

        # Also update entity transform if entity is set (for root motion, etc.)
        if self.entity is not None:
            self._update_entity(sample)

    _debug_skeleton_frame = 0

    def _update_skeleton(self, sample: Dict):
        """Update skeleton bone transforms from animation sample."""
        found_count = 0
        for channel_name, channel_data in sample.items():
            tr = channel_data[0]  # translation
            rot = channel_data[1]  # rotation (quaternion xyzw)
            sc = channel_data[2]  # scale (float or None)

            # Check if bone exists before setting
            bone_idx = self._target_skeleton._data.get_bone_index(channel_name)
            if bone_idx >= 0:
                found_count += 1

            # Set bone transform
            self._target_skeleton.set_bone_transform_by_name(
                channel_name,
                translation=tr,
                rotation=rot,
                scale=sc,  # Already a float from AnimationChannel.sample()
            )

        if self._DEBUG_UPDATE and AnimationPlayer._debug_skeleton_frame < 3:
            AnimationPlayer._debug_skeleton_frame += 1
            skeleton_bones = [b.name for b in self._target_skeleton._data.bones[:5]]
            sample_channels = list(sample.keys())[:5]
            print(f"[_update_skeleton] found {found_count}/{len(sample)} channels matching bones")
            print(f"  skeleton bones[:5]: {skeleton_bones}")
            print(f"  sample channels[:5]: {sample_channels}")

    def _update_entity(self, sample: Dict):
        """Update entity transform from animation sample (legacy mode)."""
        # Look for "clip" channel (legacy single-channel mode)
        if "clip" not in sample:
            return

        channel_data = sample["clip"]

        pose: Pose3 = self.entity.transform.local_pose()

        tr = channel_data[0]
        rot = channel_data[1]
        sc = channel_data[2]

        if tr is not None:
            pose = pose.with_translation(tr)
        if rot is not None:
            pose = pose.with_rotation(rot)

        # Update pose
        self.entity.transform.relocate(pose)

        # Scale is a separate field on Entity
        if sc is not None:
            self.entity.scale = float(sc[0]) if hasattr(sc, '__len__') else float(sc)
