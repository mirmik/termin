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
    &quot;&quot;&quot;A 3D Pose represented by rotation quaternion and translation vector.&quot;&quot;&quot;<br>
<br>
    def __init__(self, ang: numpy.ndarray = None, lin: numpy.ndarray = None):<br>
        if ang is None:<br>
            ang = numpy.array([0.0, 0.0, 0.0, 1.0])<br>
        if lin is None:<br>
            lin = numpy.array([0.0, 0.0, 0.0])<br>
        self._ang = ang<br>
        self._lin = lin<br>
        self._rot_matrix = None  # Lazy computation<br>
        self._mat = None  # Lazy computation<br>
        self._mat34 = None  # Lazy computation<br>
<br>
    @property<br>
    def ang(self) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Get the rotation quaternion.&quot;&quot;&quot;<br>
        return self._ang<br>
<br>
    @property<br>
    def lin(self) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Get the translation vector.&quot;&quot;&quot;<br>
        return self._lin<br>
<br>
    @staticmethod<br>
    def identity():<br>
        return Pose3(<br>
            ang=numpy.array([0.0, 0.0, 0.0, 1.0]),<br>
            lin=numpy.array([0.0, 0.0, 0.0])<br>
        )<br>
<br>
    def rotation_matrix(self):<br>
        &quot;&quot;&quot;Get the 3x3 rotation matrix corresponding to the pose's orientation.&quot;&quot;&quot;<br>
        if self._rot_matrix is None:<br>
            x, y, z, w = self.ang<br>
            self._rot_matrix = numpy.array([<br>
                [1 - 2*(y**2 + z**2), 2*(x*y - z*w), 2*(x*z + y*w)],<br>
                [2*(x*y + z*w), 1 - 2*(x**2 + z**2), 2*(y*z - x*w)],<br>
                [2*(x*z - y*w), 2*(y*z + x*w), 1 - 2*(x**2 + y**2)]<br>
            ])<br>
        return self._rot_matrix<br>
<br>
    def as_matrix(self):<br>
        &quot;&quot;&quot;Get the 4x4 transformation matrix corresponding to the pose.&quot;&quot;&quot;<br>
        if self._mat is None:<br>
            R = self.rotation_matrix()<br>
            t = self.lin<br>
            self._mat = numpy.eye(4)<br>
            self._mat[:3, :3] = R<br>
            self._mat[:3, 3] = t<br>
        return self._mat<br>
<br>
    def as_matrix34(self):<br>
        &quot;&quot;&quot;Get the 3x4 transformation matrix corresponding to the pose.&quot;&quot;&quot;<br>
        if self._mat34 is None:<br>
            R = self.rotation_matrix()<br>
            t = self.lin<br>
            self._mat34 = numpy.zeros((3, 4))<br>
            self._mat34[:, :3] = R<br>
            self._mat34[:, 3] = t<br>
        return self._mat34<br>
<br>
    def inverse(self):<br>
        &quot;&quot;&quot;Compute the inverse of the pose.&quot;&quot;&quot;<br>
        x, y, z, w = self.ang<br>
        tx, ty, tz = self.lin<br>
        inv_ang = numpy.array([-x, -y, -z, w])<br>
        inv_lin = qrot(inv_ang, -self.lin)<br>
        return Pose3(inv_ang, inv_lin)<br>
<br>
    def __repr__(self):<br>
        return f&quot;Pose3(ang={self.ang}, lin={self.lin})&quot;<br>
<br>
    def transform_point(self, point: numpy.ndarray) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Transform a 3D point using the pose.&quot;&quot;&quot;<br>
        return qrot(self.ang, point) + self.lin<br>
<br>
    def rotate_point(self, point: numpy.ndarray) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Rotate a 3D point using the pose (ignoring translation).&quot;&quot;&quot;<br>
        return qrot(self.ang, point)<br>
<br>
    def transform_vector(self, vector: numpy.ndarray) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Transform a 3D vector using the pose (ignoring translation).&quot;&quot;&quot;<br>
        return qrot(self.ang, vector)<br>
<br>
    def inverse_transform_point(self, pnt):<br>
        return qrot(qinv(self.ang), pnt - self.lin)<br>
    <br>
    def inverse_transform_vector(self, vec):<br>
        return qrot(qinv(self.ang), vec)<br>
<br>
    def __mul__(self, other):<br>
        &quot;&quot;&quot;Compose this pose with another pose.&quot;&quot;&quot;<br>
        if not isinstance(other, Pose3):<br>
            raise TypeError(&quot;Can only multiply Pose3 with Pose3&quot;)<br>
        q = qmul(self.ang, other.ang)<br>
        t = self.lin + qrot(self.ang, other.lin)<br>
        return Pose3(ang=q, lin=t)<br>
<br>
    def __matmul__(self, other):<br>
        &quot;&quot;&quot;Compose this pose with another pose using @ operator.&quot;&quot;&quot;<br>
        return self * other<br>
    <br>
    def compose(self, other: 'Pose3') -&gt; 'Pose3':<br>
        &quot;&quot;&quot;Compose this pose with another pose.&quot;&quot;&quot;<br>
        return self * other<br>
<br>
    def with_rotation(self, ang: numpy.ndarray) -&gt; 'Pose3':<br>
        &quot;&quot;&quot;Return a new Pose3 with the given rotation and the same translation.&quot;&quot;&quot;<br>
        return Pose3(ang=ang, lin=self.lin)<br>
<br>
    def with_translation(self, lin: numpy.ndarray) -&gt; 'Pose3':<br>
        &quot;&quot;&quot;Return a new Pose3 with the given translation and the same rotation.&quot;&quot;&quot;<br>
        return Pose3(ang=self.ang, lin=lin)<br>
<br>
    @staticmethod<br>
    def rotation(axis: numpy.ndarray, angle: float):<br>
        &quot;&quot;&quot;Create a rotation pose around a given axis by a given angle.&quot;&quot;&quot;<br>
        axis = axis / numpy.linalg.norm(axis)<br>
        s = math.sin(angle / 2)<br>
        c = math.cos(angle / 2)<br>
        q = numpy.array([axis[0] * s, axis[1] * s, axis[2] * s, c])<br>
        print(&quot;Rotation axis:&quot;, axis)<br>
        print(&quot;Rotation angle (radians):&quot;, angle)<br>
        print(&quot;Rotation sin(angle/2):&quot;, s)<br>
        print(&quot;Rotation cos(angle/2):&quot;, c)<br>
        print(&quot;Rotation quaternion:&quot;, q)<br>
        return Pose3(ang=q, lin=numpy.array([0.0, 0.0, 0.0]))<br>
<br>
    @staticmethod<br>
    def translation(x: float, y: float, z: float):<br>
        &quot;&quot;&quot;Create a translation pose.&quot;&quot;&quot;<br>
        return Pose3(ang=numpy.array([0.0, 0.0, 0.0, 1.0]), lin=numpy.array([x, y, z]))<br>
<br>
    @staticmethod<br>
    def rotateX(angle: float):<br>
        &quot;&quot;&quot;Create a rotation pose around the X axis.&quot;&quot;&quot;<br>
        return Pose3.rotation(numpy.array([1.0, 0.0, 0.0]), angle)<br>
<br>
    @staticmethod<br>
    def rotateY(angle: float):<br>
        &quot;&quot;&quot;Create a rotation pose around the Y axis.&quot;&quot;&quot;<br>
        return Pose3.rotation(numpy.array([0.0, 1.0, 0.0]), angle)<br>
    <br>
    @staticmethod<br>
    def rotateZ(angle: float):<br>
        &quot;&quot;&quot;Create a rotation pose around the Z axis.&quot;&quot;&quot;<br>
        return Pose3.rotation(numpy.array([0.0, 0.0, 1.0]), angle)<br>
<br>
    @staticmethod<br>
    def move(dx: float, dy: float, dz: float):<br>
        &quot;&quot;&quot;Move the pose by given deltas in local coordinates.&quot;&quot;&quot;<br>
        return Pose3.translation(dx, dy, dz)<br>
<br>
    @staticmethod<br>
    def moveX(distance: float):<br>
        return Pose3.move(distance, 0.0, 0.0)<br>
    <br>
    @staticmethod<br>
    def moveY(distance: float):<br>
        return Pose3.move(0.0, distance, 0.0)<br>
<br>
    @staticmethod<br>
    def moveZ(distance: float):<br>
        return Pose3.move(0.0, 0.0, distance)<br>
<br>
    @staticmethod<br>
    def right(distance: float):<br>
        return Pose3.move(distance, 0.0, 0.0)<br>
<br>
    @staticmethod<br>
    def forward(distance: float):<br>
        return Pose3.move(0.0, distance, 0.0)<br>
<br>
    @staticmethod<br>
    def up(distance: float):<br>
        return Pose3.move(0.0, 0.0, distance)<br>
<br>
<br>
    @staticmethod<br>
    def lerp(pose1: 'Pose3', pose2: 'Pose3', t: float) -&gt; 'Pose3':<br>
        &quot;&quot;&quot;Linearly interpolate between two poses.&quot;&quot;&quot;<br>
        lerped_ang = qslerp(pose1.ang, pose2.ang, t)<br>
        lerped_lin = (1 - t) * pose1.lin + t * pose2.lin<br>
        return Pose3(ang=lerped_ang, lin=lerped_lin)<br>
<br>
    # def normalize(self):<br>
    #     &quot;&quot;&quot;Normalize the quaternion to unit length.&quot;&quot;&quot;<br>
    #     norm = numpy.linalg.norm(self.ang)<br>
    #     if norm &gt; 0:<br>
    #         self.ang = self.ang / norm<br>
    #         self._rot_matrix = None<br>
    #         self._mat = None<br>
    #         self._mat34 = None<br>
<br>
    def normalized(self) -&gt; 'Pose3':<br>
        &quot;&quot;&quot;Return a new Pose3 with normalized quaternion.&quot;&quot;&quot;<br>
        norm = numpy.linalg.norm(self.ang)<br>
        if norm &gt; 0:<br>
            ang = self.ang / norm<br>
        else:<br>
            ang = self.ang<br>
        return Pose3(ang=ang, lin=self.lin)<br>
<br>
    def distance(self, other: 'Pose3') -&gt; float:<br>
        &quot;&quot;&quot;Calculate Euclidean distance between the translation parts of two poses.&quot;&quot;&quot;<br>
        return numpy.linalg.norm(self.lin - other.lin)<br>
<br>
    def to_axis_angle(self):<br>
        &quot;&quot;&quot;Convert quaternion to axis-angle representation.<br>
        Returns: (axis, angle) where axis is a 3D unit vector and angle is in radians.<br>
        &quot;&quot;&quot;<br>
        x, y, z, w = self.ang<br>
        angle = 2 * math.acos(numpy.clip(w, -1.0, 1.0))<br>
        s = math.sqrt(1 - w*w)<br>
        if s &lt; 0.001:  # If angle is close to 0<br>
            axis = numpy.array([1.0, 0.0, 0.0])<br>
        else:<br>
            axis = numpy.array([x / s, y / s, z / s])<br>
        return axis, angle<br>
<br>
    @staticmethod<br>
    def from_axis_angle(axis: numpy.ndarray, angle: float):<br>
        &quot;&quot;&quot;Create a Pose3 from axis-angle representation.&quot;&quot;&quot;<br>
        return Pose3.rotation(axis, angle)<br>
<br>
    def to_euler(self, order: str = 'xyz'):<br>
        &quot;&quot;&quot;Convert quaternion to Euler angles.<br>
        Args:<br>
            order: String specifying rotation order (e.g., 'xyz', 'zyx')<br>
        Returns:<br>
            numpy array of three angles in radians<br>
        &quot;&quot;&quot;<br>
        x, y, z, w = self.ang<br>
        <br>
        if order == 'xyz':<br>
            # Roll (x-axis rotation)<br>
            sinr_cosp = 2 * (w * x + y * z)<br>
            cosr_cosp = 1 - 2 * (x * x + y * y)<br>
            roll = math.atan2(sinr_cosp, cosr_cosp)<br>
            <br>
            # Pitch (y-axis rotation)<br>
            sinp = 2 * (w * y - z * x)<br>
            sinp = numpy.clip(sinp, -1.0, 1.0)<br>
            pitch = math.asin(sinp)<br>
            <br>
            # Yaw (z-axis rotation)<br>
            siny_cosp = 2 * (w * z + x * y)<br>
            cosy_cosp = 1 - 2 * (y * y + z * z)<br>
            yaw = math.atan2(siny_cosp, cosy_cosp)<br>
            <br>
            return numpy.array([roll, pitch, yaw])<br>
        else:<br>
            raise NotImplementedError(f&quot;Euler order '{order}' not implemented&quot;)<br>
<br>
    @staticmethod<br>
    def from_euler(roll: float, pitch: float, yaw: float, order: str = 'xyz'):<br>
        &quot;&quot;&quot;Create a Pose3 from Euler angles.<br>
        Args:<br>
            roll, pitch, yaw: Rotation angles in radians<br>
            order: String specifying rotation order (default: 'xyz')<br>
        &quot;&quot;&quot;<br>
        if order == 'xyz':<br>
            # Compute half angles<br>
            cr = math.cos(roll * 0.5)<br>
            sr = math.sin(roll * 0.5)<br>
            cp = math.cos(pitch * 0.5)<br>
            sp = math.sin(pitch * 0.5)<br>
            cy = math.cos(yaw * 0.5)<br>
            sy = math.sin(yaw * 0.5)<br>
            <br>
            # Compute quaternion<br>
            qx = sr * cp * cy - cr * sp * sy<br>
            qy = cr * sp * cy + sr * cp * sy<br>
            qz = cr * cp * sy - sr * sp * cy<br>
            qw = cr * cp * cy + sr * sp * sy<br>
            <br>
            return Pose3(ang=numpy.array([qx, qy, qz, qw]), lin=numpy.array([0.0, 0.0, 0.0]))<br>
        else:<br>
            raise NotImplementedError(f&quot;Euler order '{order}' not implemented&quot;)<br>
<br>
    @staticmethod<br>
    def looking_at(eye: numpy.ndarray, target: numpy.ndarray, up: numpy.ndarray = numpy.array([0.0, 0.0, 1.0])):<br>
        &quot;&quot;&quot;Create a pose at 'eye' position looking towards 'target'.<br>
        Args:<br>
            eye: Position of the pose<br>
            target: Point to look at<br>
            up: Up vector (default: z-axis)<br>
        &quot;&quot;&quot;<br>
        forward = target - eye<br>
        forward = forward / numpy.linalg.norm(forward)<br>
        <br>
        right = numpy.cross(forward, up)<br>
        right = right / numpy.linalg.norm(right)<br>
        <br>
        up_corrected = numpy.cross(right, forward)<br>
        <br>
        # Build rotation matrix<br>
        rot_mat = numpy.column_stack([right, up_corrected, -forward])<br>
        <br>
        # Convert rotation matrix to quaternion<br>
        trace = numpy.trace(rot_mat)<br>
        if trace &gt; 0:<br>
            s = 0.5 / math.sqrt(trace + 1.0)<br>
            qw = 0.25 / s<br>
            qx = (rot_mat[2, 1] - rot_mat[1, 2]) * s<br>
            qy = (rot_mat[0, 2] - rot_mat[2, 0]) * s<br>
            qz = (rot_mat[1, 0] - rot_mat[0, 1]) * s<br>
        else:<br>
            if rot_mat[0, 0] &gt; rot_mat[1, 1] and rot_mat[0, 0] &gt; rot_mat[2, 2]:<br>
                s = 2.0 * math.sqrt(1.0 + rot_mat[0, 0] - rot_mat[1, 1] - rot_mat[2, 2])<br>
                qw = (rot_mat[2, 1] - rot_mat[1, 2]) / s<br>
                qx = 0.25 * s<br>
                qy = (rot_mat[0, 1] + rot_mat[1, 0]) / s<br>
                qz = (rot_mat[0, 2] + rot_mat[2, 0]) / s<br>
            elif rot_mat[1, 1] &gt; rot_mat[2, 2]:<br>
                s = 2.0 * math.sqrt(1.0 + rot_mat[1, 1] - rot_mat[0, 0] - rot_mat[2, 2])<br>
                qw = (rot_mat[0, 2] - rot_mat[2, 0]) / s<br>
                qx = (rot_mat[0, 1] + rot_mat[1, 0]) / s<br>
                qy = 0.25 * s<br>
                qz = (rot_mat[1, 2] + rot_mat[2, 1]) / s<br>
            else:<br>
                s = 2.0 * math.sqrt(1.0 + rot_mat[2, 2] - rot_mat[0, 0] - rot_mat[1, 1])<br>
                qw = (rot_mat[1, 0] - rot_mat[0, 1]) / s<br>
                qx = (rot_mat[0, 2] + rot_mat[2, 0]) / s<br>
                qy = (rot_mat[1, 2] + rot_mat[2, 1]) / s<br>
                qz = 0.25 * s<br>
        <br>
        return Pose3(ang=numpy.array([qx, qy, qz, qw]), lin=eye)<br>
<br>
    @property<br>
    def x(self):<br>
        &quot;&quot;&quot;Get X coordinate of translation.&quot;&quot;&quot;<br>
        return self.lin[0]<br>
<br>
    @property<br>
    def y(self):<br>
        &quot;&quot;&quot;Get Y coordinate of translation.&quot;&quot;&quot;<br>
        return self.lin[1]<br>
<br>
    @property<br>
    def z(self):<br>
        &quot;&quot;&quot;Get Z coordinate of translation.&quot;&quot;&quot;<br>
        return self.lin[2]<br>
<br>
    @x.setter<br>
    def x(self, value: float):<br>
        &quot;&quot;&quot;Set X coordinate of translation.&quot;&quot;&quot;<br>
        self.lin[0] = value<br>
        self._mat = None<br>
        self._mat34 = None<br>
<br>
    @y.setter<br>
    def y(self, value: float):<br>
        &quot;&quot;&quot;Set Y coordinate of translation.&quot;&quot;&quot;<br>
        self.lin[1] = value<br>
        self._mat = None<br>
        self._mat34 = None<br>
<br>
    @z.setter<br>
    def z(self, value: float):<br>
        &quot;&quot;&quot;Set Z coordinate of translation.&quot;&quot;&quot;<br>
        self.lin[2] = value<br>
        self._mat = None<br>
        self._mat34 = None<br>
<br>
    @staticmethod<br>
    def from_vector_vw_order(vec: numpy.ndarray) -&gt; 'Pose3':<br>
        &quot;&quot;&quot;Create Pose3 from a 7D vector in (vx, vy, vz, wx, wy, wz, w) order.&quot;&quot;&quot;<br>
        if vec.shape != (7,):<br>
            raise ValueError(&quot;Input vector must be of shape (7,)&quot;)<br>
        ang = vec[3:7]<br>
        lin = vec[0:3]<br>
        return Pose3(ang=ang, lin=lin)<br>
<br>
    def to_vector_vw_order(self) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Convert Pose3 to a 7D vector in (vx, vy, vz, wx, wy, wz, w) order.&quot;&quot;&quot;<br>
        vec = numpy.zeros(7)<br>
        vec[0:3] = self.lin<br>
        vec[3:7] = self.ang<br>
        return vec<br>
<br>
    def rotate_vector(self, vec: numpy.ndarray) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Rotate a 3D vector using the pose's rotation.&quot;&quot;&quot;<br>
        return qrot(self.ang, vec)<br>
<!-- END SCAT CODE -->
</body>
</html>
