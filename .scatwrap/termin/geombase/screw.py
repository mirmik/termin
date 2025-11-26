<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/geombase/screw.py</title>
</head>
<body>
<pre><code>
import numpy
import math
from .pose3 import Pose3

def cross2d(scalar, vec):
    &quot;&quot;&quot;2D cross product: scalar × vector = [vy, -vx] * scalar&quot;&quot;&quot;
    return scalar * numpy.array([vec[1], -vec[0]])

def cross2d_scalar(vec1, vec2):
    &quot;&quot;&quot;2D cross product returning scalar: vec1 × vec2 = v1x*v2y - v1y*v2x&quot;&quot;&quot;
    return vec1[0]*vec2[1] - vec1[1]*vec2[0]

def cross2d_xz(vec, scalar):
    &quot;&quot;&quot;2D cross product for twist transformation: vector × scalar = [-sy, sx]&quot;&quot;&quot;
    return numpy.array([-scalar * vec[1], scalar * vec[0]])

class Screw:
    &quot;&quot;&quot;A class representing a pair of vector and bivector&quot;&quot;&quot;
    def __init__(self, ang, lin):
        self.ang = ang  # Bivector part
        self.lin = lin  # Vector part

        if not isinstance(self.ang, numpy.ndarray):
            raise Exception(&quot;ang must be ndarray&quot;)

        if not isinstance(self.lin, numpy.ndarray):
            raise Exception(&quot;lin must be ndarray&quot;)

    def __repr__(self):
        return f&quot;Screw(ang={self.ang}, lin={self.lin})&quot;

class Screw2(Screw):
    &quot;&quot;&quot;A 2D Screw specialized for planar motions.&quot;&quot;&quot;
    def __init__(self, ang: numpy.ndarray, lin: numpy.ndarray):

        if not isinstance(ang, numpy.ndarray):
            ang = numpy.array(ang)

        # # check shapes
        # if ang.shape != (1,) and ang.shape != ():
        #     raise Exception(&quot;ang must be a scalar or shape (1,) ndarray&quot;)

        # if lin.shape != (2,):
        #     raise Exception(f&quot;lin must be shape (2,) ndarray, got {lin.shape}&quot;)

        ang = ang.reshape(1)
        lin = lin.reshape(2)

        super().__init__(ang=ang, lin=lin)

    def moment(self) -&gt; float:
        &quot;&quot;&quot;Return the moment (bivector part) of the screw.&quot;&quot;&quot;
        return self.ang.item() if self.ang.shape == () or self.ang.shape == (1,) else self.ang[0]

    def vector(self) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Return the vector part of the screw.&quot;&quot;&quot;
        return self.lin

    def kinematic_carry(self, arm: &quot;Vector2&quot;) -&gt; &quot;Screw2&quot;:
        &quot;&quot;&quot;Twist transform. Carry the screw by arm. For pair of angular and linear speeds.&quot;&quot;&quot;
        return Screw2(
            lin=self.lin + cross2d(self.moment(), arm),
            ang=self.ang)

    def force_carry(self, arm: &quot;Vector2&quot;) -&gt; &quot;Screw2&quot;:
        &quot;&quot;&quot;Wrench transform. Carry the screw by arm. For pair of torques and forces.&quot;&quot;&quot;
        return Screw2(
            ang=self.ang - numpy.array([cross2d_scalar(arm, self.lin)]),
            lin=self.lin)

    def twist_carry(self, arm: &quot;Vector2&quot;) -&gt; &quot;Screw2&quot;:
        &quot;&quot;&quot;Alias for kinematic_carry.&quot;&quot;&quot;
        return self.kinematic_carry(arm)

    def wrench_carry(self, arm: &quot;Vector2&quot;) -&gt; &quot;Screw2&quot;:
        &quot;&quot;&quot;Alias for force_carry.&quot;&quot;&quot;
        return self.force_carry(arm)

    def transform_by(self, trans):
        return Screw2(ang=self.ang, lin=trans.transform_vector(self.lin))

    def rotated_by(self, trans):
        return Screw2(ang=self.ang, lin=trans.rotate_vector(self.lin))

    def inverse_transform_by(self, trans):
        return Screw2(ang=self.ang, lin=trans.inverse_transform_vector(self.lin))

    def transform_as_twist_by(self, trans):
        rlin = trans.transform_vector(self.lin)
        return Screw2(
            lin=rlin + cross2d_xz(trans.lin, self.moment()),
            ang=self.ang,
        )

    def inverse_transform_as_twist_by(self, trans):
        return Screw2(
            ang=self.ang,
            lin=trans.inverse_transform_vector(self.lin - cross2d_xz(trans.lin, self.moment()))
        )

    def transform_as_wrench_by(self, trans):
        &quot;&quot;&quot;Transform wrench (moment + force) under SE(2) transform.&quot;&quot;&quot;
        return Screw2(
            ang=self.ang + numpy.array([cross2d_scalar(trans.lin, self.lin)]),
            lin=trans.transform_vector(self.lin)
        )

    def inverse_transform_as_wrench_by(self, trans):
        &quot;&quot;&quot;Inverse transform of a wrench under SE(2) transform.&quot;&quot;&quot;
        return Screw2(
            ang=self.ang - numpy.array([cross2d_scalar(trans.lin, self.lin)]),
            lin=trans.inverse_transform_vector(self.lin)
        )

    def __mul__(self, oth):
        return Screw2(self.ang * oth, self.lin * oth)

    def __add__(self, oth):
        return Screw2(self.ang + oth.ang, self.lin + oth.lin)

    def __sub__(self, oth):
        return Screw2(self.ang - oth.ang, self.lin - oth.lin)

    def to_vector_vw_order(self) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Return the screw as a 3x1 array in [vx, vy, w] order.&quot;&quot;&quot;
        return numpy.array([self.lin[0], self.lin[1], self.moment()], float)

    def to_vector_wv_order(self) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Return the screw as a 3x1 array in [w, vx, vy] order.&quot;&quot;&quot;
        return numpy.array([self.moment(), self.lin[0], self.lin[1]], float)

    def from_vector_vw_order(vec: numpy.ndarray) -&gt; &quot;Screw2&quot;:
        &quot;&quot;&quot;Create a Screw2 from a 3x1 array in [vx, vy, w] order.&quot;&quot;&quot;
        if vec.shape != (3,):
            raise Exception(&quot;Input vector must be of shape (3,)&quot;)

        return Screw2(
            ang=numpy.array([vec[2]]),
            lin=numpy.array([vec[0], vec[1]])
        )

    def from_vector_wv_order(vec: numpy.ndarray) -&gt; &quot;Screw2&quot;:
        &quot;&quot;&quot;Create a Screw2 from a 3x1 array in [w, vx, vy] order.&quot;&quot;&quot;
        if vec.shape != (3,):
            raise Exception(&quot;Input vector must be of shape (3,)&quot;)

        return Screw2(
            ang=numpy.array([vec[0]]),
            lin=numpy.array([vec[1], vec[2]])
        )

    def to_pose(self):
        &quot;&quot;&quot;Convert the screw to a Pose2 representation (for small motions).&quot;&quot;&quot;
        return Pose2(
            ang=self.moment(),
            lin=self.lin
        )

class Screw3(Screw):
    &quot;&quot;&quot;A 3D Screw specialized for spatial motions.&quot;&quot;&quot;
    def __init__(self, ang: numpy.ndarray = numpy.array([0,0,0]), lin: numpy.ndarray = numpy.array([0,0,0])):
        super().__init__(ang=ang, lin=lin)

    def moment(self) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Return the moment (bivector part) of the screw.&quot;&quot;&quot;
        return self.ang

    def vector(self) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Return the vector part of the screw.&quot;&quot;&quot;
        return self.lin

    def kinematic_carry(self, arm: &quot;Vector3&quot;) -&gt; &quot;Screw3&quot;:
        &quot;&quot;&quot;Twist transform. Carry the screw by arm. For pair of angular and linear speeds.&quot;&quot;&quot;
        return Screw3(
            lin=self.lin + numpy.cross(self.ang, arm),
            ang=self.ang)

    def force_carry(self, arm: &quot;Vector3&quot;) -&gt; &quot;Screw3&quot;:
        &quot;&quot;&quot;Wrench transform. Carry the screw by arm. For pair of torques and forces.&quot;&quot;&quot;
        return Screw3(
            ang=self.ang - numpy.cross(arm, self.lin),
            lin=self.lin)

    def twist_carry(self, arm: &quot;Vector3&quot;) -&gt; &quot;Screw3&quot;:
        &quot;&quot;&quot;Alias for kinematic_carry.&quot;&quot;&quot;
        return self.kinematic_carry(arm)

    def wrench_carry(self, arm: &quot;Vector3&quot;) -&gt; &quot;Screw3&quot;:
        &quot;&quot;&quot;Alias for force_carry.&quot;&quot;&quot;
        return self.force_carry(arm)

    def transform_by(self, trans):
        return Screw3(
            ang=trans.transform_vector(self.ang),
            lin=trans.transform_vector(self.lin)
        )

    def rotate_by(self, rot):
        return Screw3(
            ang=rot.transform_vector(self.ang),
            lin=rot.transform_vector(self.lin)
        )

    def inverse_rotate_by(self, rot):
        return Screw3(
            ang=rot.inverse_transform_vector(self.ang),
            lin=rot.inverse_transform_vector(self.lin)
        )

    def inverse_transform_by(self, trans):
        return Screw3(
            ang=trans.inverse_transform_vector(self.ang),
            lin=trans.inverse_transform_vector(self.lin)
        )

    def transform_as_twist_by(self, trans):
        rang = trans.transform_vector(self.ang)
        return Screw3(
            ang = rang,
            lin = trans.transform_vector(self.lin) + numpy.cross(trans.lin, rang)
        )

    def inverse_transform_as_twist_by(self, trans):
        return Screw3(
            ang = trans.inverse_transform_vector(self.ang),
            lin = trans.inverse_transform_vector(self.lin - numpy.cross(trans.lin, self.ang))
        )

    def transform_as_wrench_by(self, trans):
        &quot;&quot;&quot;Transform wrench (moment + force) under SE(3) transform.&quot;&quot;&quot;
        p = trans.lin
        return Screw3(
            ang = trans.transform_vector(self.ang + numpy.cross(p, self.lin)),
            lin = trans.transform_vector(self.lin)
        )

    def inverse_transform_as_wrench_by(self, trans):
        &quot;&quot;&quot;Inverse transform of a wrench under SE(3) transform.&quot;&quot;&quot;
        p = trans.lin
        return Screw3(
            ang = trans.inverse_transform_vector(self.ang - numpy.cross(p, self.lin)),
            lin = trans.inverse_transform_vector(self.lin)
        )

    def as_pose3(self):
        &quot;&quot;&quot;Convert the screw to a Pose3 representation (for small motions).&quot;&quot;&quot;
        rotangle = numpy.linalg.norm(self.ang)
        if rotangle &lt; 1e-8:
            # Pure translation
            return Pose3(
                ang=numpy.array([0.0, 0.0, 0.0, 1.0]),
                lin=self.lin
            )
        axis = self.ang / rotangle
        half_angle = rotangle / 2.0
        q = numpy.array([
            axis[0] * math.sin(half_angle),
            axis[1] * math.sin(half_angle),
            axis[2] * math.sin(half_angle),
            math.cos(half_angle)
        ])
        return Pose3(
            ang=q,
            lin=self.lin
        )

    def __mul__(self, oth):
        return Screw3(self.ang * oth, self.lin * oth)

    def to_vw_array(self) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Return the screw as a 6x1 array in [vx, vy, vz, wx, wy, wz] order.&quot;&quot;&quot;
        return numpy.hstack([self.lin, self.ang])

    def to_wv_array(self) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Return the screw as a 6x1 array in [wx, wy, wz, vx, vy, vz] order.&quot;&quot;&quot;
        return numpy.hstack([self.ang, self.lin])

    def from_vw_array(vec: numpy.ndarray) -&gt; &quot;Screw3&quot;:
        &quot;&quot;&quot;Create a Screw3 from a 6x1 array in [vx, vy, vz, wx, wy, wz] order.&quot;&quot;&quot;
        if vec.shape != (6,):
            raise Exception(&quot;Input vector must be of shape (6,)&quot;)

        return Screw3(
            ang=vec[3:6],
            lin=vec[0:3]
        )
    def from_wv_array(vec: numpy.ndarray) -&gt; &quot;Screw3&quot;:
        &quot;&quot;&quot;Create a Screw3 from a 6x1 array in [wx, wy, wz, vx, vy, vz] order.&quot;&quot;&quot;
        if vec.shape != (6,):
            raise Exception(&quot;Input vector must be of shape (6,)&quot;)

        return Screw3(
            ang=vec[0:3],
            lin=vec[3:6]
        )

    def to_pose(self):
        &quot;&quot;&quot;Convert the screw to a Pose3 representation (for small motions).&quot;&quot;&quot;
        lin = self.lin

        #exponential map for rotation
        theta = numpy.linalg.norm(self.ang)
        if theta &lt; 1e-8:
            # Pure translation
            return Pose3(
                ang=numpy.array([0.0, 0.0, 0.0, 1.0]),
                lin=lin
            )
        axis = self.ang / theta
        half_angle = theta / 2.0
        q = numpy.array([
            axis[0] * math.sin(half_angle),
            axis[1] * math.sin(half_angle),
            axis[2] * math.sin(half_angle),
            math.cos(half_angle)
        ])
        return Pose3(
            ang=q,
            lin=lin
        )

    def from_vector_vw_order(vec: numpy.ndarray) -&gt; &quot;Screw3&quot;:
        &quot;&quot;&quot;Create a Screw3 from a 6x1 array in [vx, vy, vz, wx, wy, wz] order.&quot;&quot;&quot;
        if vec.shape != (6,):
            raise Exception(&quot;Input vector must be of shape (6,)&quot;)

        return Screw3(
            ang=vec[3:6],
            lin=vec[0:3]
        )

    def from_vector_wv_order(vec: numpy.ndarray) -&gt; &quot;Screw3&quot;:
        &quot;&quot;&quot;Create a Screw3 from a 6x1 array in [wx, wy, wz, vx, vy, vz] order.&quot;&quot;&quot;
        if vec.shape != (6,):
            raise Exception(&quot;Input vector must be of shape (6,)&quot;)

        return Screw3(
            ang=vec[0:3],
            lin=vec[3:6]
        )

    def to_vector_vw_order(self) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Return the screw as a 6x1 array in [vx, vy, vz, wx, wy, wz] order.&quot;&quot;&quot;
        return numpy.array([self.lin[0], self.lin[1], self.lin[2],
                            self.ang[0], self.ang[1], self.ang[2]], float)

    def to_vector_wv_order(self) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Return the screw as a 6x1 array in [wx, wy, wz, vx, vy, vz] order.&quot;&quot;&quot;
        return numpy.array([self.ang[0], self.ang[1], self.ang[2],
                            self.lin[0], self.lin[1], self.lin[2]], float)
</code></pre>
</body>
</html>
