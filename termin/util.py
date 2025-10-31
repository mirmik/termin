import math
import numpy

def qmul(q1: numpy.ndarray, q2: numpy.ndarray) -> numpy.ndarray:
    """Multiply two quaternions."""
    x1, y1, z1, w1 = q1
    x2, y2, z2, w2 = q2
    return numpy.array([
        w1*x2 + x1*w2 + y1*z2 - z1*y2,
        w1*y2 - x1*z2 + y1*w2 + z1*x2,
        w1*z2 + x1*y2 - y1*x2 + z1*w2,
        w1*w2 - x1*x2 - y1*y2 - z1*z2
    ])

def qmul_vector(q: numpy.ndarray, v: numpy.ndarray) -> numpy.ndarray:
    x1, y1, z1, w1 = q
    x2, y2, z2 = v
    return numpy.array([
        w1*x2         + y1*z2 - z1*y2,
        w1*y2 - x1*z2         + z1*x2,
        w1*z2 + x1*y2 - y1*x2,
              - x1*x2 - y1*y2 - z1*z2
    ])


def qrot(q: numpy.ndarray, v: numpy.ndarray) -> numpy.ndarray:
    """Rotate vector v by quaternion q."""
    q_conj = numpy.array([-q[0], -q[1], -q[2], q[3]])
    rotated_v = qmul(qmul_vector(q, v), q_conj)
    return rotated_v[:3]

def qslerp(q1: numpy.ndarray, q2: numpy.ndarray, t: float) -> numpy.ndarray:
    """Spherical linear interpolation between two quaternions."""
    dot = numpy.dot(q1, q2)
    if dot < 0.0:
        q2 = -q2
        dot = -dot

    DOT_THRESHOLD = 0.9995
    if dot > DOT_THRESHOLD:
        result = q1 + t * (q2 - q1)
        return result / numpy.linalg.norm(result)

    theta_0 = math.acos(dot)
    theta = theta_0 * t
    sin_theta = math.sin(theta)
    sin_theta_0 = math.sin(theta_0)

    s1 = math.cos(theta) - dot * sin_theta / sin_theta_0
    s2 = sin_theta / sin_theta_0

    return (s1 * q1) + (s2 * q2)

def deg2rad(deg):
    return deg / 180.0 * math.pi