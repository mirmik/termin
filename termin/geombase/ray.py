import numpy as np

class Ray3:
    """
    Простой луч в 3D:
    origin — начало
    direction — нормализованное направление
    """

    __slots__ = ('origin', 'direction')

    def __init__(self, origin: np.ndarray, direction: np.ndarray):
        self.origin = np.asarray(origin, dtype=np.float32)
        d = np.asarray(direction, dtype=np.float32)
        n = np.linalg.norm(d)
        self.direction = d / n if n > 1e-8 else np.array([0, 0, 1], dtype=np.float32)

    def point_at(self, t: float):
        """
        Возвращает точку на луче при параметре t:
        P(t) = origin + direction * t
        """
        return self.origin + self.direction * float(t)

    def __repr__(self):
        return f"Ray3(origin={self.origin}, direction={self.direction})"