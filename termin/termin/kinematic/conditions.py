import numpy
import termin.linalg.subspaces


class SymCondition:
    def __init__(self, Ah, bh, weight=1.0):
        self.Ah = Ah
        self.bh = bh
        self.weight = weight

    def A(self):
        return self.Ah.T.dot(self.Ah) * self.weight

    def b(self):
        return self.Ah.T.dot(self.bh) * self.weight

    def NullProj(self):
        return termin.linalg.subspaces.nullspace_projector(self.Ah)


class ConditionCollection:
    def __init__(self):
        self.rank = -1
        self.conds = []
        self.weights = []

    def add(self, cond, weight=None):
        if weight is not None:
            cond.weight = weight
        if self.rank < 0:
            self.rank = cond.A().shape[0]
        self.conds.append(cond)
        self.weights.append(cond.weight)

    def A(self):
        A_sum = numpy.zeros((self.rank, self.rank))
        for cond in self.conds:
            A_sum += cond.A()
        return A_sum

    def b(self):
        b_sum = numpy.zeros((self.rank,))
        for cond in self.conds:
            b_sum += cond.b()
        return b_sum