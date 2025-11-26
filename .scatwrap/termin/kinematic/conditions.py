<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/kinematic/conditions.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import&nbsp;numpy<br>
import&nbsp;termin.linalg.subspaces<br>
<br>
<br>
class&nbsp;SymCondition:<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;Ah,&nbsp;bh,&nbsp;weight=1.0):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.Ah&nbsp;=&nbsp;Ah<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.bh&nbsp;=&nbsp;bh<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.weight&nbsp;=&nbsp;weight<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;A(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self.Ah.T.dot(self.Ah)&nbsp;*&nbsp;self.weight<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;b(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self.Ah.T.dot(self.bh)&nbsp;*&nbsp;self.weight<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;NullProj(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;termin.linalg.subspaces.nullspace_projector(self.Ah)<br>
<br>
<br>
class&nbsp;ConditionCollection:<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.rank&nbsp;=&nbsp;-1<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.conds&nbsp;=&nbsp;[]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.weights&nbsp;=&nbsp;[]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;add(self,&nbsp;cond,&nbsp;weight=None):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;weight&nbsp;is&nbsp;not&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;cond.weight&nbsp;=&nbsp;weight<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;self.rank&nbsp;&lt;&nbsp;0:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.rank&nbsp;=&nbsp;cond.A().shape[0]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.conds.append(cond)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.weights.append(cond.weight)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;A(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A_sum&nbsp;=&nbsp;numpy.zeros((self.rank,&nbsp;self.rank))<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;for&nbsp;cond&nbsp;in&nbsp;self.conds:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A_sum&nbsp;+=&nbsp;cond.A()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;A_sum<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;b(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b_sum&nbsp;=&nbsp;numpy.zeros((self.rank,))<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;for&nbsp;cond&nbsp;in&nbsp;self.conds:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b_sum&nbsp;+=&nbsp;cond.b()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;b_sum<br>
<!-- END SCAT CODE -->
</body>
</html>
