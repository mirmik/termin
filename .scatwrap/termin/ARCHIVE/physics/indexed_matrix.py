<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/ARCHIVE/physics/indexed_matrix.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
<br>
import numpy<br>
import torch<br>
<br>
#import coo<br>
import scipy.sparse<br>
<br>
<br>
torch_type = torch.float64<br>
<br>
class IndexedMatrix:<br>
    def __init__(self, matrix, lidxs=None, ridxs=None, lcomm=None, rcomm=None):<br>
        self.lcomm = lcomm<br>
        self.rcomm = rcomm<br>
        self.lidxs = lidxs<br>
        self.ridxs = ridxs<br>
        #self.matrix = scipy.sparse.lil_matrix(matrix)<br>
        self.matrix = matrix<br>
        if self.lidxs:<br>
            self.index_of_lidxs = {idx: lidxs.index(idx) for idx in lidxs}<br>
        if self.ridxs:<br>
            self.index_of_ridxs = {idx: ridxs.index(idx) for idx in ridxs}<br>
<br>
#    def coo(self):<br>
#        self.matrix = scipy.sparse.coo_matrix(self.matrix)<br>
<br>
#    def dense(self):<br>
#        return self.matrix.todense()<br>
<br>
    def matmul(self, oth):<br>
        if self.ridxs != oth.lidxs:<br>
            raise Exception(&quot;indexes is not same in convolution&quot;)<br>
        matrix = self.matrix @ oth.matrix<br>
        return IndexedMatrix(matrix, self.lidxs, oth.ridxs)<br>
<br>
    def vecmul(self, oth):<br>
        if self.ridxs != oth.idxs:<br>
            raise Exception(&quot;indexes is not same in convolution&quot;)<br>
        matrix = self.matrix @ oth.matrix<br>
        return IndexedVector(matrix, self.lidxs)<br>
<br>
    def __matmul__(self, oth):<br>
        if isinstance(oth, IndexedVector):<br>
            return self.vecmul(oth)<br>
        else:<br>
            return self.matmul(oth)<br>
<br>
    def __neg__(self):<br>
        return IndexedMatrix(-self.matrix, self.lidxs, self.ridxs, self.lcomm, self.rcomm)<br>
<br>
    def inv(self):<br>
        return IndexedMatrix(scipy.sparse.linalg.inv(self.matrix), self.ridxs, self.lidxs, self.rcomm, self.lcomm)<br>
<br>
    def solve(self, b):<br>
        return numpy.linalg.solve(self.matrix, b.matrix)<br>
<br>
    def raise_if_lidxs_is_not_same(self, oth):<br>
        if self.lidxs != oth.lidxs:<br>
            raise Exception(&quot;indexes is not same in convolution&quot;)<br>
<br>
    def raise_if_ridxs_is_not_same(self, oth):<br>
        if self.ridxs != oth.ridxs:<br>
            raise Exception(&quot;indexes is not same in convolution&quot;)<br>
<br>
    def raise_if_not_linkaged(self, oth):<br>
        if self.ridxs != oth.lidxs:<br>
            raise Exception(&quot;indexes is not same in convolution&quot;)<br>
<br>
    def __add__(self, oth):<br>
        self.raise_if_lidxs_is_not_same(oth)<br>
        self.raise_if_ridxs_is_not_same(oth)<br>
        return IndexedMatrix(self.matrix + oth.matrix, self.lidxs, self.ridxs, self.lcomm, self.rcomm)<br>
<br>
    def __mul__(self, s):<br>
        return IndexedMatrix(self.matrix * s, self.lidxs, self.ridxs, self.lcomm, self.rcomm)<br>
<br>
    def unsparse(self):<br>
        return self.matrix.toarray()<br>
<br>
    def transpose(self):<br>
        return IndexedMatrix(self.matrix.T, self.ridxs, self.lidxs, self.rcomm, self.lcomm)<br>
<br>
    def accumulate_from(self, other):<br>
        lidxs = [self.index_of_lidxs[i] for i in other.lidxs]<br>
        ridxs = [self.index_of_ridxs[i] for i in other.ridxs]<br>
<br>
        for i in range(len(lidxs)):<br>
            for j in range(len(ridxs)):<br>
                self.matrix[lidxs[i], ridxs[j]] += other.matrix[i, j]<br>
<br>
    def __str__(self):<br>
        return &quot;Matrix:\r\n{}\r\nLeft Indexes: {}\r\nRight Indexes: {}\r\n&quot;.format(self.matrix, self.lidxs, self.ridxs)<br>
<br>
<br>
class IndexedVector:<br>
    def __init__(self, matrix, idxs, comm=None):<br>
        self.comm = comm<br>
        if isinstance(matrix, numpy.ndarray) and len(matrix.shape) != 1:<br>
            matrix = matrix.reshape(matrix.shape[0], 1)<br>
        self.matrix = matrix<br>
        self.idxs = idxs<br>
        if self.idxs:<br>
            self.index_of_idxs = {idx: idxs.index(idx) for idx in idxs}<br>
<br>
    def __str__(self):<br>
        return &quot;Vector:\r\n{}\r\nIndexes: {}\r\n&quot;.format(self.matrix, self.idxs)<br>
<br>
    def accumulate_from(self, other):<br>
        idxs = [self.index_of_idxs[i] for i in other.idxs]<br>
        for i in range(len(idxs)):<br>
            self.matrix[idxs[i]] += other.matrix[i]<br>
<br>
    def upbind_values(self):<br>
        for i in range(len(self.idxs)):<br>
            self.idxs[i].set_value(self.matrix[i])<br>
<!-- END SCAT CODE -->
</body>
</html>
