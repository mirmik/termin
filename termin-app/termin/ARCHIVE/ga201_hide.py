#!/usr/bin/env python3

import numpy

class multivector:
    grade_dims = [1, 3, 3, 1]
    exterior_dim = sum(grade_dims)

    def __init__(self, array):
        if len(array) != self.exterior_dim:
            raise Exception("wrong dimension")
        self.array = array

    def __add__(self, other):
        return multivector(self.array + other.array)

    def __sub__(self, other):
        return multivector(self.array - other.array)

    def expand(self):
        A = self.array
        return A[0], A[1], A[2], A[3], A[4], A[5], A[6], A[7]
        
    def to_left_prod_operator(self):
        a, a1, a2, a3, a12, a31, a23, a321 = self.expand()
        return numpy.array([
                #e    #e1   #e2       #e3   #e12  #e31   #e23   #e321
             [   a,    a1,    a2,      0,  -a12,     0,     0,     0], 
             [  a1,     a,   a12,      0,   -a2,     0,     0,     0], 
             [  a2,  -a12,     a,      0,    a1,     0,     0,     0], 
             [  a3,   a31,  -a23,      a,  a321,   -a1,    a2,   a12], 
             [ a12,   -a2,    a1,      0,     a,     0,     0,     0], 
             [ a31,    a3, -a321,    -a1,   a23,     a,  -a12,   -a2], 
             [ a23, -a321,   -a3,     a2,  -a31,   a12,     a,   -a1], 
             [a321,  -a23,  -a31,   -a12,   -a3,   -a2,   -a1,      a]])

    def __str__(self):
        return str(self.array)
        

if __name__ == "__main__":
    a = multivector(numpy.array([1, 2, 3, 4, 5, 6, 7, 8]))

    print(a.to_left_prod_operator() @ a.array)
    print(a.expand())