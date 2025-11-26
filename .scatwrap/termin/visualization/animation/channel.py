<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/animation/channel.py</title>
</head>
<body>
<pre><code>
from __future__ import annotations
from typing import List, Optional, Tuple
import numpy as np

from termin.util import qslerp
from .keyframe import AnimationKeyframe


class AnimationChannel:
    &quot;&quot;&quot;
    Канал одного узла FBX:
        - translation_keys: ключи позиций (в тиках)
        - rotation_keys: ключи вращения (кватернионы) (в тиках)
        - scale_keys: ключи скейла (в тиках)

    Всё хранится в ТИКАХ, без пересчёта в секунды.
    &quot;&quot;&quot;

    def __init__(self, translation_keys, rotation_keys, scale_keys):
        self.translation_keys = sorted(translation_keys, key=lambda k: k.time)
        self.rotation_keys = sorted(rotation_keys, key=lambda k: k.time)
        self.scale_keys = sorted(scale_keys, key=lambda k: k.time)

        # duration в тиках
        self.duration = 0.0
        for arr in (self.translation_keys, self.rotation_keys, self.scale_keys):
            if arr:
                self.duration = max(self.duration, arr[-1].time)

    # --------------------------------------------

    @staticmethod
    def _interp_linear(a, b, alpha):
        return (1.0 - alpha) * np.asarray(a, float) + alpha * np.asarray(b, float)

    @staticmethod
    def _sample_keys(keys, t_ticks, interp):
        if not keys:
            return None

        first = keys[0]
        last = keys[-1]

        if t_ticks &lt;= first.time:
            return interp(first, first, 0.0)
        if t_ticks &gt;= last.time:
            return interp(last, last, 0.0)

        for k1, k2 in zip(keys, keys[1:]):
            if k1.time &lt;= t_ticks &lt;= k2.time:
                dt = k2.time - k1.time
                alpha = (t_ticks - k1.time) / dt if dt != 0 else 0.0
                return interp(k1, k2, alpha)

        return interp(last, last, 0.0)

    # --------------------------------------------

    def sample(self, t_ticks: float) -&gt; Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[float]]:
        &quot;&quot;&quot;
        t_ticks — время в ТИКАХ.
        &quot;&quot;&quot;

        tr = None
        rot = None
        sc = None

        if self.translation_keys:
            tr = self._sample_keys(
                self.translation_keys, t_ticks,
                lambda a, b, alpha: self._interp_linear(a.translation, b.translation, alpha)
            )

        if self.rotation_keys:
            rot = self._sample_keys(
                self.rotation_keys, t_ticks,
                lambda a, b, alpha: qslerp(a.rotation, b.rotation, alpha)
            )

        if self.scale_keys:
            sc = self._sample_keys(
                self.scale_keys, t_ticks,
                lambda a, b, alpha: float((1 - alpha) * a.scale + alpha * b.scale)
            )

        return tr, rot, sc

    # --------------------------------------------

    @staticmethod
    def from_assimp_channel(ch):
        &quot;&quot;&quot;
        Берёт pos_keys, rot_keys, scale_keys в ТИКАХ (как из fbx_loader)
        и создаёт единый канал.
        &quot;&quot;&quot;

        tr = [AnimationKeyframe(t, translation=np.array(v))
              for (t, v) in getattr(ch, &quot;pos_keys&quot;, [])]

        rot = [AnimationKeyframe(t, rotation=np.array(v))
               for (t, v) in getattr(ch, &quot;rot_keys&quot;, [])]

        sc = [AnimationKeyframe(t, scale=float(np.mean(v)))
              for (t, v) in getattr(ch, &quot;scale_keys&quot;, [])]

        return AnimationChannel(tr, rot, sc)

    # --------------------------------------------

    def __repr__(self):
        return f&quot;&lt;AnimationChannel ticks={self.duration:.2f} tr_keys={len(self.translation_keys)} rot_keys={len(self.rotation_keys)} scale_keys={len(self.scale_keys)}&gt;&quot;

</code></pre>
</body>
</html>
