<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/geombase/pose3.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import math<br>
import numpy<br>
import numpy as np<br>
from termin.util import qmul, qrot, qslerp, qinv<br>
<br>
class Pose3:<br>
&#9;&quot;&quot;&quot;A 3D Pose represented by rotation quaternion and translation vector.&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, ang: numpy.ndarray = None, lin: numpy.ndarray = None):<br>
&#9;&#9;if ang is None:<br>
&#9;&#9;&#9;ang = numpy.array([0.0, 0.0, 0.0, 1.0])<br>
&#9;&#9;if lin is None:<br>
&#9;&#9;&#9;lin = numpy.array([0.0, 0.0, 0.0])<br>
&#9;&#9;self._ang = ang<br>
&#9;&#9;self._lin = lin<br>
&#9;&#9;self._rot_matrix = None  # Lazy computation<br>
&#9;&#9;self._mat = None  # Lazy computation<br>
&#9;&#9;self._mat34 = None  # Lazy computation<br>
<br>
&#9;@property<br>
&#9;def ang(self) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Get the rotation quaternion.&quot;&quot;&quot;<br>
&#9;&#9;return self._ang<br>
<br>
&#9;@property<br>
&#9;def lin(self) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Get the translation vector.&quot;&quot;&quot;<br>
&#9;&#9;return self._lin<br>
<br>
&#9;@staticmethod<br>
&#9;def identity():<br>
&#9;&#9;return Pose3(<br>
&#9;&#9;&#9;ang=numpy.array([0.0, 0.0, 0.0, 1.0]),<br>
&#9;&#9;&#9;lin=numpy.array([0.0, 0.0, 0.0])<br>
&#9;&#9;)<br>
<br>
&#9;def rotation_matrix(self):<br>
&#9;&#9;&quot;&quot;&quot;Get the 3x3 rotation matrix corresponding to the pose's orientation.&quot;&quot;&quot;<br>
&#9;&#9;if self._rot_matrix is None:<br>
&#9;&#9;&#9;x, y, z, w = self.ang<br>
&#9;&#9;&#9;self._rot_matrix = numpy.array([<br>
&#9;&#9;&#9;&#9;[1 - 2*(y**2 + z**2), 2*(x*y - z*w), 2*(x*z + y*w)],<br>
&#9;&#9;&#9;&#9;[2*(x*y + z*w), 1 - 2*(x**2 + z**2), 2*(y*z - x*w)],<br>
&#9;&#9;&#9;&#9;[2*(x*z - y*w), 2*(y*z + x*w), 1 - 2*(x**2 + y**2)]<br>
&#9;&#9;&#9;])<br>
&#9;&#9;return self._rot_matrix<br>
<br>
&#9;def as_matrix(self):<br>
&#9;&#9;&quot;&quot;&quot;Get the 4x4 transformation matrix corresponding to the pose.&quot;&quot;&quot;<br>
&#9;&#9;if self._mat is None:<br>
&#9;&#9;&#9;R = self.rotation_matrix()<br>
&#9;&#9;&#9;t = self.lin<br>
&#9;&#9;&#9;self._mat = numpy.eye(4)<br>
&#9;&#9;&#9;self._mat[:3, :3] = R<br>
&#9;&#9;&#9;self._mat[:3, 3] = t<br>
&#9;&#9;return self._mat<br>
<br>
&#9;def as_matrix34(self):<br>
&#9;&#9;&quot;&quot;&quot;Get the 3x4 transformation matrix corresponding to the pose.&quot;&quot;&quot;<br>
&#9;&#9;if self._mat34 is None:<br>
&#9;&#9;&#9;R = self.rotation_matrix()<br>
&#9;&#9;&#9;t = self.lin<br>
&#9;&#9;&#9;self._mat34 = numpy.zeros((3, 4))<br>
&#9;&#9;&#9;self._mat34[:, :3] = R<br>
&#9;&#9;&#9;self._mat34[:, 3] = t<br>
&#9;&#9;return self._mat34<br>
<br>
&#9;def inverse(self):<br>
&#9;&#9;&quot;&quot;&quot;Compute the inverse of the pose.&quot;&quot;&quot;<br>
&#9;&#9;x, y, z, w = self.ang<br>
&#9;&#9;tx, ty, tz = self.lin<br>
&#9;&#9;inv_ang = numpy.array([-x, -y, -z, w])<br>
&#9;&#9;inv_lin = qrot(inv_ang, -self.lin)<br>
&#9;&#9;return Pose3(inv_ang, inv_lin)<br>
<br>
&#9;def __repr__(self):<br>
&#9;&#9;return f&quot;Pose3(ang={self.ang}, lin={self.lin})&quot;<br>
<br>
&#9;def transform_point(self, point: numpy.ndarray) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Transform a 3D point using the pose.&quot;&quot;&quot;<br>
&#9;&#9;return qrot(self.ang, point) + self.lin<br>
<br>
&#9;def rotate_point(self, point: numpy.ndarray) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Rotate a 3D point using the pose (ignoring translation).&quot;&quot;&quot;<br>
&#9;&#9;return qrot(self.ang, point)<br>
<br>
&#9;def transform_vector(self, vector: numpy.ndarray) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Transform a 3D vector using the pose (ignoring translation).&quot;&quot;&quot;<br>
&#9;&#9;return qrot(self.ang, vector)<br>
<br>
&#9;def inverse_transform_point(self, pnt):<br>
&#9;&#9;return qrot(qinv(self.ang), pnt - self.lin)<br>
&#9;<br>
&#9;def inverse_transform_vector(self, vec):<br>
&#9;&#9;return qrot(qinv(self.ang), vec)<br>
<br>
&#9;def __mul__(self, other):<br>
&#9;&#9;&quot;&quot;&quot;Compose this pose with another pose.&quot;&quot;&quot;<br>
&#9;&#9;if not isinstance(other, Pose3):<br>
&#9;&#9;&#9;raise TypeError(&quot;Can only multiply Pose3 with Pose3&quot;)<br>
&#9;&#9;q = qmul(self.ang, other.ang)<br>
&#9;&#9;t = self.lin + qrot(self.ang, other.lin)<br>
&#9;&#9;return Pose3(ang=q, lin=t)<br>
<br>
&#9;def __matmul__(self, other):<br>
&#9;&#9;&quot;&quot;&quot;Compose this pose with another pose using @ operator.&quot;&quot;&quot;<br>
&#9;&#9;return self * other<br>
&#9;<br>
&#9;def compose(self, other: 'Pose3') -&gt; 'Pose3':<br>
&#9;&#9;&quot;&quot;&quot;Compose this pose with another pose.&quot;&quot;&quot;<br>
&#9;&#9;return self * other<br>
<br>
&#9;def with_rotation(self, ang: numpy.ndarray) -&gt; 'Pose3':<br>
&#9;&#9;&quot;&quot;&quot;Return a new Pose3 with the given rotation and the same translation.&quot;&quot;&quot;<br>
&#9;&#9;return Pose3(ang=ang, lin=self.lin)<br>
<br>
&#9;def with_translation(self, lin: numpy.ndarray) -&gt; 'Pose3':<br>
&#9;&#9;&quot;&quot;&quot;Return a new Pose3 with the given translation and the same rotation.&quot;&quot;&quot;<br>
&#9;&#9;return Pose3(ang=self.ang, lin=lin)<br>
<br>
&#9;@staticmethod<br>
&#9;def rotation(axis: numpy.ndarray, angle: float):<br>
&#9;&#9;&quot;&quot;&quot;Create a rotation pose around a given axis by a given angle.&quot;&quot;&quot;<br>
&#9;&#9;axis = axis / numpy.linalg.norm(axis)<br>
&#9;&#9;s = math.sin(angle / 2)<br>
&#9;&#9;c = math.cos(angle / 2)<br>
&#9;&#9;q = numpy.array([axis[0] * s, axis[1] * s, axis[2] * s, c])<br>
&#9;&#9;print(&quot;Rotation axis:&quot;, axis)<br>
&#9;&#9;print(&quot;Rotation angle (radians):&quot;, angle)<br>
&#9;&#9;print(&quot;Rotation sin(angle/2):&quot;, s)<br>
&#9;&#9;print(&quot;Rotation cos(angle/2):&quot;, c)<br>
&#9;&#9;print(&quot;Rotation quaternion:&quot;, q)<br>
&#9;&#9;return Pose3(ang=q, lin=numpy.array([0.0, 0.0, 0.0]))<br>
<br>
&#9;@staticmethod<br>
&#9;def translation(x: float, y: float, z: float):<br>
&#9;&#9;&quot;&quot;&quot;Create a translation pose.&quot;&quot;&quot;<br>
&#9;&#9;return Pose3(ang=numpy.array([0.0, 0.0, 0.0, 1.0]), lin=numpy.array([x, y, z]))<br>
<br>
&#9;@staticmethod<br>
&#9;def rotateX(angle: float):<br>
&#9;&#9;&quot;&quot;&quot;Create a rotation pose around the X axis.&quot;&quot;&quot;<br>
&#9;&#9;return Pose3.rotation(numpy.array([1.0, 0.0, 0.0]), angle)<br>
<br>
&#9;@staticmethod<br>
&#9;def rotateY(angle: float):<br>
&#9;&#9;&quot;&quot;&quot;Create a rotation pose around the Y axis.&quot;&quot;&quot;<br>
&#9;&#9;return Pose3.rotation(numpy.array([0.0, 1.0, 0.0]), angle)<br>
&#9;<br>
&#9;@staticmethod<br>
&#9;def rotateZ(angle: float):<br>
&#9;&#9;&quot;&quot;&quot;Create a rotation pose around the Z axis.&quot;&quot;&quot;<br>
&#9;&#9;return Pose3.rotation(numpy.array([0.0, 0.0, 1.0]), angle)<br>
<br>
&#9;@staticmethod<br>
&#9;def move(dx: float, dy: float, dz: float):<br>
&#9;&#9;&quot;&quot;&quot;Move the pose by given deltas in local coordinates.&quot;&quot;&quot;<br>
&#9;&#9;return Pose3.translation(dx, dy, dz)<br>
<br>
&#9;@staticmethod<br>
&#9;def moveX(distance: float):<br>
&#9;&#9;return Pose3.move(distance, 0.0, 0.0)<br>
&#9;<br>
&#9;@staticmethod<br>
&#9;def moveY(distance: float):<br>
&#9;&#9;return Pose3.move(0.0, distance, 0.0)<br>
<br>
&#9;@staticmethod<br>
&#9;def moveZ(distance: float):<br>
&#9;&#9;return Pose3.move(0.0, 0.0, distance)<br>
<br>
&#9;@staticmethod<br>
&#9;def right(distance: float):<br>
&#9;&#9;return Pose3.move(distance, 0.0, 0.0)<br>
<br>
&#9;@staticmethod<br>
&#9;def forward(distance: float):<br>
&#9;&#9;return Pose3.move(0.0, distance, 0.0)<br>
<br>
&#9;@staticmethod<br>
&#9;def up(distance: float):<br>
&#9;&#9;return Pose3.move(0.0, 0.0, distance)<br>
<br>
<br>
&#9;@staticmethod<br>
&#9;def lerp(pose1: 'Pose3', pose2: 'Pose3', t: float) -&gt; 'Pose3':<br>
&#9;&#9;&quot;&quot;&quot;Linearly interpolate between two poses.&quot;&quot;&quot;<br>
&#9;&#9;lerped_ang = qslerp(pose1.ang, pose2.ang, t)<br>
&#9;&#9;lerped_lin = (1 - t) * pose1.lin + t * pose2.lin<br>
&#9;&#9;return Pose3(ang=lerped_ang, lin=lerped_lin)<br>
<br>
&#9;# def normalize(self):<br>
&#9;#     &quot;&quot;&quot;Normalize the quaternion to unit length.&quot;&quot;&quot;<br>
&#9;#     norm = numpy.linalg.norm(self.ang)<br>
&#9;#     if norm &gt; 0:<br>
&#9;#         self.ang = self.ang / norm<br>
&#9;#         self._rot_matrix = None<br>
&#9;#         self._mat = None<br>
&#9;#         self._mat34 = None<br>
<br>
&#9;def normalized(self) -&gt; 'Pose3':<br>
&#9;&#9;&quot;&quot;&quot;Return a new Pose3 with normalized quaternion.&quot;&quot;&quot;<br>
&#9;&#9;norm = numpy.linalg.norm(self.ang)<br>
&#9;&#9;if norm &gt; 0:<br>
&#9;&#9;&#9;ang = self.ang / norm<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;ang = self.ang<br>
&#9;&#9;return Pose3(ang=ang, lin=self.lin)<br>
<br>
&#9;def distance(self, other: 'Pose3') -&gt; float:<br>
&#9;&#9;&quot;&quot;&quot;Calculate Euclidean distance between the translation parts of two poses.&quot;&quot;&quot;<br>
&#9;&#9;return numpy.linalg.norm(self.lin - other.lin)<br>
<br>
&#9;def to_axis_angle(self):<br>
&#9;&#9;&quot;&quot;&quot;Convert quaternion to axis-angle representation.<br>
&#9;&#9;Returns: (axis, angle) where axis is a 3D unit vector and angle is in radians.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;x, y, z, w = self.ang<br>
&#9;&#9;angle = 2 * math.acos(numpy.clip(w, -1.0, 1.0))<br>
&#9;&#9;s = math.sqrt(1 - w*w)<br>
&#9;&#9;if s &lt; 0.001:  # If angle is close to 0<br>
&#9;&#9;&#9;axis = numpy.array([1.0, 0.0, 0.0])<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;axis = numpy.array([x / s, y / s, z / s])<br>
&#9;&#9;return axis, angle<br>
<br>
&#9;@staticmethod<br>
&#9;def from_axis_angle(axis: numpy.ndarray, angle: float):<br>
&#9;&#9;&quot;&quot;&quot;Create a Pose3 from axis-angle representation.&quot;&quot;&quot;<br>
&#9;&#9;return Pose3.rotation(axis, angle)<br>
<br>
&#9;def to_euler(self, order: str = 'xyz'):<br>
&#9;&#9;&quot;&quot;&quot;Convert quaternion to Euler angles.<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;order: String specifying rotation order (e.g., 'xyz', 'zyx')<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;numpy array of three angles in radians<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;x, y, z, w = self.ang<br>
&#9;&#9;<br>
&#9;&#9;if order == 'xyz':<br>
&#9;&#9;&#9;# Roll (x-axis rotation)<br>
&#9;&#9;&#9;sinr_cosp = 2 * (w * x + y * z)<br>
&#9;&#9;&#9;cosr_cosp = 1 - 2 * (x * x + y * y)<br>
&#9;&#9;&#9;roll = math.atan2(sinr_cosp, cosr_cosp)<br>
&#9;&#9;&#9;<br>
&#9;&#9;&#9;# Pitch (y-axis rotation)<br>
&#9;&#9;&#9;sinp = 2 * (w * y - z * x)<br>
&#9;&#9;&#9;sinp = numpy.clip(sinp, -1.0, 1.0)<br>
&#9;&#9;&#9;pitch = math.asin(sinp)<br>
&#9;&#9;&#9;<br>
&#9;&#9;&#9;# Yaw (z-axis rotation)<br>
&#9;&#9;&#9;siny_cosp = 2 * (w * z + x * y)<br>
&#9;&#9;&#9;cosy_cosp = 1 - 2 * (y * y + z * z)<br>
&#9;&#9;&#9;yaw = math.atan2(siny_cosp, cosy_cosp)<br>
&#9;&#9;&#9;<br>
&#9;&#9;&#9;return numpy.array([roll, pitch, yaw])<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;raise NotImplementedError(f&quot;Euler order '{order}' not implemented&quot;)<br>
<br>
&#9;@staticmethod<br>
&#9;def from_euler(roll: float, pitch: float, yaw: float, order: str = 'xyz'):<br>
&#9;&#9;&quot;&quot;&quot;Create a Pose3 from Euler angles.<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;roll, pitch, yaw: Rotation angles in radians<br>
&#9;&#9;&#9;order: String specifying rotation order (default: 'xyz')<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;if order == 'xyz':<br>
&#9;&#9;&#9;# Compute half angles<br>
&#9;&#9;&#9;cr = math.cos(roll * 0.5)<br>
&#9;&#9;&#9;sr = math.sin(roll * 0.5)<br>
&#9;&#9;&#9;cp = math.cos(pitch * 0.5)<br>
&#9;&#9;&#9;sp = math.sin(pitch * 0.5)<br>
&#9;&#9;&#9;cy = math.cos(yaw * 0.5)<br>
&#9;&#9;&#9;sy = math.sin(yaw * 0.5)<br>
&#9;&#9;&#9;<br>
&#9;&#9;&#9;# Compute quaternion<br>
&#9;&#9;&#9;qx = sr * cp * cy - cr * sp * sy<br>
&#9;&#9;&#9;qy = cr * sp * cy + sr * cp * sy<br>
&#9;&#9;&#9;qz = cr * cp * sy - sr * sp * cy<br>
&#9;&#9;&#9;qw = cr * cp * cy + sr * sp * sy<br>
&#9;&#9;&#9;<br>
&#9;&#9;&#9;return Pose3(ang=numpy.array([qx, qy, qz, qw]), lin=numpy.array([0.0, 0.0, 0.0]))<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;raise NotImplementedError(f&quot;Euler order '{order}' not implemented&quot;)<br>
<br>
&#9;@staticmethod<br>
&#9;def looking_at(eye: numpy.ndarray, target: numpy.ndarray, up: numpy.ndarray = numpy.array([0.0, 0.0, 1.0])):<br>
&#9;&#9;&quot;&quot;&quot;Create a pose at 'eye' position looking towards 'target'.<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;eye: Position of the pose<br>
&#9;&#9;&#9;target: Point to look at<br>
&#9;&#9;&#9;up: Up vector (default: z-axis)<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;forward = target - eye<br>
&#9;&#9;forward = forward / numpy.linalg.norm(forward)<br>
&#9;&#9;<br>
&#9;&#9;right = numpy.cross(forward, up)<br>
&#9;&#9;right = right / numpy.linalg.norm(right)<br>
&#9;&#9;<br>
&#9;&#9;up_corrected = numpy.cross(right, forward)<br>
&#9;&#9;<br>
&#9;&#9;# Build rotation matrix<br>
&#9;&#9;rot_mat = numpy.column_stack([right, up_corrected, -forward])<br>
&#9;&#9;<br>
&#9;&#9;# Convert rotation matrix to quaternion<br>
&#9;&#9;trace = numpy.trace(rot_mat)<br>
&#9;&#9;if trace &gt; 0:<br>
&#9;&#9;&#9;s = 0.5 / math.sqrt(trace + 1.0)<br>
&#9;&#9;&#9;qw = 0.25 / s<br>
&#9;&#9;&#9;qx = (rot_mat[2, 1] - rot_mat[1, 2]) * s<br>
&#9;&#9;&#9;qy = (rot_mat[0, 2] - rot_mat[2, 0]) * s<br>
&#9;&#9;&#9;qz = (rot_mat[1, 0] - rot_mat[0, 1]) * s<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;if rot_mat[0, 0] &gt; rot_mat[1, 1] and rot_mat[0, 0] &gt; rot_mat[2, 2]:<br>
&#9;&#9;&#9;&#9;s = 2.0 * math.sqrt(1.0 + rot_mat[0, 0] - rot_mat[1, 1] - rot_mat[2, 2])<br>
&#9;&#9;&#9;&#9;qw = (rot_mat[2, 1] - rot_mat[1, 2]) / s<br>
&#9;&#9;&#9;&#9;qx = 0.25 * s<br>
&#9;&#9;&#9;&#9;qy = (rot_mat[0, 1] + rot_mat[1, 0]) / s<br>
&#9;&#9;&#9;&#9;qz = (rot_mat[0, 2] + rot_mat[2, 0]) / s<br>
&#9;&#9;&#9;elif rot_mat[1, 1] &gt; rot_mat[2, 2]:<br>
&#9;&#9;&#9;&#9;s = 2.0 * math.sqrt(1.0 + rot_mat[1, 1] - rot_mat[0, 0] - rot_mat[2, 2])<br>
&#9;&#9;&#9;&#9;qw = (rot_mat[0, 2] - rot_mat[2, 0]) / s<br>
&#9;&#9;&#9;&#9;qx = (rot_mat[0, 1] + rot_mat[1, 0]) / s<br>
&#9;&#9;&#9;&#9;qy = 0.25 * s<br>
&#9;&#9;&#9;&#9;qz = (rot_mat[1, 2] + rot_mat[2, 1]) / s<br>
&#9;&#9;&#9;else:<br>
&#9;&#9;&#9;&#9;s = 2.0 * math.sqrt(1.0 + rot_mat[2, 2] - rot_mat[0, 0] - rot_mat[1, 1])<br>
&#9;&#9;&#9;&#9;qw = (rot_mat[1, 0] - rot_mat[0, 1]) / s<br>
&#9;&#9;&#9;&#9;qx = (rot_mat[0, 2] + rot_mat[2, 0]) / s<br>
&#9;&#9;&#9;&#9;qy = (rot_mat[1, 2] + rot_mat[2, 1]) / s<br>
&#9;&#9;&#9;&#9;qz = 0.25 * s<br>
&#9;&#9;<br>
&#9;&#9;return Pose3(ang=numpy.array([qx, qy, qz, qw]), lin=eye)<br>
<br>
&#9;@property<br>
&#9;def x(self):<br>
&#9;&#9;&quot;&quot;&quot;Get X coordinate of translation.&quot;&quot;&quot;<br>
&#9;&#9;return self.lin[0]<br>
<br>
&#9;@property<br>
&#9;def y(self):<br>
&#9;&#9;&quot;&quot;&quot;Get Y coordinate of translation.&quot;&quot;&quot;<br>
&#9;&#9;return self.lin[1]<br>
<br>
&#9;@property<br>
&#9;def z(self):<br>
&#9;&#9;&quot;&quot;&quot;Get Z coordinate of translation.&quot;&quot;&quot;<br>
&#9;&#9;return self.lin[2]<br>
<br>
&#9;@x.setter<br>
&#9;def x(self, value: float):<br>
&#9;&#9;&quot;&quot;&quot;Set X coordinate of translation.&quot;&quot;&quot;<br>
&#9;&#9;self.lin[0] = value<br>
&#9;&#9;self._mat = None<br>
&#9;&#9;self._mat34 = None<br>
<br>
&#9;@y.setter<br>
&#9;def y(self, value: float):<br>
&#9;&#9;&quot;&quot;&quot;Set Y coordinate of translation.&quot;&quot;&quot;<br>
&#9;&#9;self.lin[1] = value<br>
&#9;&#9;self._mat = None<br>
&#9;&#9;self._mat34 = None<br>
<br>
&#9;@z.setter<br>
&#9;def z(self, value: float):<br>
&#9;&#9;&quot;&quot;&quot;Set Z coordinate of translation.&quot;&quot;&quot;<br>
&#9;&#9;self.lin[2] = value<br>
&#9;&#9;self._mat = None<br>
&#9;&#9;self._mat34 = None<br>
<br>
&#9;@staticmethod<br>
&#9;def from_vector_vw_order(vec: numpy.ndarray) -&gt; 'Pose3':<br>
&#9;&#9;&quot;&quot;&quot;Create Pose3 from a 7D vector in (vx, vy, vz, wx, wy, wz, w) order.&quot;&quot;&quot;<br>
&#9;&#9;if vec.shape != (7,):<br>
&#9;&#9;&#9;raise ValueError(&quot;Input vector must be of shape (7,)&quot;)<br>
&#9;&#9;ang = vec[3:7]<br>
&#9;&#9;lin = vec[0:3]<br>
&#9;&#9;return Pose3(ang=ang, lin=lin)<br>
<br>
&#9;def to_vector_vw_order(self) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Convert Pose3 to a 7D vector in (vx, vy, vz, wx, wy, wz, w) order.&quot;&quot;&quot;<br>
&#9;&#9;vec = numpy.zeros(7)<br>
&#9;&#9;vec[0:3] = self.lin<br>
&#9;&#9;vec[3:7] = self.ang<br>
&#9;&#9;return vec<br>
<br>
&#9;def rotate_vector(self, vec: numpy.ndarray) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Rotate a 3D vector using the pose's rotation.&quot;&quot;&quot;<br>
&#9;&#9;return qrot(self.ang, vec)<br>
<!-- END SCAT CODE -->
</body>
</html>
