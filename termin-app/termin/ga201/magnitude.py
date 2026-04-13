


class Magnitude:
    def __init__(self, v, w):
        self.v = v
        self.w = w

    def __str__(self):
        return str((self.v, self.w))

    def unitize(self):
        return Magnitude(
            self.v / self.w,
            1
        )

    def to_float(self):
        return self.v / self.w

    def __abs__(self):
        return Magnitude(abs(self.v), abs(self.w))