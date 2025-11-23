from __future__ import annotations

from typing import Dict, Mapping, Optional, Tuple

from .channel import AnimationChannel


class AnimationClip:
    """
    Анимационный клип: содержит несколько каналов (translation/rotation/scale)
    и умеет выдавать значение (tr, rot, scale) в момент времени t.
    """

    def __init__(self, name: str, channels: Mapping[str, AnimationChannel], loop: bool = True):
        self.name = name
        self.channels: Dict[str, AnimationChannel] = dict(channels)
        self.loop = loop

        # длительность — максимум по всем каналам
        self.duration: float = 0.0
        for ch in self.channels.values():
            if ch.keyframes:
                self.duration = max(self.duration, ch.keyframes[-1].time)

    def sample(self, t: float) -> Tuple[Optional[object], Optional[object], Optional[object]]:
        """
        Вернуть (translation, rotation, scale) в момент времени t.
        Любое из значений может быть None, если канал отсутствует.
        """
        tr = rot = sc = None

        if not self.channels:
            return tr, rot, sc

        duration = self.duration if self.loop else None

        for name, ch in self.channels.items():
            value = ch.sample(t, duration)
            if value is None:
                continue

            if name == "translation":
                tr = value
            elif name == "rotation":
                rot = value
            elif name == "scale":
                sc = value

        return tr, rot, sc
