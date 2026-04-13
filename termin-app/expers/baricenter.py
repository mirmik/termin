#!/usr/bin/env python3

import numpy as np

a = np.array([2, 0, 0])
b = np.array([0, 2, 0])
c = np.array([0, 0, 0])
d = np.cross((a-c), (b-c))
d = d / np.linalg.norm(d)

a = a.reshape(3, 1)
b = b.reshape(3, 1)
c = c.reshape(3, 1)
d = d.reshape(3, 1)

p = np.array([2, 2, 15, 1])

A = np.hstack([a, b, c, d])
A = np.vstack([A, np.array([1, 1, 1, 0]).T])

print()
print(A)
print(np.linalg.inv(A))
print(np.linalg.inv(A).dot(p))

e = np.cross((b.reshape(3,) - a.reshape(3,)), (d.reshape(3,)))
e = e / np.linalg.norm(e)
e = e.reshape(3, 1)

a = a[:2, :]
b = b[:2, :]
e = e[:2, :]

B = np.hstack([a, b, e])
B = np.vstack([B, np.array([1, 1, 0]).T])

print()
print(B)
print(np.linalg.inv(B))

p = np.hstack((p[:2], np.array([1])))
print(np.linalg.inv(B).dot(p))
