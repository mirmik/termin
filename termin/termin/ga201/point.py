import math

class Point2:
    def __init__(self, x, y, z=1):
        self.x = x
        self.y = y
        self.z = z

    def __str__(self):
        return str((self.x, self.y, self.z))

    def __add__(self, other):
        return Point2(
            self.x + other.x,
            self.y + other.y,
            self.z + other.z
        )

    def __mul__(self, other):
        return Point2(
            self.x * other,
            self.y * other,
            self.z * other
        )

    def __sub__(self, other):
        return Point2(
            self.x - other.x,
            self.y - other.y,
            self.z - other.z
        )

    def __truediv__(self, a):
        return Point2(
            self.x / a,
            self.y / a,
            self.z / a
        )

    def bulk_norm(self):
        return math.sqrt(self.x*self.x + self.y*self.y)

    def __str__(self):
        return str((self.x, self.y, self.z))

    def __repr__(self):
        return str(self)

    def unitized(self):
        return Point2(
            self.x / self.z,
            self.y / self.z,
            1
        )

    def is_infinite(self):
        return self.z == 0

def origin():
    return Point2(0, 0, 1)