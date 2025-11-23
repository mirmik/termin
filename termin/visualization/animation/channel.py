from __future__ import annotations

from typing import Iterable, List, Optional

import numpy as np

from termin.util import qslerp
from .keyframe import AnimationKeyframe


class AnimationChannel:
    """
    Один канал анимации:
      type == "translation" -> работает с keyframe.translation
      type == "rotation"    -> работает с keyframe.rotation (кватернион)
      type == "scale"       -> работает с keyframe.scale (float)
    """

    def __init__(self, channel_type: str, keyframes: Iterable[AnimationKeyframe]):
        if channel_type not in ("translation", "rotation", "scale"):
            raise ValueError(f"Unknown channel type: {channel_type}")
        self.type = channel_type
        self.keyframes: List[AnimationKeyframe] = sorted(
            list(keyframes), key=lambda k: k.time
        )

    def _value_from_key(self, kf: AnimationKeyframe):
        if self.type == "translation":
            return kf.translation
        if self.type == "rotation":
            return kf.rotation
        return kf.scale

    def sample(self, t: float, duration: Optional[float] = None):
        """
        Вернуть значение канала в момент времени t.
        Если duration задан и > 0, t берётся по модулю duration (loop).
        """
        if not self.keyframes:
            return None

        if duration and duration > 0.0:
            t = t % duration

        first = self.keyframes[0]
        last = self.keyframes[-1]

        # до первого / после последнего — clamp
        if t <= first.time:
            return self._value_from_key(first)
        if t >= last.time:
            return self._value_from_key(last)

        # поиск отрезка
        for k1, k2 in zip(self.keyframes, self.keyframes[1:]):
            if k1.time <= t <= k2.time:
                if k2.time == k1.time:
                    return self._value_from_key(k1)

                alpha = (t - k1.time) / (k2.time - k1.time)
                v1 = self._value_from_key(k1)
                v2 = self._value_from_key(k2)

                # если один из ключей не задаёт этот канал — берём тот, что задаёт
                if v1 is None and v2 is None:
                    return None
                if v1 is None:
                    return v2
                if v2 is None:
                    return v1

                if self.type == "translation":
                    v1 = np.asarray(v1, dtype=float)
                    v2 = np.asarray(v2, dtype=float)
                    return (1.0 - alpha) * v1 + alpha * v2

                if self.type == "scale":
                    return (1.0 - alpha) * float(v1) + alpha * float(v2)

                # rotation: slerp кватернионов
                v1 = np.asarray(v1, dtype=float)
                v2 = np.asarray(v2, dtype=float)
                print("V1:", v1)
                print("V2:", v2)
                slerped = qslerp(v1, v2, alpha)
                print("Slerped:", slerped)
                return slerped

        # теоретически не дойдём, но на всякий
        return self._value_from_key(last)
