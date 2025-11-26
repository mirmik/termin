<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/animation/keyframe.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from&nbsp;__future__&nbsp;import&nbsp;annotations<br>
<br>
from&nbsp;dataclasses&nbsp;import&nbsp;dataclass<br>
from&nbsp;typing&nbsp;import&nbsp;Optional<br>
<br>
import&nbsp;numpy&nbsp;as&nbsp;np<br>
<br>
<br>
@dataclass<br>
class&nbsp;AnimationKeyframe:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Кадр&nbsp;анимации&nbsp;в&nbsp;момент&nbsp;time.<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;Любое&nbsp;из&nbsp;полей&nbsp;может&nbsp;быть&nbsp;None&nbsp;—&nbsp;тогда&nbsp;этот&nbsp;канал&nbsp;анимацией&nbsp;не&nbsp;затрагивается.<br>
&nbsp;&nbsp;&nbsp;&nbsp;translation:&nbsp;np.array&nbsp;shape&nbsp;(3,)<br>
&nbsp;&nbsp;&nbsp;&nbsp;rotation:&nbsp;&nbsp;&nbsp;&nbsp;np.array&nbsp;shape&nbsp;(4,)&nbsp;(кватернион&nbsp;x,&nbsp;y,&nbsp;z,&nbsp;w)<br>
&nbsp;&nbsp;&nbsp;&nbsp;scale:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;float&nbsp;(uniform-скейл)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;time:&nbsp;float<br>
&nbsp;&nbsp;&nbsp;&nbsp;translation:&nbsp;Optional[np.ndarray]&nbsp;=&nbsp;None<br>
&nbsp;&nbsp;&nbsp;&nbsp;rotation:&nbsp;Optional[np.ndarray]&nbsp;=&nbsp;None<br>
&nbsp;&nbsp;&nbsp;&nbsp;scale:&nbsp;Optional[float]&nbsp;=&nbsp;None<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__post_init__(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.time&nbsp;=&nbsp;float(self.time)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;self.translation&nbsp;is&nbsp;not&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.translation&nbsp;=&nbsp;np.asarray(self.translation,&nbsp;dtype=float)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;self.translation.shape&nbsp;!=&nbsp;(3,):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;raise&nbsp;ValueError(&quot;translation&nbsp;must&nbsp;have&nbsp;shape&nbsp;(3,)&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;self.rotation&nbsp;is&nbsp;not&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.rotation&nbsp;=&nbsp;np.asarray(self.rotation,&nbsp;dtype=float)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;self.rotation.shape&nbsp;!=&nbsp;(4,):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;raise&nbsp;ValueError(&quot;rotation&nbsp;(quaternion)&nbsp;must&nbsp;have&nbsp;shape&nbsp;(4,)&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;self.scale&nbsp;is&nbsp;not&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.scale&nbsp;=&nbsp;float(self.scale)<br>
<!-- END SCAT CODE -->
</body>
</html>
