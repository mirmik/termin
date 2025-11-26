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
&#9;&quot;&quot;&quot;<br>
&#9;channels: { node_name : AnimationChannel }<br>
&#9;duration: секунды<br>
&#9;tps: ticks per second<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, name: str, channels: Dict[str, AnimationChannel], tps: float, loop=True):<br>
&#9;&#9;self.name = name<br>
&#9;&#9;self.channels = channels<br>
&#9;&#9;self.loop = loop<br>
&#9;&#9;self.tps = tps<br>
<br>
&#9;&#9;# переводим тики → секунды<br>
&#9;&#9;max_ticks = 0.0<br>
&#9;&#9;for ch in channels.values():<br>
&#9;&#9;&#9;max_ticks = max(max_ticks, ch.duration)<br>
<br>
&#9;&#9;self.duration = max_ticks / tps if tps &gt; 0 else 0.0<br>
<br>
&#9;# --------------------------------------------<br>
<br>
&#9;@staticmethod<br>
&#9;def _to_str(x):<br>
&#9;&#9;if isinstance(x, str): return x<br>
&#9;&#9;if hasattr(x, &quot;data&quot;): return x.data<br>
&#9;&#9;return str(x)<br>
<br>
&#9;# --------------------------------------------<br>
<br>
&#9;@staticmethod<br>
&#9;def from_assimp_clip(assimp_clip):<br>
&#9;&#9;tps = getattr(assimp_clip, &quot;tickspersecond&quot;, 0.0) or 30.0<br>
<br>
&#9;&#9;channels = {}<br>
&#9;&#9;for ch in assimp_clip.channels:<br>
&#9;&#9;&#9;node_name = AnimationClip._to_str(ch.node_name)<br>
&#9;&#9;&#9;channels[node_name] = AnimationChannel.from_assimp_channel(ch)<br>
<br>
&#9;&#9;return AnimationClip(<br>
&#9;&#9;&#9;name=AnimationClip._to_str(assimp_clip.name),<br>
&#9;&#9;&#9;channels=channels,<br>
&#9;&#9;&#9;tps=tps,<br>
&#9;&#9;&#9;loop=True<br>
&#9;&#9;)<br>
<br>
&#9;# --------------------------------------------<br>
<br>
&#9;def sample(self, t_seconds: float):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;sample в секундах (как в движке).<br>
&#9;&#9;Возвращает dict:<br>
&#9;&#9;&#9;{ node_name : (tr, rot, sc) }<br>
&#9;&#9;&quot;&quot;&quot;<br>
<br>
&#9;&#9;if self.loop and self.duration &gt; 0:<br>
&#9;&#9;&#9;t_seconds = t_seconds % self.duration<br>
<br>
&#9;&#9;# переводим секунды → тики<br>
&#9;&#9;t_ticks = t_seconds * self.tps<br>
<br>
&#9;&#9;return { node: ch.sample(t_ticks) for node, ch in self.channels.items() }<br>
<br>
&#9;# --------------------------------------------<br>
<br>
&#9;def __repr__(self):<br>
&#9;&#9;return f&quot;&lt;AnimationClip name={self.name} duration={self.duration:.2f}s channels={len(self.channels)}&gt;&quot;<br>
<!-- END SCAT CODE -->
</body>
</html>
