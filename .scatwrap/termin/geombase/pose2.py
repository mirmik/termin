<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/geombase/pose2.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import math<br>
import numpy<br>
<br>
<br>
class Pose2:<br>
&#9;&quot;&quot;&quot;A 2D Pose represented by rotation angle and translation vector.&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, ang: float = 0.0, lin: numpy.ndarray = numpy.array([0.0, 0.0])):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;ang: Rotation angle in radians<br>
&#9;&#9;&#9;lin: Translation vector [x, y]<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self.ang = ang<br>
&#9;&#9;self.lin = numpy.asarray(lin)<br>
&#9;&#9;if self.lin.shape != (2,):<br>
&#9;&#9;&#9;raise ValueError(&quot;lin must be a 2D vector&quot;)<br>
&#9;&#9;self._rot_matrix = None  # Lazy computation<br>
&#9;&#9;self._mat = None  # Lazy computation<br>
<br>
&#9;@staticmethod<br>
&#9;def identity():<br>
&#9;&#9;&quot;&quot;&quot;Create an identity pose (no rotation, no translation).&quot;&quot;&quot;<br>
&#9;&#9;return Pose2(ang=0.0, lin=numpy.array([0.0, 0.0]))<br>
<br>
&#9;def rotation_matrix(self):<br>
&#9;&#9;&quot;&quot;&quot;Get the 2x2 rotation matrix corresponding to the pose's orientation.&quot;&quot;&quot;<br>
&#9;&#9;if self._rot_matrix is None:<br>
&#9;&#9;&#9;c = math.cos(self.ang)<br>
&#9;&#9;&#9;s = math.sin(self.ang)<br>
&#9;&#9;&#9;self._rot_matrix = numpy.array([<br>
&#9;&#9;&#9;&#9;[c, -s],<br>
&#9;&#9;&#9;&#9;[s,  c]<br>
&#9;&#9;&#9;])<br>
&#9;&#9;return self._rot_matrix<br>
<br>
&#9;def as_matrix(self):<br>
&#9;&#9;&quot;&quot;&quot;Get the 3x3 transformation matrix corresponding to the pose.&quot;&quot;&quot;<br>
&#9;&#9;if self._mat is None:<br>
&#9;&#9;&#9;R = self.rotation_matrix()<br>
&#9;&#9;&#9;t = self.lin<br>
&#9;&#9;&#9;self._mat = numpy.eye(3)<br>
&#9;&#9;&#9;self._mat[:2, :2] = R<br>
&#9;&#9;&#9;self._mat[:2, 2] = t<br>
&#9;&#9;return self._mat<br>
<br>
&#9;def inverse(self):<br>
&#9;&#9;&quot;&quot;&quot;Compute the inverse of the pose.&quot;&quot;&quot;<br>
&#9;&#9;inv_ang = -self.ang<br>
&#9;&#9;c = math.cos(inv_ang)<br>
&#9;&#9;s = math.sin(inv_ang)<br>
&#9;&#9;# Rotate translation by inverse rotation<br>
&#9;&#9;inv_lin = numpy.array([<br>
&#9;&#9;&#9;c * (-self.lin[0]) - s * (-self.lin[1]),<br>
&#9;&#9;&#9;s * (-self.lin[0]) + c * (-self.lin[1])<br>
&#9;&#9;])<br>
&#9;&#9;return Pose2(inv_ang, inv_lin)<br>
<br>
&#9;def __repr__(self):<br>
&#9;&#9;return f&quot;Pose2(ang={self.ang}, lin={self.lin})&quot;<br>
<br>
&#9;def transform_point(self, point: numpy.ndarray) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Transform a 2D point using the pose.&quot;&quot;&quot;<br>
&#9;&#9;point = numpy.asarray(point)<br>
&#9;&#9;if point.shape != (2,):<br>
&#9;&#9;&#9;raise ValueError(&quot;point must be a 2D vector&quot;)<br>
&#9;&#9;R = self.rotation_matrix()<br>
&#9;&#9;return R @ point + self.lin<br>
<br>
&#9;def transform_vector(self, vector: numpy.ndarray) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Transform a 2D vector using the pose (ignoring translation).&quot;&quot;&quot;<br>
&#9;&#9;vector = numpy.asarray(vector)<br>
&#9;&#9;if vector.shape != (2,):<br>
&#9;&#9;&#9;raise ValueError(&quot;vector must be a 2D vector&quot;)<br>
&#9;&#9;R = self.rotation_matrix()<br>
&#9;&#9;return R @ vector<br>
<br>
&#9;def rotate_vector(self, vector: numpy.ndarray) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Rotate a 2D vector using the pose's rotation.&quot;&quot;&quot;<br>
&#9;&#9;vector = numpy.asarray(vector)<br>
&#9;&#9;if vector.shape != (2,):<br>
&#9;&#9;&#9;raise ValueError(&quot;vector must be a 2D vector&quot;)<br>
&#9;&#9;R = self.rotation_matrix()<br>
&#9;&#9;return R @ vector<br>
<br>
&#9;def inverse_transform_point(self, point: numpy.ndarray) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Transform a 2D point using the inverse of the pose.&quot;&quot;&quot;<br>
&#9;&#9;point = numpy.asarray(point)<br>
&#9;&#9;point = point.reshape(2)<br>
&#9;&#9;R = self.rotation_matrix()<br>
&#9;&#9;return R.T @ (point - self.lin)<br>
<br>
&#9;def inverse_rotate_vector(self, vector: numpy.ndarray) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Rotate a 2D vector using the inverse of the pose's rotation.&quot;&quot;&quot;<br>
&#9;&#9;vector = numpy.asarray(vector)<br>
&#9;&#9;if vector.shape != (2,):<br>
&#9;&#9;&#9;raise ValueError(&quot;vector must be a 2D vector&quot;)<br>
&#9;&#9;R = self.rotation_matrix()<br>
&#9;&#9;return R.T @ vector<br>
<br>
&#9;def inverse_transform_vector(self, vector: numpy.ndarray) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Transform a 2D vector using the inverse of the pose (ignoring translation).&quot;&quot;&quot;<br>
&#9;&#9;vector = numpy.asarray(vector)<br>
&#9;&#9;if vector.shape != (2,):<br>
&#9;&#9;&#9;raise ValueError(&quot;vector must be a 2D vector&quot;)<br>
&#9;&#9;R = self.rotation_matrix()<br>
&#9;&#9;return R.T @ vector<br>
<br>
&#9;def __mul__(self, other):<br>
&#9;&#9;&quot;&quot;&quot;Compose this pose with another pose.&quot;&quot;&quot;<br>
&#9;&#9;if not isinstance(other, Pose2):<br>
&#9;&#9;&#9;raise TypeError(&quot;Can only multiply Pose2 with Pose2&quot;)<br>
&#9;&#9;# Compose rotations: angles add<br>
&#9;&#9;new_ang = self.ang + other.ang<br>
&#9;&#9;# Compose translations: rotate other's translation and add to self's<br>
&#9;&#9;R = self.rotation_matrix()<br>
&#9;&#9;new_lin = self.lin + R @ other.lin<br>
&#9;&#9;return Pose2(ang=new_ang, lin=new_lin)<br>
<br>
&#9;def __matmul__(self, other):<br>
&#9;&#9;&quot;&quot;&quot;Compose this pose with another pose using @ operator.&quot;&quot;&quot;<br>
&#9;&#9;return self * other<br>
<br>
&#9;def compose(self, other: 'Pose2') -&gt; 'Pose2':<br>
&#9;&#9;&quot;&quot;&quot;Compose this pose with another pose.&quot;&quot;&quot;<br>
&#9;&#9;return self * other<br>
<br>
&#9;@staticmethod<br>
&#9;def rotation(angle: float):<br>
&#9;&#9;&quot;&quot;&quot;Create a rotation pose by a given angle.&quot;&quot;&quot;<br>
&#9;&#9;return Pose2(ang=angle, lin=numpy.array([0.0, 0.0]))<br>
<br>
&#9;@staticmethod<br>
&#9;def translation(x: float, y: float):<br>
&#9;&#9;&quot;&quot;&quot;Create a translation pose.&quot;&quot;&quot;<br>
&#9;&#9;return Pose2(ang=0.0, lin=numpy.array([x, y]))<br>
<br>
&#9;@staticmethod<br>
&#9;def move(dx: float, dy: float):<br>
&#9;&#9;&quot;&quot;&quot;Move the pose by given deltas in local coordinates.&quot;&quot;&quot;<br>
&#9;&#9;return Pose2.translation(dx, dy)<br>
<br>
&#9;@staticmethod<br>
&#9;def moveX(distance: float):<br>
&#9;&#9;&quot;&quot;&quot;Move along X axis.&quot;&quot;&quot;<br>
&#9;&#9;return Pose2.move(distance, 0.0)<br>
<br>
&#9;@staticmethod<br>
&#9;def moveY(distance: float):<br>
&#9;&#9;&quot;&quot;&quot;Move along Y axis.&quot;&quot;&quot;<br>
&#9;&#9;return Pose2.move(0.0, distance)<br>
<br>
&#9;@staticmethod<br>
&#9;def right(distance: float):<br>
&#9;&#9;&quot;&quot;&quot;Move right (along X axis).&quot;&quot;&quot;<br>
&#9;&#9;return Pose2.move(distance, 0.0)<br>
<br>
&#9;@staticmethod<br>
&#9;def forward(distance: float):<br>
&#9;&#9;&quot;&quot;&quot;Move forward (along Y axis).&quot;&quot;&quot;<br>
&#9;&#9;return Pose2.move(0.0, distance)<br>
<br>
&#9;@staticmethod<br>
&#9;def lerp(pose1: 'Pose2', pose2: 'Pose2', t: float) -&gt; 'Pose2':<br>
&#9;&#9;&quot;&quot;&quot;Linearly interpolate between two poses.&quot;&quot;&quot;<br>
&#9;&#9;lerped_ang = (1 - t) * pose1.ang + t * pose2.ang<br>
&#9;&#9;lerped_lin = (1 - t) * pose1.lin + t * pose2.lin<br>
&#9;&#9;return Pose2(ang=lerped_ang, lin=lerped_lin)<br>
<br>
&#9;def normalize_angle(self):<br>
&#9;&#9;&quot;&quot;&quot;Normalize the angle to [-π, π].&quot;&quot;&quot;<br>
&#9;&#9;self.ang = math.atan2(math.sin(self.ang), math.cos(self.ang))<br>
&#9;&#9;self._rot_matrix = None<br>
&#9;&#9;self._mat = None<br>
<br>
&#9;@property<br>
&#9;def x(self):<br>
&#9;&#9;&quot;&quot;&quot;Get X coordinate of translation.&quot;&quot;&quot;<br>
&#9;&#9;return self.lin[0]<br>
<br>
&#9;@property<br>
&#9;def y(self):<br>
&#9;&#9;&quot;&quot;&quot;Get Y coordinate of translation.&quot;&quot;&quot;<br>
&#9;&#9;return self.lin[1]<br>
<br>
&#9;@x.setter<br>
&#9;def x(self, value: float):<br>
&#9;&#9;&quot;&quot;&quot;Set X coordinate of translation.&quot;&quot;&quot;<br>
&#9;&#9;self.lin[0] = value<br>
&#9;&#9;self._mat = None<br>
<br>
&#9;@y.setter<br>
&#9;def y(self, value: float):<br>
&#9;&#9;&quot;&quot;&quot;Set Y coordinate of translation.&quot;&quot;&quot;<br>
&#9;&#9;self.lin[1] = value<br>
&#9;&#9;self._mat = None<br>
<!-- END SCAT CODE -->
</body>
</html>
