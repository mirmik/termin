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
&#9;&quot;&quot;&quot;2D cross product: scalar × vector = [vy, -vx] * scalar&quot;&quot;&quot;<br>
&#9;return scalar * numpy.array([vec[1], -vec[0]])<br>
<br>
def cross2d_scalar(vec1, vec2):<br>
&#9;&quot;&quot;&quot;2D cross product returning scalar: vec1 × vec2 = v1x*v2y - v1y*v2x&quot;&quot;&quot;<br>
&#9;return vec1[0]*vec2[1] - vec1[1]*vec2[0]<br>
<br>
def cross2d_xz(vec, scalar):<br>
&#9;&quot;&quot;&quot;2D cross product for twist transformation: vector × scalar = [-sy, sx]&quot;&quot;&quot;<br>
&#9;return numpy.array([-scalar * vec[1], scalar * vec[0]])<br>
<br>
class Screw:<br>
&#9;&quot;&quot;&quot;A class representing a pair of vector and bivector&quot;&quot;&quot;<br>
&#9;def __init__(self, ang, lin):<br>
&#9;&#9;self.ang = ang  # Bivector part<br>
&#9;&#9;self.lin = lin  # Vector part<br>
<br>
&#9;&#9;if not isinstance(self.ang, numpy.ndarray):<br>
&#9;&#9;&#9;raise Exception(&quot;ang must be ndarray&quot;)<br>
<br>
&#9;&#9;if not isinstance(self.lin, numpy.ndarray):<br>
&#9;&#9;&#9;raise Exception(&quot;lin must be ndarray&quot;)<br>
<br>
&#9;def __repr__(self):<br>
&#9;&#9;return f&quot;Screw(ang={self.ang}, lin={self.lin})&quot;<br>
<br>
class Screw2(Screw):<br>
&#9;&quot;&quot;&quot;A 2D Screw specialized for planar motions.&quot;&quot;&quot;<br>
&#9;def __init__(self, ang: numpy.ndarray, lin: numpy.ndarray):<br>
<br>
&#9;&#9;if not isinstance(ang, numpy.ndarray):<br>
&#9;&#9;&#9;ang = numpy.array(ang)<br>
<br>
&#9;&#9;# # check shapes<br>
&#9;&#9;# if ang.shape != (1,) and ang.shape != ():<br>
&#9;&#9;#     raise Exception(&quot;ang must be a scalar or shape (1,) ndarray&quot;)<br>
<br>
&#9;&#9;# if lin.shape != (2,):<br>
&#9;&#9;#     raise Exception(f&quot;lin must be shape (2,) ndarray, got {lin.shape}&quot;)<br>
<br>
&#9;&#9;ang = ang.reshape(1)<br>
&#9;&#9;lin = lin.reshape(2)<br>
<br>
&#9;&#9;super().__init__(ang=ang, lin=lin)<br>
<br>
&#9;def moment(self) -&gt; float:<br>
&#9;&#9;&quot;&quot;&quot;Return the moment (bivector part) of the screw.&quot;&quot;&quot;<br>
&#9;&#9;return self.ang.item() if self.ang.shape == () or self.ang.shape == (1,) else self.ang[0]<br>
<br>
&#9;def vector(self) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Return the vector part of the screw.&quot;&quot;&quot;<br>
&#9;&#9;return self.lin<br>
<br>
&#9;def kinematic_carry(self, arm: &quot;Vector2&quot;) -&gt; &quot;Screw2&quot;:<br>
&#9;&#9;&quot;&quot;&quot;Twist transform. Carry the screw by arm. For pair of angular and linear speeds.&quot;&quot;&quot;<br>
&#9;&#9;return Screw2(<br>
&#9;&#9;&#9;lin=self.lin + cross2d(self.moment(), arm),<br>
&#9;&#9;&#9;ang=self.ang)<br>
<br>
&#9;def force_carry(self, arm: &quot;Vector2&quot;) -&gt; &quot;Screw2&quot;:<br>
&#9;&#9;&quot;&quot;&quot;Wrench transform. Carry the screw by arm. For pair of torques and forces.&quot;&quot;&quot;<br>
&#9;&#9;return Screw2(<br>
&#9;&#9;&#9;ang=self.ang - numpy.array([cross2d_scalar(arm, self.lin)]),<br>
&#9;&#9;&#9;lin=self.lin)<br>
<br>
&#9;def twist_carry(self, arm: &quot;Vector2&quot;) -&gt; &quot;Screw2&quot;:<br>
&#9;&#9;&quot;&quot;&quot;Alias for kinematic_carry.&quot;&quot;&quot;<br>
&#9;&#9;return self.kinematic_carry(arm)<br>
<br>
&#9;def wrench_carry(self, arm: &quot;Vector2&quot;) -&gt; &quot;Screw2&quot;:<br>
&#9;&#9;&quot;&quot;&quot;Alias for force_carry.&quot;&quot;&quot;<br>
&#9;&#9;return self.force_carry(arm)<br>
<br>
&#9;def transform_by(self, trans):<br>
&#9;&#9;return Screw2(ang=self.ang, lin=trans.transform_vector(self.lin))<br>
<br>
&#9;def rotated_by(self, trans):<br>
&#9;&#9;return Screw2(ang=self.ang, lin=trans.rotate_vector(self.lin))<br>
<br>
&#9;def inverse_transform_by(self, trans):<br>
&#9;&#9;return Screw2(ang=self.ang, lin=trans.inverse_transform_vector(self.lin))<br>
<br>
&#9;def transform_as_twist_by(self, trans):<br>
&#9;&#9;rlin = trans.transform_vector(self.lin)<br>
&#9;&#9;return Screw2(<br>
&#9;&#9;&#9;lin=rlin + cross2d_xz(trans.lin, self.moment()),<br>
&#9;&#9;&#9;ang=self.ang,<br>
&#9;&#9;)<br>
<br>
&#9;def inverse_transform_as_twist_by(self, trans):<br>
&#9;&#9;return Screw2(<br>
&#9;&#9;&#9;ang=self.ang,<br>
&#9;&#9;&#9;lin=trans.inverse_transform_vector(self.lin - cross2d_xz(trans.lin, self.moment()))<br>
&#9;&#9;)<br>
<br>
&#9;def transform_as_wrench_by(self, trans):<br>
&#9;&#9;&quot;&quot;&quot;Transform wrench (moment + force) under SE(2) transform.&quot;&quot;&quot;<br>
&#9;&#9;return Screw2(<br>
&#9;&#9;&#9;ang=self.ang + numpy.array([cross2d_scalar(trans.lin, self.lin)]),<br>
&#9;&#9;&#9;lin=trans.transform_vector(self.lin)<br>
&#9;&#9;)<br>
<br>
&#9;def inverse_transform_as_wrench_by(self, trans):<br>
&#9;&#9;&quot;&quot;&quot;Inverse transform of a wrench under SE(2) transform.&quot;&quot;&quot;<br>
&#9;&#9;return Screw2(<br>
&#9;&#9;&#9;ang=self.ang - numpy.array([cross2d_scalar(trans.lin, self.lin)]),<br>
&#9;&#9;&#9;lin=trans.inverse_transform_vector(self.lin)<br>
&#9;&#9;)<br>
<br>
&#9;def __mul__(self, oth):<br>
&#9;&#9;return Screw2(self.ang * oth, self.lin * oth)<br>
<br>
&#9;def __add__(self, oth):<br>
&#9;&#9;return Screw2(self.ang + oth.ang, self.lin + oth.lin)<br>
<br>
&#9;def __sub__(self, oth):<br>
&#9;&#9;return Screw2(self.ang - oth.ang, self.lin - oth.lin)<br>
<br>
&#9;def to_vector_vw_order(self) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Return the screw as a 3x1 array in [vx, vy, w] order.&quot;&quot;&quot;<br>
&#9;&#9;return numpy.array([self.lin[0], self.lin[1], self.moment()], float)<br>
<br>
&#9;def to_vector_wv_order(self) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Return the screw as a 3x1 array in [w, vx, vy] order.&quot;&quot;&quot;<br>
&#9;&#9;return numpy.array([self.moment(), self.lin[0], self.lin[1]], float)<br>
<br>
&#9;def from_vector_vw_order(vec: numpy.ndarray) -&gt; &quot;Screw2&quot;:<br>
&#9;&#9;&quot;&quot;&quot;Create a Screw2 from a 3x1 array in [vx, vy, w] order.&quot;&quot;&quot;<br>
&#9;&#9;if vec.shape != (3,):<br>
&#9;&#9;&#9;raise Exception(&quot;Input vector must be of shape (3,)&quot;)<br>
<br>
&#9;&#9;return Screw2(<br>
&#9;&#9;&#9;ang=numpy.array([vec[2]]),<br>
&#9;&#9;&#9;lin=numpy.array([vec[0], vec[1]])<br>
&#9;&#9;)<br>
<br>
&#9;def from_vector_wv_order(vec: numpy.ndarray) -&gt; &quot;Screw2&quot;:<br>
&#9;&#9;&quot;&quot;&quot;Create a Screw2 from a 3x1 array in [w, vx, vy] order.&quot;&quot;&quot;<br>
&#9;&#9;if vec.shape != (3,):<br>
&#9;&#9;&#9;raise Exception(&quot;Input vector must be of shape (3,)&quot;)<br>
<br>
&#9;&#9;return Screw2(<br>
&#9;&#9;&#9;ang=numpy.array([vec[0]]),<br>
&#9;&#9;&#9;lin=numpy.array([vec[1], vec[2]])<br>
&#9;&#9;)<br>
<br>
&#9;def to_pose(self):<br>
&#9;&#9;&quot;&quot;&quot;Convert the screw to a Pose2 representation (for small motions).&quot;&quot;&quot;<br>
&#9;&#9;return Pose2(<br>
&#9;&#9;&#9;ang=self.moment(),<br>
&#9;&#9;&#9;lin=self.lin<br>
&#9;&#9;)<br>
<br>
class Screw3(Screw):<br>
&#9;&quot;&quot;&quot;A 3D Screw specialized for spatial motions.&quot;&quot;&quot;<br>
&#9;def __init__(self, ang: numpy.ndarray = numpy.array([0,0,0]), lin: numpy.ndarray = numpy.array([0,0,0])):<br>
&#9;&#9;super().__init__(ang=ang, lin=lin)<br>
<br>
&#9;def moment(self) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Return the moment (bivector part) of the screw.&quot;&quot;&quot;<br>
&#9;&#9;return self.ang<br>
<br>
&#9;def vector(self) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Return the vector part of the screw.&quot;&quot;&quot;<br>
&#9;&#9;return self.lin<br>
<br>
&#9;def kinematic_carry(self, arm: &quot;Vector3&quot;) -&gt; &quot;Screw3&quot;:<br>
&#9;&#9;&quot;&quot;&quot;Twist transform. Carry the screw by arm. For pair of angular and linear speeds.&quot;&quot;&quot;<br>
&#9;&#9;return Screw3(<br>
&#9;&#9;&#9;lin=self.lin + numpy.cross(self.ang, arm),<br>
&#9;&#9;&#9;ang=self.ang)<br>
<br>
&#9;def force_carry(self, arm: &quot;Vector3&quot;) -&gt; &quot;Screw3&quot;:<br>
&#9;&#9;&quot;&quot;&quot;Wrench transform. Carry the screw by arm. For pair of torques and forces.&quot;&quot;&quot;<br>
&#9;&#9;return Screw3(<br>
&#9;&#9;&#9;ang=self.ang - numpy.cross(arm, self.lin),<br>
&#9;&#9;&#9;lin=self.lin)<br>
<br>
&#9;def twist_carry(self, arm: &quot;Vector3&quot;) -&gt; &quot;Screw3&quot;:<br>
&#9;&#9;&quot;&quot;&quot;Alias for kinematic_carry.&quot;&quot;&quot;<br>
&#9;&#9;return self.kinematic_carry(arm)<br>
<br>
&#9;def wrench_carry(self, arm: &quot;Vector3&quot;) -&gt; &quot;Screw3&quot;:<br>
&#9;&#9;&quot;&quot;&quot;Alias for force_carry.&quot;&quot;&quot;<br>
&#9;&#9;return self.force_carry(arm)<br>
<br>
&#9;def transform_by(self, trans):<br>
&#9;&#9;return Screw3(<br>
&#9;&#9;&#9;ang=trans.transform_vector(self.ang),<br>
&#9;&#9;&#9;lin=trans.transform_vector(self.lin)<br>
&#9;&#9;)<br>
<br>
&#9;def rotate_by(self, rot):<br>
&#9;&#9;return Screw3(<br>
&#9;&#9;&#9;ang=rot.transform_vector(self.ang),<br>
&#9;&#9;&#9;lin=rot.transform_vector(self.lin)<br>
&#9;&#9;)<br>
<br>
&#9;def inverse_rotate_by(self, rot):<br>
&#9;&#9;return Screw3(<br>
&#9;&#9;&#9;ang=rot.inverse_transform_vector(self.ang),<br>
&#9;&#9;&#9;lin=rot.inverse_transform_vector(self.lin)<br>
&#9;&#9;)<br>
<br>
&#9;def inverse_transform_by(self, trans):<br>
&#9;&#9;return Screw3(<br>
&#9;&#9;&#9;ang=trans.inverse_transform_vector(self.ang),<br>
&#9;&#9;&#9;lin=trans.inverse_transform_vector(self.lin)<br>
&#9;&#9;)<br>
<br>
&#9;def transform_as_twist_by(self, trans):<br>
&#9;&#9;rang = trans.transform_vector(self.ang)<br>
&#9;&#9;return Screw3(<br>
&#9;&#9;&#9;ang = rang,<br>
&#9;&#9;&#9;lin = trans.transform_vector(self.lin) + numpy.cross(trans.lin, rang)<br>
&#9;&#9;)<br>
<br>
&#9;def inverse_transform_as_twist_by(self, trans):<br>
&#9;&#9;return Screw3(<br>
&#9;&#9;&#9;ang = trans.inverse_transform_vector(self.ang),<br>
&#9;&#9;&#9;lin = trans.inverse_transform_vector(self.lin - numpy.cross(trans.lin, self.ang))<br>
&#9;&#9;)<br>
<br>
&#9;def transform_as_wrench_by(self, trans):<br>
&#9;&#9;&quot;&quot;&quot;Transform wrench (moment + force) under SE(3) transform.&quot;&quot;&quot;<br>
&#9;&#9;p = trans.lin<br>
&#9;&#9;return Screw3(<br>
&#9;&#9;&#9;ang = trans.transform_vector(self.ang + numpy.cross(p, self.lin)),<br>
&#9;&#9;&#9;lin = trans.transform_vector(self.lin)<br>
&#9;&#9;)<br>
<br>
&#9;def inverse_transform_as_wrench_by(self, trans):<br>
&#9;&#9;&quot;&quot;&quot;Inverse transform of a wrench under SE(3) transform.&quot;&quot;&quot;<br>
&#9;&#9;p = trans.lin<br>
&#9;&#9;return Screw3(<br>
&#9;&#9;&#9;ang = trans.inverse_transform_vector(self.ang - numpy.cross(p, self.lin)),<br>
&#9;&#9;&#9;lin = trans.inverse_transform_vector(self.lin)<br>
&#9;&#9;)<br>
<br>
&#9;def as_pose3(self):<br>
&#9;&#9;&quot;&quot;&quot;Convert the screw to a Pose3 representation (for small motions).&quot;&quot;&quot;<br>
&#9;&#9;rotangle = numpy.linalg.norm(self.ang)<br>
&#9;&#9;if rotangle &lt; 1e-8:<br>
&#9;&#9;&#9;# Pure translation<br>
&#9;&#9;&#9;return Pose3(<br>
&#9;&#9;&#9;&#9;ang=numpy.array([0.0, 0.0, 0.0, 1.0]),<br>
&#9;&#9;&#9;&#9;lin=self.lin<br>
&#9;&#9;&#9;)<br>
&#9;&#9;axis = self.ang / rotangle<br>
&#9;&#9;half_angle = rotangle / 2.0<br>
&#9;&#9;q = numpy.array([<br>
&#9;&#9;&#9;axis[0] * math.sin(half_angle),<br>
&#9;&#9;&#9;axis[1] * math.sin(half_angle),<br>
&#9;&#9;&#9;axis[2] * math.sin(half_angle),<br>
&#9;&#9;&#9;math.cos(half_angle)<br>
&#9;&#9;])<br>
&#9;&#9;return Pose3(<br>
&#9;&#9;&#9;ang=q,<br>
&#9;&#9;&#9;lin=self.lin<br>
&#9;&#9;)<br>
<br>
&#9;def __mul__(self, oth):<br>
&#9;&#9;return Screw3(self.ang * oth, self.lin * oth)<br>
<br>
&#9;def to_vw_array(self) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Return the screw as a 6x1 array in [vx, vy, vz, wx, wy, wz] order.&quot;&quot;&quot;<br>
&#9;&#9;return numpy.hstack([self.lin, self.ang])<br>
<br>
&#9;def to_wv_array(self) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Return the screw as a 6x1 array in [wx, wy, wz, vx, vy, vz] order.&quot;&quot;&quot;<br>
&#9;&#9;return numpy.hstack([self.ang, self.lin])<br>
<br>
&#9;def from_vw_array(vec: numpy.ndarray) -&gt; &quot;Screw3&quot;:<br>
&#9;&#9;&quot;&quot;&quot;Create a Screw3 from a 6x1 array in [vx, vy, vz, wx, wy, wz] order.&quot;&quot;&quot;<br>
&#9;&#9;if vec.shape != (6,):<br>
&#9;&#9;&#9;raise Exception(&quot;Input vector must be of shape (6,)&quot;)<br>
<br>
&#9;&#9;return Screw3(<br>
&#9;&#9;&#9;ang=vec[3:6],<br>
&#9;&#9;&#9;lin=vec[0:3]<br>
&#9;&#9;)<br>
&#9;def from_wv_array(vec: numpy.ndarray) -&gt; &quot;Screw3&quot;:<br>
&#9;&#9;&quot;&quot;&quot;Create a Screw3 from a 6x1 array in [wx, wy, wz, vx, vy, vz] order.&quot;&quot;&quot;<br>
&#9;&#9;if vec.shape != (6,):<br>
&#9;&#9;&#9;raise Exception(&quot;Input vector must be of shape (6,)&quot;)<br>
<br>
&#9;&#9;return Screw3(<br>
&#9;&#9;&#9;ang=vec[0:3],<br>
&#9;&#9;&#9;lin=vec[3:6]<br>
&#9;&#9;)<br>
<br>
&#9;def to_pose(self):<br>
&#9;&#9;&quot;&quot;&quot;Convert the screw to a Pose3 representation (for small motions).&quot;&quot;&quot;<br>
&#9;&#9;lin = self.lin<br>
<br>
&#9;&#9;#exponential map for rotation<br>
&#9;&#9;theta = numpy.linalg.norm(self.ang)<br>
&#9;&#9;if theta &lt; 1e-8:<br>
&#9;&#9;&#9;# Pure translation<br>
&#9;&#9;&#9;return Pose3(<br>
&#9;&#9;&#9;&#9;ang=numpy.array([0.0, 0.0, 0.0, 1.0]),<br>
&#9;&#9;&#9;&#9;lin=lin<br>
&#9;&#9;&#9;)<br>
&#9;&#9;axis = self.ang / theta<br>
&#9;&#9;half_angle = theta / 2.0<br>
&#9;&#9;q = numpy.array([<br>
&#9;&#9;&#9;axis[0] * math.sin(half_angle),<br>
&#9;&#9;&#9;axis[1] * math.sin(half_angle),<br>
&#9;&#9;&#9;axis[2] * math.sin(half_angle),<br>
&#9;&#9;&#9;math.cos(half_angle)<br>
&#9;&#9;])<br>
&#9;&#9;return Pose3(<br>
&#9;&#9;&#9;ang=q,<br>
&#9;&#9;&#9;lin=lin<br>
&#9;&#9;)<br>
<br>
&#9;def from_vector_vw_order(vec: numpy.ndarray) -&gt; &quot;Screw3&quot;:<br>
&#9;&#9;&quot;&quot;&quot;Create a Screw3 from a 6x1 array in [vx, vy, vz, wx, wy, wz] order.&quot;&quot;&quot;<br>
&#9;&#9;if vec.shape != (6,):<br>
&#9;&#9;&#9;raise Exception(&quot;Input vector must be of shape (6,)&quot;)<br>
<br>
&#9;&#9;return Screw3(<br>
&#9;&#9;&#9;ang=vec[3:6],<br>
&#9;&#9;&#9;lin=vec[0:3]<br>
&#9;&#9;)<br>
<br>
&#9;def from_vector_wv_order(vec: numpy.ndarray) -&gt; &quot;Screw3&quot;:<br>
&#9;&#9;&quot;&quot;&quot;Create a Screw3 from a 6x1 array in [wx, wy, wz, vx, vy, vz] order.&quot;&quot;&quot;<br>
&#9;&#9;if vec.shape != (6,):<br>
&#9;&#9;&#9;raise Exception(&quot;Input vector must be of shape (6,)&quot;)<br>
<br>
&#9;&#9;return Screw3(<br>
&#9;&#9;&#9;ang=vec[0:3],<br>
&#9;&#9;&#9;lin=vec[3:6]<br>
&#9;&#9;)<br>
<br>
&#9;def to_vector_vw_order(self) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Return the screw as a 6x1 array in [vx, vy, vz, wx, wy, wz] order.&quot;&quot;&quot;<br>
&#9;&#9;return numpy.array([self.lin[0], self.lin[1], self.lin[2],<br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;self.ang[0], self.ang[1], self.ang[2]], float)<br>
<br>
&#9;def to_vector_wv_order(self) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Return the screw as a 6x1 array in [wx, wy, wz, vx, vy, vz] order.&quot;&quot;&quot;<br>
&#9;&#9;return numpy.array([self.ang[0], self.ang[1], self.ang[2],<br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;self.lin[0], self.lin[1], self.lin[2]], float)<br>
<!-- END SCAT CODE -->
</body>
</html>
