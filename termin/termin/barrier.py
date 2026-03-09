#/usr/bin/env python3

import math

def shotki_barrier(b, l):
    def func(x):
        if x >= l: 
            return 0
        return b/x + b*x/(l**2) - 2*b/l
    return func

def alpha_function(l, k):
    l2 = l * k
    a = 1/(k-1)/l
    b = - 1/(k-1)
    def func(x):
        if x > l: 
            return 0
        elif x < l2:
            return 1
        else:
            return a*x+b
    return func

        