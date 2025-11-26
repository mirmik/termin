<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/animation/channel.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from __future__ import annotations<br>
from typing import List, Optional, Tuple<br>
import numpy as np<br>
<br>
from termin.util import qslerp<br>
from .keyframe import AnimationKeyframe<br>
<br>
<br>
class AnimationChannel:<br>
&#9;&quot;&quot;&quot;<br>
&#9;Канал одного узла FBX:<br>
&#9;&#9;- translation_keys: ключи позиций (в тиках)<br>
&#9;&#9;- rotation_keys: ключи вращения (кватернионы) (в тиках)<br>
&#9;&#9;- scale_keys: ключи скейла (в тиках)<br>
<br>
&#9;Всё хранится в ТИКАХ, без пересчёта в секунды.<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, translation_keys, rotation_keys, scale_keys):<br>
&#9;&#9;self.translation_keys = sorted(translation_keys, key=lambda k: k.time)<br>
&#9;&#9;self.rotation_keys = sorted(rotation_keys, key=lambda k: k.time)<br>
&#9;&#9;self.scale_keys = sorted(scale_keys, key=lambda k: k.time)<br>
<br>
&#9;&#9;# duration в тиках<br>
&#9;&#9;self.duration = 0.0<br>
&#9;&#9;for arr in (self.translation_keys, self.rotation_keys, self.scale_keys):<br>
&#9;&#9;&#9;if arr:<br>
&#9;&#9;&#9;&#9;self.duration = max(self.duration, arr[-1].time)<br>
<br>
&#9;# --------------------------------------------<br>
<br>
&#9;@staticmethod<br>
&#9;def _interp_linear(a, b, alpha):<br>
&#9;&#9;return (1.0 - alpha) * np.asarray(a, float) + alpha * np.asarray(b, float)<br>
<br>
&#9;@staticmethod<br>
&#9;def _sample_keys(keys, t_ticks, interp):<br>
&#9;&#9;if not keys:<br>
&#9;&#9;&#9;return None<br>
<br>
&#9;&#9;first = keys[0]<br>
&#9;&#9;last = keys[-1]<br>
<br>
&#9;&#9;if t_ticks &lt;= first.time:<br>
&#9;&#9;&#9;return interp(first, first, 0.0)<br>
&#9;&#9;if t_ticks &gt;= last.time:<br>
&#9;&#9;&#9;return interp(last, last, 0.0)<br>
<br>
&#9;&#9;for k1, k2 in zip(keys, keys[1:]):<br>
&#9;&#9;&#9;if k1.time &lt;= t_ticks &lt;= k2.time:<br>
&#9;&#9;&#9;&#9;dt = k2.time - k1.time<br>
&#9;&#9;&#9;&#9;alpha = (t_ticks - k1.time) / dt if dt != 0 else 0.0<br>
&#9;&#9;&#9;&#9;return interp(k1, k2, alpha)<br>
<br>
&#9;&#9;return interp(last, last, 0.0)<br>
<br>
&#9;# --------------------------------------------<br>
<br>
&#9;def sample(self, t_ticks: float) -&gt; Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[float]]:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;t_ticks — время в ТИКАХ.<br>
&#9;&#9;&quot;&quot;&quot;<br>
<br>
&#9;&#9;tr = None<br>
&#9;&#9;rot = None<br>
&#9;&#9;sc = None<br>
<br>
&#9;&#9;if self.translation_keys:<br>
&#9;&#9;&#9;tr = self._sample_keys(<br>
&#9;&#9;&#9;&#9;self.translation_keys, t_ticks,<br>
&#9;&#9;&#9;&#9;lambda a, b, alpha: self._interp_linear(a.translation, b.translation, alpha)<br>
&#9;&#9;&#9;)<br>
<br>
&#9;&#9;if self.rotation_keys:<br>
&#9;&#9;&#9;rot = self._sample_keys(<br>
&#9;&#9;&#9;&#9;self.rotation_keys, t_ticks,<br>
&#9;&#9;&#9;&#9;lambda a, b, alpha: qslerp(a.rotation, b.rotation, alpha)<br>
&#9;&#9;&#9;)<br>
<br>
&#9;&#9;if self.scale_keys:<br>
&#9;&#9;&#9;sc = self._sample_keys(<br>
&#9;&#9;&#9;&#9;self.scale_keys, t_ticks,<br>
&#9;&#9;&#9;&#9;lambda a, b, alpha: float((1 - alpha) * a.scale + alpha * b.scale)<br>
&#9;&#9;&#9;)<br>
<br>
&#9;&#9;return tr, rot, sc<br>
<br>
&#9;# --------------------------------------------<br>
<br>
&#9;@staticmethod<br>
&#9;def from_assimp_channel(ch):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Берёт pos_keys, rot_keys, scale_keys в ТИКАХ (как из fbx_loader)<br>
&#9;&#9;и создаёт единый канал.<br>
&#9;&#9;&quot;&quot;&quot;<br>
<br>
&#9;&#9;tr = [AnimationKeyframe(t, translation=np.array(v))<br>
&#9;&#9;&#9;for (t, v) in getattr(ch, &quot;pos_keys&quot;, [])]<br>
<br>
&#9;&#9;rot = [AnimationKeyframe(t, rotation=np.array(v))<br>
&#9;&#9;&#9;for (t, v) in getattr(ch, &quot;rot_keys&quot;, [])]<br>
<br>
&#9;&#9;sc = [AnimationKeyframe(t, scale=float(np.mean(v)))<br>
&#9;&#9;&#9;for (t, v) in getattr(ch, &quot;scale_keys&quot;, [])]<br>
<br>
&#9;&#9;return AnimationChannel(tr, rot, sc)<br>
<br>
&#9;# --------------------------------------------<br>
<br>
&#9;def __repr__(self):<br>
&#9;&#9;return f&quot;&lt;AnimationChannel ticks={self.duration:.2f} tr_keys={len(self.translation_keys)} rot_keys={len(self.rotation_keys)} scale_keys={len(self.scale_keys)}&gt;&quot;<br>
<!-- END SCAT CODE -->
</body>
</html>
