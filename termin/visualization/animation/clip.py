from __future__ import annotations
from typing import Dict
from .channel import AnimationChannel


class AnimationClip:
    """
    channels: { node_name : AnimationChannel }
    duration: секунды
    tps: ticks per second
    """

    def __init__(self, name: str, channels: Dict[str, AnimationChannel], tps: float, loop=True):
        self.name = name
        self.channels = channels
        self.loop = loop
        self.tps = tps

        # переводим тики → секунды
        max_ticks = 0.0
        for ch in channels.values():
            max_ticks = max(max_ticks, ch.duration)

        self.duration = max_ticks / tps if tps > 0 else 0.0

    # --------------------------------------------

    @staticmethod
    def _to_str(x):
        if isinstance(x, str): return x
        if hasattr(x, "data"): return x.data
        return str(x)

    # --------------------------------------------

    @staticmethod
    def from_assimp_clip(assimp_clip):
        tps = getattr(assimp_clip, "tickspersecond", 0.0) or 30.0

        channels = {}
        for ch in assimp_clip.channels:
            node_name = AnimationClip._to_str(ch.node_name)
            channels[node_name] = AnimationChannel.from_assimp_channel(ch)

        return AnimationClip(
            name=AnimationClip._to_str(assimp_clip.name),
            channels=channels,
            tps=tps,
            loop=True
        )

    # --------------------------------------------

    def sample(self, t_seconds: float):
        """
        sample в секундах (как в движке).
        Возвращает dict:
            { node_name : (tr, rot, sc) }
        """

        if self.loop and self.duration > 0:
            t_seconds = t_seconds % self.duration

        # переводим секунды → тики
        t_ticks = t_seconds * self.tps

        return { node: ch.sample(t_ticks) for node, ch in self.channels.items() }

    # --------------------------------------------

    def __repr__(self):
        return f"<AnimationClip name={self.name} duration={self.duration:.2f}s channels={len(self.channels)}>"
