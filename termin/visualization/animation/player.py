from __future__ import annotations

from typing import Dict, Optional

import numpy as np

from ..entity import Component
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
            # можно заменить на логгер, если он есть
            print(f"[AnimationPlayer] clip '{name}' not found")
            return

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

        tr, rot, sc = self.current.sample(self.time)

        pose: Pose3 = self.entity.transform.local_pose()

        if tr is not None and rot is None:
            pose = Pose3(lin=np.asarray(tr, dtype=float), ang=pose.ang)
        elif rot is not None and tr is None:
            pose = Pose3(lin=pose.lin, ang=np.asarray(rot, dtype=float))
        elif tr is not None and rot is not None:
            pose = Pose3(lin=np.asarray(tr, dtype=float), ang=np.asarray(rot, dtype=float))

        # сначала обновляем позу
        self.entity.transform.relocate(pose)

        # scale — отдельное поле у Entity, используем uniform-скейл
        if sc is not None:
            self.entity.scale = float(sc)
