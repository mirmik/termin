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
&#9;def __init__(self, matrix, lidxs=None, ridxs=None, lcomm=None, rcomm=None):<br>
&#9;&#9;self.lcomm = lcomm<br>
&#9;&#9;self.rcomm = rcomm<br>
&#9;&#9;self.lidxs = lidxs<br>
&#9;&#9;self.ridxs = ridxs<br>
&#9;&#9;#self.matrix = scipy.sparse.lil_matrix(matrix)<br>
&#9;&#9;self.matrix = matrix<br>
&#9;&#9;if self.lidxs:<br>
&#9;&#9;&#9;self.index_of_lidxs = {idx: lidxs.index(idx) for idx in lidxs}<br>
&#9;&#9;if self.ridxs:<br>
&#9;&#9;&#9;self.index_of_ridxs = {idx: ridxs.index(idx) for idx in ridxs}<br>
<br>
#    def coo(self):<br>
#        self.matrix = scipy.sparse.coo_matrix(self.matrix)<br>
<br>
#    def dense(self):<br>
#        return self.matrix.todense()<br>
<br>
&#9;def matmul(self, oth):<br>
&#9;&#9;if self.ridxs != oth.lidxs:<br>
&#9;&#9;&#9;raise Exception(&quot;indexes is not same in convolution&quot;)<br>
&#9;&#9;matrix = self.matrix @ oth.matrix<br>
&#9;&#9;return IndexedMatrix(matrix, self.lidxs, oth.ridxs)<br>
<br>
&#9;def vecmul(self, oth):<br>
&#9;&#9;if self.ridxs != oth.idxs:<br>
&#9;&#9;&#9;raise Exception(&quot;indexes is not same in convolution&quot;)<br>
&#9;&#9;matrix = self.matrix @ oth.matrix<br>
&#9;&#9;return IndexedVector(matrix, self.lidxs)<br>
<br>
&#9;def __matmul__(self, oth):<br>
&#9;&#9;if isinstance(oth, IndexedVector):<br>
&#9;&#9;&#9;return self.vecmul(oth)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;return self.matmul(oth)<br>
<br>
&#9;def __neg__(self):<br>
&#9;&#9;return IndexedMatrix(-self.matrix, self.lidxs, self.ridxs, self.lcomm, self.rcomm)<br>
<br>
&#9;def inv(self):<br>
&#9;&#9;return IndexedMatrix(scipy.sparse.linalg.inv(self.matrix), self.ridxs, self.lidxs, self.rcomm, self.lcomm)<br>
<br>
&#9;def solve(self, b):<br>
&#9;&#9;return numpy.linalg.solve(self.matrix, b.matrix)<br>
<br>
&#9;def raise_if_lidxs_is_not_same(self, oth):<br>
&#9;&#9;if self.lidxs != oth.lidxs:<br>
&#9;&#9;&#9;raise Exception(&quot;indexes is not same in convolution&quot;)<br>
<br>
&#9;def raise_if_ridxs_is_not_same(self, oth):<br>
&#9;&#9;if self.ridxs != oth.ridxs:<br>
&#9;&#9;&#9;raise Exception(&quot;indexes is not same in convolution&quot;)<br>
<br>
&#9;def raise_if_not_linkaged(self, oth):<br>
&#9;&#9;if self.ridxs != oth.lidxs:<br>
&#9;&#9;&#9;raise Exception(&quot;indexes is not same in convolution&quot;)<br>
<br>
&#9;def __add__(self, oth):<br>
&#9;&#9;self.raise_if_lidxs_is_not_same(oth)<br>
&#9;&#9;self.raise_if_ridxs_is_not_same(oth)<br>
&#9;&#9;return IndexedMatrix(self.matrix + oth.matrix, self.lidxs, self.ridxs, self.lcomm, self.rcomm)<br>
<br>
&#9;def __mul__(self, s):<br>
&#9;&#9;return IndexedMatrix(self.matrix * s, self.lidxs, self.ridxs, self.lcomm, self.rcomm)<br>
<br>
&#9;def unsparse(self):<br>
&#9;&#9;return self.matrix.toarray()<br>
<br>
&#9;def transpose(self):<br>
&#9;&#9;return IndexedMatrix(self.matrix.T, self.ridxs, self.lidxs, self.rcomm, self.lcomm)<br>
<br>
&#9;def accumulate_from(self, other):<br>
&#9;&#9;lidxs = [self.index_of_lidxs[i] for i in other.lidxs]<br>
&#9;&#9;ridxs = [self.index_of_ridxs[i] for i in other.ridxs]<br>
<br>
&#9;&#9;for i in range(len(lidxs)):<br>
&#9;&#9;&#9;for j in range(len(ridxs)):<br>
&#9;&#9;&#9;&#9;self.matrix[lidxs[i], ridxs[j]] += other.matrix[i, j]<br>
<br>
&#9;def __str__(self):<br>
&#9;&#9;return &quot;Matrix:\r\n{}\r\nLeft Indexes: {}\r\nRight Indexes: {}\r\n&quot;.format(self.matrix, self.lidxs, self.ridxs)<br>
<br>
<br>
class IndexedVector:<br>
&#9;def __init__(self, matrix, idxs, comm=None):<br>
&#9;&#9;self.comm = comm<br>
&#9;&#9;if isinstance(matrix, numpy.ndarray) and len(matrix.shape) != 1:<br>
&#9;&#9;&#9;matrix = matrix.reshape(matrix.shape[0], 1)<br>
&#9;&#9;self.matrix = matrix<br>
&#9;&#9;self.idxs = idxs<br>
&#9;&#9;if self.idxs:<br>
&#9;&#9;&#9;self.index_of_idxs = {idx: idxs.index(idx) for idx in idxs}<br>
<br>
&#9;def __str__(self):<br>
&#9;&#9;return &quot;Vector:\r\n{}\r\nIndexes: {}\r\n&quot;.format(self.matrix, self.idxs)<br>
<br>
&#9;def accumulate_from(self, other):<br>
&#9;&#9;idxs = [self.index_of_idxs[i] for i in other.idxs]<br>
&#9;&#9;for i in range(len(idxs)):<br>
&#9;&#9;&#9;self.matrix[idxs[i]] += other.matrix[i]<br>
<br>
&#9;def upbind_values(self):<br>
&#9;&#9;for i in range(len(self.idxs)):<br>
&#9;&#9;&#9;self.idxs[i].set_value(self.matrix[i])<br>
<!-- END SCAT CODE -->
</body>
</html>
