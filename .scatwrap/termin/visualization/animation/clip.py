<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/animation/clip.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from __future__ import annotations<br>
from typing import Dict<br>
from .channel import AnimationChannel<br>
<br>
<br>
class AnimationClip:<br>
    &quot;&quot;&quot;<br>
    channels: { node_name : AnimationChannel }<br>
    duration: секунды<br>
    tps: ticks per second<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(self, name: str, channels: Dict[str, AnimationChannel], tps: float, loop=True):<br>
        self.name = name<br>
        self.channels = channels<br>
        self.loop = loop<br>
        self.tps = tps<br>
<br>
        # переводим тики → секунды<br>
        max_ticks = 0.0<br>
        for ch in channels.values():<br>
            max_ticks = max(max_ticks, ch.duration)<br>
<br>
        self.duration = max_ticks / tps if tps &gt; 0 else 0.0<br>
<br>
    # --------------------------------------------<br>
<br>
    @staticmethod<br>
    def _to_str(x):<br>
        if isinstance(x, str): return x<br>
        if hasattr(x, &quot;data&quot;): return x.data<br>
        return str(x)<br>
<br>
    # --------------------------------------------<br>
<br>
    @staticmethod<br>
    def from_assimp_clip(assimp_clip):<br>
        tps = getattr(assimp_clip, &quot;tickspersecond&quot;, 0.0) or 30.0<br>
<br>
        channels = {}<br>
        for ch in assimp_clip.channels:<br>
            node_name = AnimationClip._to_str(ch.node_name)<br>
            channels[node_name] = AnimationChannel.from_assimp_channel(ch)<br>
<br>
        return AnimationClip(<br>
            name=AnimationClip._to_str(assimp_clip.name),<br>
            channels=channels,<br>
            tps=tps,<br>
            loop=True<br>
        )<br>
<br>
    # --------------------------------------------<br>
<br>
    def sample(self, t_seconds: float):<br>
        &quot;&quot;&quot;<br>
        sample в секундах (как в движке).<br>
        Возвращает dict:<br>
            { node_name : (tr, rot, sc) }<br>
        &quot;&quot;&quot;<br>
<br>
        if self.loop and self.duration &gt; 0:<br>
            t_seconds = t_seconds % self.duration<br>
<br>
        # переводим секунды → тики<br>
        t_ticks = t_seconds * self.tps<br>
<br>
        return { node: ch.sample(t_ticks) for node, ch in self.channels.items() }<br>
<br>
    # --------------------------------------------<br>
<br>
    def __repr__(self):<br>
        return f&quot;&lt;AnimationClip name={self.name} duration={self.duration:.2f}s channels={len(self.channels)}&gt;&quot;<br>
<!-- END SCAT CODE -->
</body>
</html>
