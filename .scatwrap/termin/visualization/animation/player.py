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
&#9;&quot;&quot;&quot;<br>
&#9;Компонент-плеер: хранит набор клипов и проигрывает один из них,<br>
&#9;обновляя локальный Pose3 сущности (и её scale).<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, enabled: bool = True):<br>
&#9;&#9;super().__init__(enabled=enabled)<br>
&#9;&#9;self.clips: Dict[str, AnimationClip] = {}<br>
&#9;&#9;self.current: Optional[AnimationClip] = None<br>
&#9;&#9;self.time: float = 0.0<br>
&#9;&#9;self.playing: bool = False<br>
<br>
&#9;def add_clip(self, clip: AnimationClip) -&gt; AnimationClip:<br>
&#9;&#9;self.clips[clip.name] = clip<br>
&#9;&#9;return clip<br>
<br>
&#9;def play(self, name: str, restart: bool = True):<br>
&#9;&#9;clip = self.clips.get(name)<br>
&#9;&#9;if clip is None:<br>
&#9;&#9;&#9;# можно заменить на логгер, если он есть<br>
&#9;&#9;&#9;print(f&quot;[AnimationPlayer] clip '{name}' not found&quot;)<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;if self.current is not clip or restart:<br>
&#9;&#9;&#9;self.time = 0.0<br>
<br>
&#9;&#9;self.current = clip<br>
&#9;&#9;self.playing = True<br>
<br>
&#9;def stop(self):<br>
&#9;&#9;self.playing = False<br>
<br>
&#9;def update(self, dt: float):<br>
&#9;&#9;if not (self.enabled and self.playing and self.current and self.entity):<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;self.time += dt<br>
<br>
&#9;&#9;sample = self.current.sample(self.time)<br>
<br>
&#9;&#9;pose: Pose3 = self.entity.transform.local_pose()<br>
<br>
&#9;&#9;<br>
&#9;&#9;sample = self.current.sample(self.time)<br>
&#9;&#9;<br>
&#9;&#9;# TODO: Разобраться с тем, как передать в плеер несколько каналов и к чему они должны применяться.<br>
&#9;&#9;sample = sample[&quot;clip&quot;]<br>
<br>
&#9;&#9;tr = sample[0]<br>
&#9;&#9;rot = sample[1]<br>
&#9;&#9;sc = sample[2]<br>
<br>
&#9;&#9;if tr is not None:<br>
&#9;&#9;&#9;pose = pose.with_translation(tr)<br>
&#9;&#9;if rot is not None:<br>
&#9;&#9;&#9;pose = pose.with_rotation(rot)<br>
&#9;&#9;sc = sample[2]<br>
<br>
&#9;&#9;# сначала обновляем позу<br>
&#9;&#9;self.entity.transform.relocate(pose)<br>
<br>
&#9;&#9;# scale — отдельное поле у Entity, используем uniform-скейл<br>
&#9;&#9;if sc is not None:<br>
&#9;&#9;&#9;self.entity.scale = float(sc)<br>
<!-- END SCAT CODE -->
</body>
</html>
