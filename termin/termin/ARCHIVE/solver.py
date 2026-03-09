#!/usr/bin/env python3

import numpy
import scipy
from termin.physics.indexed_matrix import IndexedMatrix, IndexedVector
import torch

TORCH_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

def full_indexes_list_vector(arr):
    s = set()
    for a in arr:
        for index in a.idxs:
            s.add(index)
    return sorted(list(s))


def full_indexes_list_matrix(arr, lidxs=None, ridxs=None):
    l = set()
    r = set()
    for a in arr:
        if lidxs is None:
            for index in a.lidxs:
                l.add(index)
        if ridxs is None:
            for index in a.ridxs:
                r.add(index)

    lidxs = lidxs if lidxs is not None else sorted(list(l))
    ridxs = ridxs if ridxs is not None else sorted(list(r))

    return lidxs, ridxs


def symmetric_full_indexes_list_matrix(arr, idxs=None):
    l = set()
    for a in arr:
        if idxs is None:
            for index in a.lidxs:
                l.add(index)

    idxs = idxs if idxs is not None else sorted(list(l))
    return idxs

def symmetric_matrix_numbers(Aarr):
    res = []
    counter = 0
    for A in Aarr:
        res.append((counter, counter + A.matrix.shape[0]))
        counter += A.matrix.shape[0]
    return res

def indexed_matrix_summation(arr, lidxs=None, ridxs=None):
    lidxs, ridxs = full_indexes_list_matrix(arr, lidxs=lidxs, ridxs=ridxs)

    result_matrix = IndexedMatrix(numpy.zeros(
        (len(lidxs), len(ridxs))), lidxs, ridxs)
    for m in arr:
        result_matrix.accumulate_from(m)
    return result_matrix


def symmetric_indexed_matrix_summation(arr, idxs=None):
    numbers = symmetric_matrix_numbers(arr)
    idxs = symmetric_full_indexes_list_matrix(
        arr, idxs=idxs)

    result_matrix = IndexedMatrix(numpy.zeros(
        (len(idxs), len(idxs))), idxs, idxs)

#    for i in range(len(arr)):
#        A_view = result_matrix.matrix[numbers[i][0]:numbers[i][1], numbers[i][0]:numbers[i][1]]
#        A_view += arr[i].matrix

    for m in arr:
        result_matrix.accumulate_from(m)
    return result_matrix


def indexed_vector_summation(arr, idxs=None):
    if idxs is None:
        idxs = full_indexes_list_vector(arr)
    result_vector = IndexedVector(numpy.zeros(
        (len(idxs))), idxs)
    for m in arr:
        result_vector.accumulate_from(m)
    return result_vector


def invoke_set_values_for_indexed_vector(self, indexed_vector):
    indexes = indexed_vector.idxs
    values = indexed_vector.matrix
    for idx, val in zip(indexes, values):
        idx.set_value(val)

def commutator_list_indexes(commutator_list):
    indexes = {}
    counter = 0
    for commutator in commutator_list:
        indexes[commutator] = (counter, counter + commutator.dim())
        counter += commutator.dim()
    return indexes, counter

def qpc_solver_indexes_array(
        Aarr: list, 
        Carr: list, 
        Barr: list = [], 
        Darr: list = [],
        Harr: list = [],
        Ksiarr: list = []):
    A_counter = 0
    B_counter = 0
    H_counter = 0
    D_counter = 0
    A_idxs = []
    B_idxs = []
    H_idxs = []
    D_idxs = []
    commutator_list_unique = []
    for A in Aarr:
        if A.lcomm in commutator_list_unique:
            continue
        commutator_list_unique.append(A.lcomm)
        A_counter += A.lcomm.dim()
        A_idxs.extend(A.lidxs)
    for B in Barr:
        if B.rcomm in commutator_list_unique:
            continue
        commutator_list_unique.append(B.rcomm)
        B_counter += B.rcomm.dim()
        B_idxs.extend(B.ridxs)
    for H in Harr:
        if H.rcomm in commutator_list_unique:
            continue
        commutator_list_unique.append(H.rcomm)
        H_counter += H.rcomm.dim()
        H_idxs.extend(H.ridxs)
    for D in Darr:
        if D.comm in commutator_list_unique:
            continue
        commutator_list_unique.append(D.comm)
        D_counter += D.comm.dim()
        D_idxs.extend(D.idxs)

    #commutator_list_unique = list(set(commutator_list))
    indexes, fulldim = commutator_list_indexes(commutator_list_unique)
    
    Q = numpy.zeros((fulldim, fulldim))
    b = numpy.zeros((fulldim, 1))
    for A in Aarr:
        Q[indexes[A.lcomm][0]:indexes[A.lcomm][1], indexes[A.lcomm][0]:indexes[A.lcomm][1]] += A.matrix
    for B in Barr:
        Q[indexes[B.lcomm][0]:indexes[B.lcomm][1], indexes[B.rcomm][0]:indexes[B.rcomm][1]] += B.matrix
        Q[indexes[B.rcomm][0]:indexes[B.rcomm][1], indexes[B.lcomm][0]:indexes[B.lcomm][1]] += B.matrix.T
    for H in Harr:
        Q[indexes[H.lcomm][0]:indexes[H.lcomm][1], indexes[H.rcomm][0]:indexes[H.rcomm][1]] += H.matrix
        Q[indexes[H.rcomm][0]:indexes[H.rcomm][1], indexes[H.lcomm][0]:indexes[H.lcomm][1]] += H.matrix.T

    for C in Carr:
        b[indexes[C.comm][0]:indexes[C.comm][1], 0] += C.matrix
    for D in Darr:
        b[indexes[D.comm][0]:indexes[D.comm][1], 0] += D.matrix
    for Ksi in Ksiarr:
        b[indexes[Ksi.comm][0]:indexes[Ksi.comm][1], 0] += Ksi.matrix

    Q_torch = torch.tensor(Q, dtype=torch.float64).to(device=TORCH_DEVICE)
    b_torch = torch.tensor(b, dtype=torch.float64).to(device=TORCH_DEVICE)

    #X = numpy.linalg.inv(Q) @ b
    #X_torch = torch.linalg.solve(Q_torch, b_torch)
    X_torch = torch.pinverse(Q_torch) @ b_torch
    X = X_torch.cpu().detach().numpy()
    #X = numpy.linalg.solve(Q, b)

    X = X_torch

    X = X.reshape((X.shape[0],))
    x = X[:len(A_idxs)]
    l = X[len(A_idxs):len(A_idxs) + len(B_idxs)]
    ksi = X[len(A_idxs) + len(B_idxs):]
    
    x = x.cpu().detach().numpy()
    l = l.cpu().detach().numpy()
    ksi = ksi.cpu().detach().numpy()

    return (IndexedVector(x, idxs=A_idxs), 
        IndexedVector(l, idxs=B_idxs), 
        IndexedVector(ksi, idxs=H_idxs), Q, b)
