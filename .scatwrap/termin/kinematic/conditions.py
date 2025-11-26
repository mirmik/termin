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
    def __init__(self, Ah, bh, weight=1.0):<br>
        self.Ah = Ah<br>
        self.bh = bh<br>
        self.weight = weight<br>
<br>
    def A(self):<br>
        return self.Ah.T.dot(self.Ah) * self.weight<br>
<br>
    def b(self):<br>
        return self.Ah.T.dot(self.bh) * self.weight<br>
<br>
    def NullProj(self):<br>
        return termin.linalg.subspaces.nullspace_projector(self.Ah)<br>
<br>
<br>
class ConditionCollection:<br>
    def __init__(self):<br>
        self.rank = -1<br>
        self.conds = []<br>
        self.weights = []<br>
<br>
    def add(self, cond, weight=None):<br>
        if weight is not None:<br>
            cond.weight = weight<br>
        if self.rank &lt; 0:<br>
            self.rank = cond.A().shape[0]<br>
        self.conds.append(cond)<br>
        self.weights.append(cond.weight)<br>
<br>
    def A(self):<br>
        A_sum = numpy.zeros((self.rank, self.rank))<br>
        for cond in self.conds:<br>
            A_sum += cond.A()<br>
        return A_sum<br>
<br>
    def b(self):<br>
        b_sum = numpy.zeros((self.rank,))<br>
        for cond in self.conds:<br>
            b_sum += cond.b()<br>
        return b_sum<br>
<!-- END SCAT CODE -->
</body>
</html>
