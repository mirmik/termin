import numpy as np

def outkernel_operator(matrix):
    return matrix @ numpy.linalg.pinv(matrix)

def kernel_operator(matrix):
    outkernel = outkernel_operator(matrix)
    return numpy.eye(matrix.shape[0]) - outkernel
