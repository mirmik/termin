#!/usr/bin/env python3

import torch

geomproduct_left_operator_template = torch.tensor([
    [
        [1, 0, 0, 0, 0, 0, 0, 0],
        [0, 1, 0, 0, 0, 0, 0, 0],
        [0, 0, 1, 0, 0, 0, 0, 0],
        [0, 0, 0, 1, 0, 0, 0, 0],
        [0, 0, 0, 0, 1, 0, 0, 0],
        [0, 0, 0, 0, 0, 1, 0, 0],
        [0, 0, 0, -2, 0, 0, 1, 0],
        [0, 0, 0, 0, 0, 0, 0, 1],
    ]
])
geomproduct_left_operator_sign = geomproduct_left_operator_template.sign()
geomproduct_left_operator_indexes = geomproduct_left_operator_template.abs()


def multivector(e=0, e1=0, e2=0, e3=0, e23=0, e31=0, e12=0, e321=0):
    return torch.tensor([e, e1, e2, e3, e23, e31, e12, e321])


def vector(x, y, z=0):
    return multivector(e1=x, e2=y, e3=z)


def realbivector(x, y):
    return multivector(e23=x, e31=y)


def dualbivector(x, y):
    return multivector(e31=x, e32=y)


def bivector(rx, ry, dx, dy):
    return realbivector(rx, ry) + dualbivector(dx, dy)


def scalar(s):
    return multivector(e=s)


def pseudoscalar(p):
    return multivector(e321=p)


def geomproduct_left_operator(m):
    return m[geomproduct_left_operator_indexes] * geomproduct_left_operator_sign


def geomprod(a, b):
    return geomproduct_left_operator(a) @ b


#print(geomprod(vector(1, 4, 3), vector(1, 2, 3)))


A = torch.tensor(
    [
        [
            [1, 0, 2],
            [0, 1, 0],
            [0, 0, 1]
        ],
        [
            [1, 0, 0],
            [0, 0, 0],
            [0, 0, 0]
        ],

        [
            [1, 0, 0],
            [0, 0, 0],
            [0, 0, 0]
        ]
    ],
)

print(A.shape)

a = torch.tensor([
    [1, 1, 1],
    [0, 1, 0]
])
b = torch.tensor([
    [1, 1, 1],
    [10, 10, 10]
]).permute(1, 0)

print("a@A")
print(a@A)
print("A@b")
print(A@b)
print("a@A@b")
print((a@A@b).permute(2, 1, 0))
print((a@A@b).shape)
