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
    def from_fbx_clip(fbx_clip) -> "AnimationClip":
        """
        Создаёт AnimationClip из FBXAnimationClip.

        Args:
            fbx_clip: FBXAnimationClip из fbx_loader
        """
        channels = {}
        for ch in fbx_clip.channels:
            channels[ch.node_name] = AnimationChannel.from_fbx_channel(ch)

        return AnimationClip(
            name=fbx_clip.name,
            channels=channels,
            tps=fbx_clip.ticks_per_second or 30.0,
            loop=True,
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

    # --------------------------------------------

    def serialize(self) -> dict:
        """Сериализует клип в словарь для JSON."""
        return {
            "version": 1,
            "name": self.name,
            "tps": self.tps,
            "loop": self.loop,
            "channels": {name: ch.serialize() for name, ch in self.channels.items()},
        }

    @classmethod
    def deserialize(cls, data: dict) -> "AnimationClip":
        """Десериализует клип из словаря."""
        channels = {
            name: AnimationChannel.deserialize(ch_data)
            for name, ch_data in data.get("channels", {}).items()
        }
        return cls(
            name=data.get("name", "Unnamed"),
            channels=channels,
            tps=data.get("tps", 30.0),
            loop=data.get("loop", True),
        )
