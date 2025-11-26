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
    &quot;&quot;&quot;<br>
    Канал одного узла FBX:<br>
        - translation_keys: ключи позиций (в тиках)<br>
        - rotation_keys: ключи вращения (кватернионы) (в тиках)<br>
        - scale_keys: ключи скейла (в тиках)<br>
<br>
    Всё хранится в ТИКАХ, без пересчёта в секунды.<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(self, translation_keys, rotation_keys, scale_keys):<br>
        self.translation_keys = sorted(translation_keys, key=lambda k: k.time)<br>
        self.rotation_keys = sorted(rotation_keys, key=lambda k: k.time)<br>
        self.scale_keys = sorted(scale_keys, key=lambda k: k.time)<br>
<br>
        # duration в тиках<br>
        self.duration = 0.0<br>
        for arr in (self.translation_keys, self.rotation_keys, self.scale_keys):<br>
            if arr:<br>
                self.duration = max(self.duration, arr[-1].time)<br>
<br>
    # --------------------------------------------<br>
<br>
    @staticmethod<br>
    def _interp_linear(a, b, alpha):<br>
        return (1.0 - alpha) * np.asarray(a, float) + alpha * np.asarray(b, float)<br>
<br>
    @staticmethod<br>
    def _sample_keys(keys, t_ticks, interp):<br>
        if not keys:<br>
            return None<br>
<br>
        first = keys[0]<br>
        last = keys[-1]<br>
<br>
        if t_ticks &lt;= first.time:<br>
            return interp(first, first, 0.0)<br>
        if t_ticks &gt;= last.time:<br>
            return interp(last, last, 0.0)<br>
<br>
        for k1, k2 in zip(keys, keys[1:]):<br>
            if k1.time &lt;= t_ticks &lt;= k2.time:<br>
                dt = k2.time - k1.time<br>
                alpha = (t_ticks - k1.time) / dt if dt != 0 else 0.0<br>
                return interp(k1, k2, alpha)<br>
<br>
        return interp(last, last, 0.0)<br>
<br>
    # --------------------------------------------<br>
<br>
    def sample(self, t_ticks: float) -&gt; Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[float]]:<br>
        &quot;&quot;&quot;<br>
        t_ticks — время в ТИКАХ.<br>
        &quot;&quot;&quot;<br>
<br>
        tr = None<br>
        rot = None<br>
        sc = None<br>
<br>
        if self.translation_keys:<br>
            tr = self._sample_keys(<br>
                self.translation_keys, t_ticks,<br>
                lambda a, b, alpha: self._interp_linear(a.translation, b.translation, alpha)<br>
            )<br>
<br>
        if self.rotation_keys:<br>
            rot = self._sample_keys(<br>
                self.rotation_keys, t_ticks,<br>
                lambda a, b, alpha: qslerp(a.rotation, b.rotation, alpha)<br>
            )<br>
<br>
        if self.scale_keys:<br>
            sc = self._sample_keys(<br>
                self.scale_keys, t_ticks,<br>
                lambda a, b, alpha: float((1 - alpha) * a.scale + alpha * b.scale)<br>
            )<br>
<br>
        return tr, rot, sc<br>
<br>
    # --------------------------------------------<br>
<br>
    @staticmethod<br>
    def from_assimp_channel(ch):<br>
        &quot;&quot;&quot;<br>
        Берёт pos_keys, rot_keys, scale_keys в ТИКАХ (как из fbx_loader)<br>
        и создаёт единый канал.<br>
        &quot;&quot;&quot;<br>
<br>
        tr = [AnimationKeyframe(t, translation=np.array(v))<br>
              for (t, v) in getattr(ch, &quot;pos_keys&quot;, [])]<br>
<br>
        rot = [AnimationKeyframe(t, rotation=np.array(v))<br>
               for (t, v) in getattr(ch, &quot;rot_keys&quot;, [])]<br>
<br>
        sc = [AnimationKeyframe(t, scale=float(np.mean(v)))<br>
              for (t, v) in getattr(ch, &quot;scale_keys&quot;, [])]<br>
<br>
        return AnimationChannel(tr, rot, sc)<br>
<br>
    # --------------------------------------------<br>
<br>
    def __repr__(self):<br>
        return f&quot;&lt;AnimationChannel ticks={self.duration:.2f} tr_keys={len(self.translation_keys)} rot_keys={len(self.rotation_keys)} scale_keys={len(self.scale_keys)}&gt;&quot;<br>
<!-- END SCAT CODE -->
</body>
</html>
