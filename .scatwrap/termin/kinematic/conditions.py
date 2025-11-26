<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/kinematic/conditions.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import numpy<br>
import termin.linalg.subspaces<br>
<br>
<br>
class SymCondition:<br>
&#9;def __init__(self, Ah, bh, weight=1.0):<br>
&#9;&#9;self.Ah = Ah<br>
&#9;&#9;self.bh = bh<br>
&#9;&#9;self.weight = weight<br>
<br>
&#9;def A(self):<br>
&#9;&#9;return self.Ah.T.dot(self.Ah) * self.weight<br>
<br>
&#9;def b(self):<br>
&#9;&#9;return self.Ah.T.dot(self.bh) * self.weight<br>
<br>
&#9;def NullProj(self):<br>
&#9;&#9;return termin.linalg.subspaces.nullspace_projector(self.Ah)<br>
<br>
<br>
class ConditionCollection:<br>
&#9;def __init__(self):<br>
&#9;&#9;self.rank = -1<br>
&#9;&#9;self.conds = []<br>
&#9;&#9;self.weights = []<br>
<br>
&#9;def add(self, cond, weight=None):<br>
&#9;&#9;if weight is not None:<br>
&#9;&#9;&#9;cond.weight = weight<br>
&#9;&#9;if self.rank &lt; 0:<br>
&#9;&#9;&#9;self.rank = cond.A().shape[0]<br>
&#9;&#9;self.conds.append(cond)<br>
&#9;&#9;self.weights.append(cond.weight)<br>
<br>
&#9;def A(self):<br>
&#9;&#9;A_sum = numpy.zeros((self.rank, self.rank))<br>
&#9;&#9;for cond in self.conds:<br>
&#9;&#9;&#9;A_sum += cond.A()<br>
&#9;&#9;return A_sum<br>
<br>
&#9;def b(self):<br>
&#9;&#9;b_sum = numpy.zeros((self.rank,))<br>
&#9;&#9;for cond in self.conds:<br>
&#9;&#9;&#9;b_sum += cond.b()<br>
&#9;&#9;return b_sum<br>
<!-- END SCAT CODE -->
</body>
</html>
