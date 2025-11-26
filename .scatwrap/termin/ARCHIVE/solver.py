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
    s = set()<br>
    for a in arr:<br>
        for index in a.idxs:<br>
            s.add(index)<br>
    return sorted(list(s))<br>
<br>
<br>
def full_indexes_list_matrix(arr, lidxs=None, ridxs=None):<br>
    l = set()<br>
    r = set()<br>
    for a in arr:<br>
        if lidxs is None:<br>
            for index in a.lidxs:<br>
                l.add(index)<br>
        if ridxs is None:<br>
            for index in a.ridxs:<br>
                r.add(index)<br>
<br>
    lidxs = lidxs if lidxs is not None else sorted(list(l))<br>
    ridxs = ridxs if ridxs is not None else sorted(list(r))<br>
<br>
    return lidxs, ridxs<br>
<br>
<br>
def symmetric_full_indexes_list_matrix(arr, idxs=None):<br>
    l = set()<br>
    for a in arr:<br>
        if idxs is None:<br>
            for index in a.lidxs:<br>
                l.add(index)<br>
<br>
    idxs = idxs if idxs is not None else sorted(list(l))<br>
    return idxs<br>
<br>
def symmetric_matrix_numbers(Aarr):<br>
    res = []<br>
    counter = 0<br>
    for A in Aarr:<br>
        res.append((counter, counter + A.matrix.shape[0]))<br>
        counter += A.matrix.shape[0]<br>
    return res<br>
<br>
def indexed_matrix_summation(arr, lidxs=None, ridxs=None):<br>
    lidxs, ridxs = full_indexes_list_matrix(arr, lidxs=lidxs, ridxs=ridxs)<br>
<br>
    result_matrix = IndexedMatrix(numpy.zeros(<br>
        (len(lidxs), len(ridxs))), lidxs, ridxs)<br>
    for m in arr:<br>
        result_matrix.accumulate_from(m)<br>
    return result_matrix<br>
<br>
<br>
def symmetric_indexed_matrix_summation(arr, idxs=None):<br>
    numbers = symmetric_matrix_numbers(arr)<br>
    idxs = symmetric_full_indexes_list_matrix(<br>
        arr, idxs=idxs)<br>
<br>
    result_matrix = IndexedMatrix(numpy.zeros(<br>
        (len(idxs), len(idxs))), idxs, idxs)<br>
<br>
#    for i in range(len(arr)):<br>
#        A_view = result_matrix.matrix[numbers[i][0]:numbers[i][1], numbers[i][0]:numbers[i][1]]<br>
#        A_view += arr[i].matrix<br>
<br>
    for m in arr:<br>
        result_matrix.accumulate_from(m)<br>
    return result_matrix<br>
<br>
<br>
def indexed_vector_summation(arr, idxs=None):<br>
    if idxs is None:<br>
        idxs = full_indexes_list_vector(arr)<br>
    result_vector = IndexedVector(numpy.zeros(<br>
        (len(idxs))), idxs)<br>
    for m in arr:<br>
        result_vector.accumulate_from(m)<br>
    return result_vector<br>
<br>
<br>
def invoke_set_values_for_indexed_vector(self, indexed_vector):<br>
    indexes = indexed_vector.idxs<br>
    values = indexed_vector.matrix<br>
    for idx, val in zip(indexes, values):<br>
        idx.set_value(val)<br>
<br>
def commutator_list_indexes(commutator_list):<br>
    indexes = {}<br>
    counter = 0<br>
    for commutator in commutator_list:<br>
        indexes[commutator] = (counter, counter + commutator.dim())<br>
        counter += commutator.dim()<br>
    return indexes, counter<br>
<br>
def qpc_solver_indexes_array(<br>
        Aarr: list, <br>
        Carr: list, <br>
        Barr: list = [], <br>
        Darr: list = [],<br>
        Harr: list = [],<br>
        Ksiarr: list = []):<br>
    A_counter = 0<br>
    B_counter = 0<br>
    H_counter = 0<br>
    D_counter = 0<br>
    A_idxs = []<br>
    B_idxs = []<br>
    H_idxs = []<br>
    D_idxs = []<br>
    commutator_list_unique = []<br>
    for A in Aarr:<br>
        if A.lcomm in commutator_list_unique:<br>
            continue<br>
        commutator_list_unique.append(A.lcomm)<br>
        A_counter += A.lcomm.dim()<br>
        A_idxs.extend(A.lidxs)<br>
    for B in Barr:<br>
        if B.rcomm in commutator_list_unique:<br>
            continue<br>
        commutator_list_unique.append(B.rcomm)<br>
        B_counter += B.rcomm.dim()<br>
        B_idxs.extend(B.ridxs)<br>
    for H in Harr:<br>
        if H.rcomm in commutator_list_unique:<br>
            continue<br>
        commutator_list_unique.append(H.rcomm)<br>
        H_counter += H.rcomm.dim()<br>
        H_idxs.extend(H.ridxs)<br>
    for D in Darr:<br>
        if D.comm in commutator_list_unique:<br>
            continue<br>
        commutator_list_unique.append(D.comm)<br>
        D_counter += D.comm.dim()<br>
        D_idxs.extend(D.idxs)<br>
<br>
    #commutator_list_unique = list(set(commutator_list))<br>
    indexes, fulldim = commutator_list_indexes(commutator_list_unique)<br>
    <br>
    Q = numpy.zeros((fulldim, fulldim))<br>
    b = numpy.zeros((fulldim, 1))<br>
    for A in Aarr:<br>
        Q[indexes[A.lcomm][0]:indexes[A.lcomm][1], indexes[A.lcomm][0]:indexes[A.lcomm][1]] += A.matrix<br>
    for B in Barr:<br>
        Q[indexes[B.lcomm][0]:indexes[B.lcomm][1], indexes[B.rcomm][0]:indexes[B.rcomm][1]] += B.matrix<br>
        Q[indexes[B.rcomm][0]:indexes[B.rcomm][1], indexes[B.lcomm][0]:indexes[B.lcomm][1]] += B.matrix.T<br>
    for H in Harr:<br>
        Q[indexes[H.lcomm][0]:indexes[H.lcomm][1], indexes[H.rcomm][0]:indexes[H.rcomm][1]] += H.matrix<br>
        Q[indexes[H.rcomm][0]:indexes[H.rcomm][1], indexes[H.lcomm][0]:indexes[H.lcomm][1]] += H.matrix.T<br>
<br>
    for C in Carr:<br>
        b[indexes[C.comm][0]:indexes[C.comm][1], 0] += C.matrix<br>
    for D in Darr:<br>
        b[indexes[D.comm][0]:indexes[D.comm][1], 0] += D.matrix<br>
    for Ksi in Ksiarr:<br>
        b[indexes[Ksi.comm][0]:indexes[Ksi.comm][1], 0] += Ksi.matrix<br>
<br>
    Q_torch = torch.tensor(Q, dtype=torch.float64).to(device=TORCH_DEVICE)<br>
    b_torch = torch.tensor(b, dtype=torch.float64).to(device=TORCH_DEVICE)<br>
<br>
    #X = numpy.linalg.inv(Q) @ b<br>
    #X_torch = torch.linalg.solve(Q_torch, b_torch)<br>
    X_torch = torch.pinverse(Q_torch) @ b_torch<br>
    X = X_torch.cpu().detach().numpy()<br>
    #X = numpy.linalg.solve(Q, b)<br>
<br>
    X = X_torch<br>
<br>
    X = X.reshape((X.shape[0],))<br>
    x = X[:len(A_idxs)]<br>
    l = X[len(A_idxs):len(A_idxs) + len(B_idxs)]<br>
    ksi = X[len(A_idxs) + len(B_idxs):]<br>
    <br>
    x = x.cpu().detach().numpy()<br>
    l = l.cpu().detach().numpy()<br>
    ksi = ksi.cpu().detach().numpy()<br>
<br>
    return (IndexedVector(x, idxs=A_idxs), <br>
        IndexedVector(l, idxs=B_idxs), <br>
        IndexedVector(ksi, idxs=H_idxs), Q, b)<br>
<!-- END SCAT CODE -->
</body>
</html>
