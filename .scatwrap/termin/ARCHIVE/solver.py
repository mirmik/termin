<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/ARCHIVE/solver.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#!/usr/bin/env python3<br>
<br>
import numpy<br>
import scipy<br>
from termin.physics.indexed_matrix import IndexedMatrix, IndexedVector<br>
import torch<br>
<br>
TORCH_DEVICE = &quot;cuda&quot; if torch.cuda.is_available() else &quot;cpu&quot;<br>
<br>
def full_indexes_list_vector(arr):<br>
&#9;s = set()<br>
&#9;for a in arr:<br>
&#9;&#9;for index in a.idxs:<br>
&#9;&#9;&#9;s.add(index)<br>
&#9;return sorted(list(s))<br>
<br>
<br>
def full_indexes_list_matrix(arr, lidxs=None, ridxs=None):<br>
&#9;l = set()<br>
&#9;r = set()<br>
&#9;for a in arr:<br>
&#9;&#9;if lidxs is None:<br>
&#9;&#9;&#9;for index in a.lidxs:<br>
&#9;&#9;&#9;&#9;l.add(index)<br>
&#9;&#9;if ridxs is None:<br>
&#9;&#9;&#9;for index in a.ridxs:<br>
&#9;&#9;&#9;&#9;r.add(index)<br>
<br>
&#9;lidxs = lidxs if lidxs is not None else sorted(list(l))<br>
&#9;ridxs = ridxs if ridxs is not None else sorted(list(r))<br>
<br>
&#9;return lidxs, ridxs<br>
<br>
<br>
def symmetric_full_indexes_list_matrix(arr, idxs=None):<br>
&#9;l = set()<br>
&#9;for a in arr:<br>
&#9;&#9;if idxs is None:<br>
&#9;&#9;&#9;for index in a.lidxs:<br>
&#9;&#9;&#9;&#9;l.add(index)<br>
<br>
&#9;idxs = idxs if idxs is not None else sorted(list(l))<br>
&#9;return idxs<br>
<br>
def symmetric_matrix_numbers(Aarr):<br>
&#9;res = []<br>
&#9;counter = 0<br>
&#9;for A in Aarr:<br>
&#9;&#9;res.append((counter, counter + A.matrix.shape[0]))<br>
&#9;&#9;counter += A.matrix.shape[0]<br>
&#9;return res<br>
<br>
def indexed_matrix_summation(arr, lidxs=None, ridxs=None):<br>
&#9;lidxs, ridxs = full_indexes_list_matrix(arr, lidxs=lidxs, ridxs=ridxs)<br>
<br>
&#9;result_matrix = IndexedMatrix(numpy.zeros(<br>
&#9;&#9;(len(lidxs), len(ridxs))), lidxs, ridxs)<br>
&#9;for m in arr:<br>
&#9;&#9;result_matrix.accumulate_from(m)<br>
&#9;return result_matrix<br>
<br>
<br>
def symmetric_indexed_matrix_summation(arr, idxs=None):<br>
&#9;numbers = symmetric_matrix_numbers(arr)<br>
&#9;idxs = symmetric_full_indexes_list_matrix(<br>
&#9;&#9;arr, idxs=idxs)<br>
<br>
&#9;result_matrix = IndexedMatrix(numpy.zeros(<br>
&#9;&#9;(len(idxs), len(idxs))), idxs, idxs)<br>
<br>
#    for i in range(len(arr)):<br>
#        A_view = result_matrix.matrix[numbers[i][0]:numbers[i][1], numbers[i][0]:numbers[i][1]]<br>
#        A_view += arr[i].matrix<br>
<br>
&#9;for m in arr:<br>
&#9;&#9;result_matrix.accumulate_from(m)<br>
&#9;return result_matrix<br>
<br>
<br>
def indexed_vector_summation(arr, idxs=None):<br>
&#9;if idxs is None:<br>
&#9;&#9;idxs = full_indexes_list_vector(arr)<br>
&#9;result_vector = IndexedVector(numpy.zeros(<br>
&#9;&#9;(len(idxs))), idxs)<br>
&#9;for m in arr:<br>
&#9;&#9;result_vector.accumulate_from(m)<br>
&#9;return result_vector<br>
<br>
<br>
def invoke_set_values_for_indexed_vector(self, indexed_vector):<br>
&#9;indexes = indexed_vector.idxs<br>
&#9;values = indexed_vector.matrix<br>
&#9;for idx, val in zip(indexes, values):<br>
&#9;&#9;idx.set_value(val)<br>
<br>
def commutator_list_indexes(commutator_list):<br>
&#9;indexes = {}<br>
&#9;counter = 0<br>
&#9;for commutator in commutator_list:<br>
&#9;&#9;indexes[commutator] = (counter, counter + commutator.dim())<br>
&#9;&#9;counter += commutator.dim()<br>
&#9;return indexes, counter<br>
<br>
def qpc_solver_indexes_array(<br>
&#9;&#9;Aarr: list, <br>
&#9;&#9;Carr: list, <br>
&#9;&#9;Barr: list = [], <br>
&#9;&#9;Darr: list = [],<br>
&#9;&#9;Harr: list = [],<br>
&#9;&#9;Ksiarr: list = []):<br>
&#9;A_counter = 0<br>
&#9;B_counter = 0<br>
&#9;H_counter = 0<br>
&#9;D_counter = 0<br>
&#9;A_idxs = []<br>
&#9;B_idxs = []<br>
&#9;H_idxs = []<br>
&#9;D_idxs = []<br>
&#9;commutator_list_unique = []<br>
&#9;for A in Aarr:<br>
&#9;&#9;if A.lcomm in commutator_list_unique:<br>
&#9;&#9;&#9;continue<br>
&#9;&#9;commutator_list_unique.append(A.lcomm)<br>
&#9;&#9;A_counter += A.lcomm.dim()<br>
&#9;&#9;A_idxs.extend(A.lidxs)<br>
&#9;for B in Barr:<br>
&#9;&#9;if B.rcomm in commutator_list_unique:<br>
&#9;&#9;&#9;continue<br>
&#9;&#9;commutator_list_unique.append(B.rcomm)<br>
&#9;&#9;B_counter += B.rcomm.dim()<br>
&#9;&#9;B_idxs.extend(B.ridxs)<br>
&#9;for H in Harr:<br>
&#9;&#9;if H.rcomm in commutator_list_unique:<br>
&#9;&#9;&#9;continue<br>
&#9;&#9;commutator_list_unique.append(H.rcomm)<br>
&#9;&#9;H_counter += H.rcomm.dim()<br>
&#9;&#9;H_idxs.extend(H.ridxs)<br>
&#9;for D in Darr:<br>
&#9;&#9;if D.comm in commutator_list_unique:<br>
&#9;&#9;&#9;continue<br>
&#9;&#9;commutator_list_unique.append(D.comm)<br>
&#9;&#9;D_counter += D.comm.dim()<br>
&#9;&#9;D_idxs.extend(D.idxs)<br>
<br>
&#9;#commutator_list_unique = list(set(commutator_list))<br>
&#9;indexes, fulldim = commutator_list_indexes(commutator_list_unique)<br>
&#9;<br>
&#9;Q = numpy.zeros((fulldim, fulldim))<br>
&#9;b = numpy.zeros((fulldim, 1))<br>
&#9;for A in Aarr:<br>
&#9;&#9;Q[indexes[A.lcomm][0]:indexes[A.lcomm][1], indexes[A.lcomm][0]:indexes[A.lcomm][1]] += A.matrix<br>
&#9;for B in Barr:<br>
&#9;&#9;Q[indexes[B.lcomm][0]:indexes[B.lcomm][1], indexes[B.rcomm][0]:indexes[B.rcomm][1]] += B.matrix<br>
&#9;&#9;Q[indexes[B.rcomm][0]:indexes[B.rcomm][1], indexes[B.lcomm][0]:indexes[B.lcomm][1]] += B.matrix.T<br>
&#9;for H in Harr:<br>
&#9;&#9;Q[indexes[H.lcomm][0]:indexes[H.lcomm][1], indexes[H.rcomm][0]:indexes[H.rcomm][1]] += H.matrix<br>
&#9;&#9;Q[indexes[H.rcomm][0]:indexes[H.rcomm][1], indexes[H.lcomm][0]:indexes[H.lcomm][1]] += H.matrix.T<br>
<br>
&#9;for C in Carr:<br>
&#9;&#9;b[indexes[C.comm][0]:indexes[C.comm][1], 0] += C.matrix<br>
&#9;for D in Darr:<br>
&#9;&#9;b[indexes[D.comm][0]:indexes[D.comm][1], 0] += D.matrix<br>
&#9;for Ksi in Ksiarr:<br>
&#9;&#9;b[indexes[Ksi.comm][0]:indexes[Ksi.comm][1], 0] += Ksi.matrix<br>
<br>
&#9;Q_torch = torch.tensor(Q, dtype=torch.float64).to(device=TORCH_DEVICE)<br>
&#9;b_torch = torch.tensor(b, dtype=torch.float64).to(device=TORCH_DEVICE)<br>
<br>
&#9;#X = numpy.linalg.inv(Q) @ b<br>
&#9;#X_torch = torch.linalg.solve(Q_torch, b_torch)<br>
&#9;X_torch = torch.pinverse(Q_torch) @ b_torch<br>
&#9;X = X_torch.cpu().detach().numpy()<br>
&#9;#X = numpy.linalg.solve(Q, b)<br>
<br>
&#9;X = X_torch<br>
<br>
&#9;X = X.reshape((X.shape[0],))<br>
&#9;x = X[:len(A_idxs)]<br>
&#9;l = X[len(A_idxs):len(A_idxs) + len(B_idxs)]<br>
&#9;ksi = X[len(A_idxs) + len(B_idxs):]<br>
&#9;<br>
&#9;x = x.cpu().detach().numpy()<br>
&#9;l = l.cpu().detach().numpy()<br>
&#9;ksi = ksi.cpu().detach().numpy()<br>
<br>
&#9;return (IndexedVector(x, idxs=A_idxs), <br>
&#9;&#9;IndexedVector(l, idxs=B_idxs), <br>
&#9;&#9;IndexedVector(ksi, idxs=H_idxs), Q, b)<br>
<!-- END SCAT CODE -->
</body>
</html>
