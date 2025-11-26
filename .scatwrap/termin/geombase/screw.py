<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/geombase/screw.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import numpy<br>
import math<br>
from .pose3 import Pose3<br>
<br>
def cross2d(scalar, vec):<br>
    &quot;&quot;&quot;2D cross product: scalar × vector = [vy, -vx] * scalar&quot;&quot;&quot;<br>
    return scalar * numpy.array([vec[1], -vec[0]])<br>
<br>
def cross2d_scalar(vec1, vec2):<br>
    &quot;&quot;&quot;2D cross product returning scalar: vec1 × vec2 = v1x*v2y - v1y*v2x&quot;&quot;&quot;<br>
    return vec1[0]*vec2[1] - vec1[1]*vec2[0]<br>
<br>
def cross2d_xz(vec, scalar):<br>
    &quot;&quot;&quot;2D cross product for twist transformation: vector × scalar = [-sy, sx]&quot;&quot;&quot;<br>
    return numpy.array([-scalar * vec[1], scalar * vec[0]])<br>
<br>
class Screw:<br>
    &quot;&quot;&quot;A class representing a pair of vector and bivector&quot;&quot;&quot;<br>
    def __init__(self, ang, lin):<br>
        self.ang = ang  # Bivector part<br>
        self.lin = lin  # Vector part<br>
<br>
        if not isinstance(self.ang, numpy.ndarray):<br>
            raise Exception(&quot;ang must be ndarray&quot;)<br>
<br>
        if not isinstance(self.lin, numpy.ndarray):<br>
            raise Exception(&quot;lin must be ndarray&quot;)<br>
<br>
    def __repr__(self):<br>
        return f&quot;Screw(ang={self.ang}, lin={self.lin})&quot;<br>
<br>
class Screw2(Screw):<br>
    &quot;&quot;&quot;A 2D Screw specialized for planar motions.&quot;&quot;&quot;<br>
    def __init__(self, ang: numpy.ndarray, lin: numpy.ndarray):<br>
<br>
        if not isinstance(ang, numpy.ndarray):<br>
            ang = numpy.array(ang)<br>
<br>
        # # check shapes<br>
        # if ang.shape != (1,) and ang.shape != ():<br>
        #     raise Exception(&quot;ang must be a scalar or shape (1,) ndarray&quot;)<br>
<br>
        # if lin.shape != (2,):<br>
        #     raise Exception(f&quot;lin must be shape (2,) ndarray, got {lin.shape}&quot;)<br>
<br>
        ang = ang.reshape(1)<br>
        lin = lin.reshape(2)<br>
<br>
        super().__init__(ang=ang, lin=lin)<br>
<br>
    def moment(self) -&gt; float:<br>
        &quot;&quot;&quot;Return the moment (bivector part) of the screw.&quot;&quot;&quot;<br>
        return self.ang.item() if self.ang.shape == () or self.ang.shape == (1,) else self.ang[0]<br>
<br>
    def vector(self) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Return the vector part of the screw.&quot;&quot;&quot;<br>
        return self.lin<br>
<br>
    def kinematic_carry(self, arm: &quot;Vector2&quot;) -&gt; &quot;Screw2&quot;:<br>
        &quot;&quot;&quot;Twist transform. Carry the screw by arm. For pair of angular and linear speeds.&quot;&quot;&quot;<br>
        return Screw2(<br>
            lin=self.lin + cross2d(self.moment(), arm),<br>
            ang=self.ang)<br>
<br>
    def force_carry(self, arm: &quot;Vector2&quot;) -&gt; &quot;Screw2&quot;:<br>
        &quot;&quot;&quot;Wrench transform. Carry the screw by arm. For pair of torques and forces.&quot;&quot;&quot;<br>
        return Screw2(<br>
            ang=self.ang - numpy.array([cross2d_scalar(arm, self.lin)]),<br>
            lin=self.lin)<br>
<br>
    def twist_carry(self, arm: &quot;Vector2&quot;) -&gt; &quot;Screw2&quot;:<br>
        &quot;&quot;&quot;Alias for kinematic_carry.&quot;&quot;&quot;<br>
        return self.kinematic_carry(arm)<br>
<br>
    def wrench_carry(self, arm: &quot;Vector2&quot;) -&gt; &quot;Screw2&quot;:<br>
        &quot;&quot;&quot;Alias for force_carry.&quot;&quot;&quot;<br>
        return self.force_carry(arm)<br>
<br>
    def transform_by(self, trans):<br>
        return Screw2(ang=self.ang, lin=trans.transform_vector(self.lin))<br>
<br>
    def rotated_by(self, trans):<br>
        return Screw2(ang=self.ang, lin=trans.rotate_vector(self.lin))<br>
<br>
    def inverse_transform_by(self, trans):<br>
        return Screw2(ang=self.ang, lin=trans.inverse_transform_vector(self.lin))<br>
<br>
    def transform_as_twist_by(self, trans):<br>
        rlin = trans.transform_vector(self.lin)<br>
        return Screw2(<br>
            lin=rlin + cross2d_xz(trans.lin, self.moment()),<br>
            ang=self.ang,<br>
        )<br>
<br>
    def inverse_transform_as_twist_by(self, trans):<br>
        return Screw2(<br>
            ang=self.ang,<br>
            lin=trans.inverse_transform_vector(self.lin - cross2d_xz(trans.lin, self.moment()))<br>
        )<br>
<br>
    def transform_as_wrench_by(self, trans):<br>
        &quot;&quot;&quot;Transform wrench (moment + force) under SE(2) transform.&quot;&quot;&quot;<br>
        return Screw2(<br>
            ang=self.ang + numpy.array([cross2d_scalar(trans.lin, self.lin)]),<br>
            lin=trans.transform_vector(self.lin)<br>
        )<br>
<br>
    def inverse_transform_as_wrench_by(self, trans):<br>
        &quot;&quot;&quot;Inverse transform of a wrench under SE(2) transform.&quot;&quot;&quot;<br>
        return Screw2(<br>
            ang=self.ang - numpy.array([cross2d_scalar(trans.lin, self.lin)]),<br>
            lin=trans.inverse_transform_vector(self.lin)<br>
        )<br>
<br>
    def __mul__(self, oth):<br>
        return Screw2(self.ang * oth, self.lin * oth)<br>
<br>
    def __add__(self, oth):<br>
        return Screw2(self.ang + oth.ang, self.lin + oth.lin)<br>
<br>
    def __sub__(self, oth):<br>
        return Screw2(self.ang - oth.ang, self.lin - oth.lin)<br>
<br>
    def to_vector_vw_order(self) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Return the screw as a 3x1 array in [vx, vy, w] order.&quot;&quot;&quot;<br>
        return numpy.array([self.lin[0], self.lin[1], self.moment()], float)<br>
<br>
    def to_vector_wv_order(self) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Return the screw as a 3x1 array in [w, vx, vy] order.&quot;&quot;&quot;<br>
        return numpy.array([self.moment(), self.lin[0], self.lin[1]], float)<br>
<br>
    def from_vector_vw_order(vec: numpy.ndarray) -&gt; &quot;Screw2&quot;:<br>
        &quot;&quot;&quot;Create a Screw2 from a 3x1 array in [vx, vy, w] order.&quot;&quot;&quot;<br>
        if vec.shape != (3,):<br>
            raise Exception(&quot;Input vector must be of shape (3,)&quot;)<br>
<br>
        return Screw2(<br>
            ang=numpy.array([vec[2]]),<br>
            lin=numpy.array([vec[0], vec[1]])<br>
        )<br>
<br>
    def from_vector_wv_order(vec: numpy.ndarray) -&gt; &quot;Screw2&quot;:<br>
        &quot;&quot;&quot;Create a Screw2 from a 3x1 array in [w, vx, vy] order.&quot;&quot;&quot;<br>
        if vec.shape != (3,):<br>
            raise Exception(&quot;Input vector must be of shape (3,)&quot;)<br>
<br>
        return Screw2(<br>
            ang=numpy.array([vec[0]]),<br>
            lin=numpy.array([vec[1], vec[2]])<br>
        )<br>
<br>
    def to_pose(self):<br>
        &quot;&quot;&quot;Convert the screw to a Pose2 representation (for small motions).&quot;&quot;&quot;<br>
        return Pose2(<br>
            ang=self.moment(),<br>
            lin=self.lin<br>
        )<br>
<br>
class Screw3(Screw):<br>
    &quot;&quot;&quot;A 3D Screw specialized for spatial motions.&quot;&quot;&quot;<br>
    def __init__(self, ang: numpy.ndarray = numpy.array([0,0,0]), lin: numpy.ndarray = numpy.array([0,0,0])):<br>
        super().__init__(ang=ang, lin=lin)<br>
<br>
    def moment(self) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Return the moment (bivector part) of the screw.&quot;&quot;&quot;<br>
        return self.ang<br>
<br>
    def vector(self) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Return the vector part of the screw.&quot;&quot;&quot;<br>
        return self.lin<br>
<br>
    def kinematic_carry(self, arm: &quot;Vector3&quot;) -&gt; &quot;Screw3&quot;:<br>
        &quot;&quot;&quot;Twist transform. Carry the screw by arm. For pair of angular and linear speeds.&quot;&quot;&quot;<br>
        return Screw3(<br>
            lin=self.lin + numpy.cross(self.ang, arm),<br>
            ang=self.ang)<br>
<br>
    def force_carry(self, arm: &quot;Vector3&quot;) -&gt; &quot;Screw3&quot;:<br>
        &quot;&quot;&quot;Wrench transform. Carry the screw by arm. For pair of torques and forces.&quot;&quot;&quot;<br>
        return Screw3(<br>
            ang=self.ang - numpy.cross(arm, self.lin),<br>
            lin=self.lin)<br>
<br>
    def twist_carry(self, arm: &quot;Vector3&quot;) -&gt; &quot;Screw3&quot;:<br>
        &quot;&quot;&quot;Alias for kinematic_carry.&quot;&quot;&quot;<br>
        return self.kinematic_carry(arm)<br>
<br>
    def wrench_carry(self, arm: &quot;Vector3&quot;) -&gt; &quot;Screw3&quot;:<br>
        &quot;&quot;&quot;Alias for force_carry.&quot;&quot;&quot;<br>
        return self.force_carry(arm)<br>
<br>
    def transform_by(self, trans):<br>
        return Screw3(<br>
            ang=trans.transform_vector(self.ang),<br>
            lin=trans.transform_vector(self.lin)<br>
        )<br>
<br>
    def rotate_by(self, rot):<br>
        return Screw3(<br>
            ang=rot.transform_vector(self.ang),<br>
            lin=rot.transform_vector(self.lin)<br>
        )<br>
<br>
    def inverse_rotate_by(self, rot):<br>
        return Screw3(<br>
            ang=rot.inverse_transform_vector(self.ang),<br>
            lin=rot.inverse_transform_vector(self.lin)<br>
        )<br>
<br>
    def inverse_transform_by(self, trans):<br>
        return Screw3(<br>
            ang=trans.inverse_transform_vector(self.ang),<br>
            lin=trans.inverse_transform_vector(self.lin)<br>
        )<br>
<br>
    def transform_as_twist_by(self, trans):<br>
        rang = trans.transform_vector(self.ang)<br>
        return Screw3(<br>
            ang = rang,<br>
            lin = trans.transform_vector(self.lin) + numpy.cross(trans.lin, rang)<br>
        )<br>
<br>
    def inverse_transform_as_twist_by(self, trans):<br>
        return Screw3(<br>
            ang = trans.inverse_transform_vector(self.ang),<br>
            lin = trans.inverse_transform_vector(self.lin - numpy.cross(trans.lin, self.ang))<br>
        )<br>
<br>
    def transform_as_wrench_by(self, trans):<br>
        &quot;&quot;&quot;Transform wrench (moment + force) under SE(3) transform.&quot;&quot;&quot;<br>
        p = trans.lin<br>
        return Screw3(<br>
            ang = trans.transform_vector(self.ang + numpy.cross(p, self.lin)),<br>
            lin = trans.transform_vector(self.lin)<br>
        )<br>
<br>
    def inverse_transform_as_wrench_by(self, trans):<br>
        &quot;&quot;&quot;Inverse transform of a wrench under SE(3) transform.&quot;&quot;&quot;<br>
        p = trans.lin<br>
        return Screw3(<br>
            ang = trans.inverse_transform_vector(self.ang - numpy.cross(p, self.lin)),<br>
            lin = trans.inverse_transform_vector(self.lin)<br>
        )<br>
<br>
    def as_pose3(self):<br>
        &quot;&quot;&quot;Convert the screw to a Pose3 representation (for small motions).&quot;&quot;&quot;<br>
        rotangle = numpy.linalg.norm(self.ang)<br>
        if rotangle &lt; 1e-8:<br>
            # Pure translation<br>
            return Pose3(<br>
                ang=numpy.array([0.0, 0.0, 0.0, 1.0]),<br>
                lin=self.lin<br>
            )<br>
        axis = self.ang / rotangle<br>
        half_angle = rotangle / 2.0<br>
        q = numpy.array([<br>
            axis[0] * math.sin(half_angle),<br>
            axis[1] * math.sin(half_angle),<br>
            axis[2] * math.sin(half_angle),<br>
            math.cos(half_angle)<br>
        ])<br>
        return Pose3(<br>
            ang=q,<br>
            lin=self.lin<br>
        )<br>
<br>
    def __mul__(self, oth):<br>
        return Screw3(self.ang * oth, self.lin * oth)<br>
<br>
    def to_vw_array(self) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Return the screw as a 6x1 array in [vx, vy, vz, wx, wy, wz] order.&quot;&quot;&quot;<br>
        return numpy.hstack([self.lin, self.ang])<br>
<br>
    def to_wv_array(self) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Return the screw as a 6x1 array in [wx, wy, wz, vx, vy, vz] order.&quot;&quot;&quot;<br>
        return numpy.hstack([self.ang, self.lin])<br>
<br>
    def from_vw_array(vec: numpy.ndarray) -&gt; &quot;Screw3&quot;:<br>
        &quot;&quot;&quot;Create a Screw3 from a 6x1 array in [vx, vy, vz, wx, wy, wz] order.&quot;&quot;&quot;<br>
        if vec.shape != (6,):<br>
            raise Exception(&quot;Input vector must be of shape (6,)&quot;)<br>
<br>
        return Screw3(<br>
            ang=vec[3:6],<br>
            lin=vec[0:3]<br>
        )<br>
    def from_wv_array(vec: numpy.ndarray) -&gt; &quot;Screw3&quot;:<br>
        &quot;&quot;&quot;Create a Screw3 from a 6x1 array in [wx, wy, wz, vx, vy, vz] order.&quot;&quot;&quot;<br>
        if vec.shape != (6,):<br>
            raise Exception(&quot;Input vector must be of shape (6,)&quot;)<br>
<br>
        return Screw3(<br>
            ang=vec[0:3],<br>
            lin=vec[3:6]<br>
        )<br>
<br>
    def to_pose(self):<br>
        &quot;&quot;&quot;Convert the screw to a Pose3 representation (for small motions).&quot;&quot;&quot;<br>
        lin = self.lin<br>
<br>
        #exponential map for rotation<br>
        theta = numpy.linalg.norm(self.ang)<br>
        if theta &lt; 1e-8:<br>
            # Pure translation<br>
            return Pose3(<br>
                ang=numpy.array([0.0, 0.0, 0.0, 1.0]),<br>
                lin=lin<br>
            )<br>
        axis = self.ang / theta<br>
        half_angle = theta / 2.0<br>
        q = numpy.array([<br>
            axis[0] * math.sin(half_angle),<br>
            axis[1] * math.sin(half_angle),<br>
            axis[2] * math.sin(half_angle),<br>
            math.cos(half_angle)<br>
        ])<br>
        return Pose3(<br>
            ang=q,<br>
            lin=lin<br>
        )<br>
<br>
    def from_vector_vw_order(vec: numpy.ndarray) -&gt; &quot;Screw3&quot;:<br>
        &quot;&quot;&quot;Create a Screw3 from a 6x1 array in [vx, vy, vz, wx, wy, wz] order.&quot;&quot;&quot;<br>
        if vec.shape != (6,):<br>
            raise Exception(&quot;Input vector must be of shape (6,)&quot;)<br>
<br>
        return Screw3(<br>
            ang=vec[3:6],<br>
            lin=vec[0:3]<br>
        )<br>
<br>
    def from_vector_wv_order(vec: numpy.ndarray) -&gt; &quot;Screw3&quot;:<br>
        &quot;&quot;&quot;Create a Screw3 from a 6x1 array in [wx, wy, wz, vx, vy, vz] order.&quot;&quot;&quot;<br>
        if vec.shape != (6,):<br>
            raise Exception(&quot;Input vector must be of shape (6,)&quot;)<br>
<br>
        return Screw3(<br>
            ang=vec[0:3],<br>
            lin=vec[3:6]<br>
        )<br>
<br>
    def to_vector_vw_order(self) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Return the screw as a 6x1 array in [vx, vy, vz, wx, wy, wz] order.&quot;&quot;&quot;<br>
        return numpy.array([self.lin[0], self.lin[1], self.lin[2],<br>
                            self.ang[0], self.ang[1], self.ang[2]], float)<br>
<br>
    def to_vector_wv_order(self) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Return the screw as a 6x1 array in [wx, wy, wz, vx, vy, vz] order.&quot;&quot;&quot;<br>
        return numpy.array([self.ang[0], self.ang[1], self.ang[2],<br>
                            self.lin[0], self.lin[1], self.lin[2]], float)<br>
<!-- END SCAT CODE -->
</body>
</html>
