from __future__ import annotations

from typing import Dict, Optional

import numpy as np

from termin.visualization.core.entity import Component
from termin.geombase.pose3 import Pose3
from .clip import AnimationClip


class AnimationPlayer(Component):
    """
    Компонент-плеер: хранит набор клипов и проигрывает один из них,
    обновляя локальный Pose3 сущности (и её scale).
    """

    def __init__(self, enabled: bool = True):
        super().__init__(enabled=enabled)
        self.clips: Dict[str, AnimationClip] = {}
        self.current: Optional[AnimationClip] = None
        self.time: float = 0.0
        self.playing: bool = False

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

    def update(self, dt: float):
        if not (self.enabled and self.playing and self.current and self.entity):
            return

        self.time += dt

        sample = self.current.sample(self.time)

        pose: Pose3 = self.entity.transform.local_pose()

        
        sample = self.current.sample(self.time)
        
        # TODO: Разобраться с тем, как передать в плеер несколько каналов и к чему они должны применяться.
        sample = sample["clip"]

        tr = sample[0]
        rot = sample[1]
        sc = sample[2]

        if tr is not None:
            pose = pose.with_translation(tr)
        if rot is not None:
            pose = pose.with_rotation(rot)
        sc = sample[2]

        # сначала обновляем позу
        self.entity.transform.relocate(pose)

        # scale — отдельное поле у Entity, используем uniform-скейл
        if sc is not None:
            self.entity.scale = float(sc)
