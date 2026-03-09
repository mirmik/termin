import torch

geomproduct_left_operator_indexes = [
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
]


def multivector(e=0, e1=0, e2=0, e3=0, e4=0, e23=0, e31=0, e12=0, e43=0, e42=0, e41=0, e321=0, e412=0, e431=0, e423=0, e1234=0):
    return torch.tensor([e, e1, e2, e3, e4, e23, e31, e12, e43, e42, e41, e321, e412, e431, e423, e1234])


def vector(x, y, z, w=0):
    return multivector(e1=x, e2=y, e3=z, e4=w)


def realbivector(x, y, z):
    return multivector(e23=x, e31=y, e12=z)


def dualbivector(x, y, z):
    return multivector(e41=x, e42=y, e43=z)


def bivector(rx, ry, rz, dx, dy, dz):
    return realbivector(rx, ry, rz) + dualbivector(dx, dy, dz)


def scalar(s):
    return multivector(e=s)


def pseudoscalar(p):
    return multivector(e1234=p)


def geomproduct_left_operator(m):
