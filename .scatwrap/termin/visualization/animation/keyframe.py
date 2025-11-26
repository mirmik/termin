<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/animation/keyframe.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from __future__ import annotations<br>
<br>
from dataclasses import dataclass<br>
from typing import Optional<br>
<br>
import numpy as np<br>
<br>
<br>
@dataclass<br>
class AnimationKeyframe:<br>
    &quot;&quot;&quot;<br>
    Кадр анимации в момент time.<br>
<br>
    Любое из полей может быть None — тогда этот канал анимацией не затрагивается.<br>
    translation: np.array shape (3,)<br>
    rotation:    np.array shape (4,) (кватернион x, y, z, w)<br>
    scale:       float (uniform-скейл)<br>
    &quot;&quot;&quot;<br>
    time: float<br>
    translation: Optional[np.ndarray] = None<br>
    rotation: Optional[np.ndarray] = None<br>
    scale: Optional[float] = None<br>
<br>
    def __post_init__(self):<br>
        self.time = float(self.time)<br>
<br>
        if self.translation is not None:<br>
            self.translation = np.asarray(self.translation, dtype=float)<br>
            if self.translation.shape != (3,):<br>
                raise ValueError(&quot;translation must have shape (3,)&quot;)<br>
<br>
        if self.rotation is not None:<br>
            self.rotation = np.asarray(self.rotation, dtype=float)<br>
            if self.rotation.shape != (4,):<br>
                raise ValueError(&quot;rotation (quaternion) must have shape (4,)&quot;)<br>
<br>
        if self.scale is not None:<br>
            self.scale = float(self.scale)<br>
<!-- END SCAT CODE -->
</body>
</html>
