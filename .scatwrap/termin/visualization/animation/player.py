<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/animation/player.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from __future__ import annotations<br>
<br>
from typing import Dict, Optional<br>
<br>
import numpy as np<br>
<br>
from ..entity import Component<br>
from termin.geombase.pose3 import Pose3<br>
from .clip import AnimationClip<br>
<br>
<br>
class AnimationPlayer(Component):<br>
    &quot;&quot;&quot;<br>
    Компонент-плеер: хранит набор клипов и проигрывает один из них,<br>
    обновляя локальный Pose3 сущности (и её scale).<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(self, enabled: bool = True):<br>
        super().__init__(enabled=enabled)<br>
        self.clips: Dict[str, AnimationClip] = {}<br>
        self.current: Optional[AnimationClip] = None<br>
        self.time: float = 0.0<br>
        self.playing: bool = False<br>
<br>
    def add_clip(self, clip: AnimationClip) -&gt; AnimationClip:<br>
        self.clips[clip.name] = clip<br>
        return clip<br>
<br>
    def play(self, name: str, restart: bool = True):<br>
        clip = self.clips.get(name)<br>
        if clip is None:<br>
            # можно заменить на логгер, если он есть<br>
            print(f&quot;[AnimationPlayer] clip '{name}' not found&quot;)<br>
            return<br>
<br>
        if self.current is not clip or restart:<br>
            self.time = 0.0<br>
<br>
        self.current = clip<br>
        self.playing = True<br>
<br>
    def stop(self):<br>
        self.playing = False<br>
<br>
    def update(self, dt: float):<br>
        if not (self.enabled and self.playing and self.current and self.entity):<br>
            return<br>
<br>
        self.time += dt<br>
<br>
        sample = self.current.sample(self.time)<br>
<br>
        pose: Pose3 = self.entity.transform.local_pose()<br>
<br>
        <br>
        sample = self.current.sample(self.time)<br>
        <br>
        # TODO: Разобраться с тем, как передать в плеер несколько каналов и к чему они должны применяться.<br>
        sample = sample[&quot;clip&quot;]<br>
<br>
        tr = sample[0]<br>
        rot = sample[1]<br>
        sc = sample[2]<br>
<br>
        if tr is not None:<br>
            pose = pose.with_translation(tr)<br>
        if rot is not None:<br>
            pose = pose.with_rotation(rot)<br>
        sc = sample[2]<br>
<br>
        # сначала обновляем позу<br>
        self.entity.transform.relocate(pose)<br>
<br>
        # scale — отдельное поле у Entity, используем uniform-скейл<br>
        if sc is not None:<br>
            self.entity.scale = float(sc)<br>
<!-- END SCAT CODE -->
</body>
</html>
