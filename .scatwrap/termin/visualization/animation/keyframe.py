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
&#9;&quot;&quot;&quot;<br>
&#9;Кадр анимации в момент time.<br>
<br>
&#9;Любое из полей может быть None — тогда этот канал анимацией не затрагивается.<br>
&#9;translation: np.array shape (3,)<br>
&#9;rotation:    np.array shape (4,) (кватернион x, y, z, w)<br>
&#9;scale:       float (uniform-скейл)<br>
&#9;&quot;&quot;&quot;<br>
&#9;time: float<br>
&#9;translation: Optional[np.ndarray] = None<br>
&#9;rotation: Optional[np.ndarray] = None<br>
&#9;scale: Optional[float] = None<br>
<br>
&#9;def __post_init__(self):<br>
&#9;&#9;self.time = float(self.time)<br>
<br>
&#9;&#9;if self.translation is not None:<br>
&#9;&#9;&#9;self.translation = np.asarray(self.translation, dtype=float)<br>
&#9;&#9;&#9;if self.translation.shape != (3,):<br>
&#9;&#9;&#9;&#9;raise ValueError(&quot;translation must have shape (3,)&quot;)<br>
<br>
&#9;&#9;if self.rotation is not None:<br>
&#9;&#9;&#9;self.rotation = np.asarray(self.rotation, dtype=float)<br>
&#9;&#9;&#9;if self.rotation.shape != (4,):<br>
&#9;&#9;&#9;&#9;raise ValueError(&quot;rotation (quaternion) must have shape (4,)&quot;)<br>
<br>
&#9;&#9;if self.scale is not None:<br>
&#9;&#9;&#9;self.scale = float(self.scale)<br>
<!-- END SCAT CODE -->
</body>
</html>
