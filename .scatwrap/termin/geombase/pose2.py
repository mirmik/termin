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
    &quot;&quot;&quot;A 2D Pose represented by rotation angle and translation vector.&quot;&quot;&quot;<br>
<br>
    def __init__(self, ang: float = 0.0, lin: numpy.ndarray = numpy.array([0.0, 0.0])):<br>
        &quot;&quot;&quot;<br>
        Args:<br>
            ang: Rotation angle in radians<br>
            lin: Translation vector [x, y]<br>
        &quot;&quot;&quot;<br>
        self.ang = ang<br>
        self.lin = numpy.asarray(lin)<br>
        if self.lin.shape != (2,):<br>
            raise ValueError(&quot;lin must be a 2D vector&quot;)<br>
        self._rot_matrix = None  # Lazy computation<br>
        self._mat = None  # Lazy computation<br>
<br>
    @staticmethod<br>
    def identity():<br>
        &quot;&quot;&quot;Create an identity pose (no rotation, no translation).&quot;&quot;&quot;<br>
        return Pose2(ang=0.0, lin=numpy.array([0.0, 0.0]))<br>
<br>
    def rotation_matrix(self):<br>
        &quot;&quot;&quot;Get the 2x2 rotation matrix corresponding to the pose's orientation.&quot;&quot;&quot;<br>
        if self._rot_matrix is None:<br>
            c = math.cos(self.ang)<br>
            s = math.sin(self.ang)<br>
            self._rot_matrix = numpy.array([<br>
                [c, -s],<br>
                [s,  c]<br>
            ])<br>
        return self._rot_matrix<br>
<br>
    def as_matrix(self):<br>
        &quot;&quot;&quot;Get the 3x3 transformation matrix corresponding to the pose.&quot;&quot;&quot;<br>
        if self._mat is None:<br>
            R = self.rotation_matrix()<br>
            t = self.lin<br>
            self._mat = numpy.eye(3)<br>
            self._mat[:2, :2] = R<br>
            self._mat[:2, 2] = t<br>
        return self._mat<br>
<br>
    def inverse(self):<br>
        &quot;&quot;&quot;Compute the inverse of the pose.&quot;&quot;&quot;<br>
        inv_ang = -self.ang<br>
        c = math.cos(inv_ang)<br>
        s = math.sin(inv_ang)<br>
        # Rotate translation by inverse rotation<br>
        inv_lin = numpy.array([<br>
            c * (-self.lin[0]) - s * (-self.lin[1]),<br>
            s * (-self.lin[0]) + c * (-self.lin[1])<br>
        ])<br>
        return Pose2(inv_ang, inv_lin)<br>
<br>
    def __repr__(self):<br>
        return f&quot;Pose2(ang={self.ang}, lin={self.lin})&quot;<br>
<br>
    def transform_point(self, point: numpy.ndarray) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Transform a 2D point using the pose.&quot;&quot;&quot;<br>
        point = numpy.asarray(point)<br>
        if point.shape != (2,):<br>
            raise ValueError(&quot;point must be a 2D vector&quot;)<br>
        R = self.rotation_matrix()<br>
        return R @ point + self.lin<br>
<br>
    def transform_vector(self, vector: numpy.ndarray) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Transform a 2D vector using the pose (ignoring translation).&quot;&quot;&quot;<br>
        vector = numpy.asarray(vector)<br>
        if vector.shape != (2,):<br>
            raise ValueError(&quot;vector must be a 2D vector&quot;)<br>
        R = self.rotation_matrix()<br>
        return R @ vector<br>
<br>
    def rotate_vector(self, vector: numpy.ndarray) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Rotate a 2D vector using the pose's rotation.&quot;&quot;&quot;<br>
        vector = numpy.asarray(vector)<br>
        if vector.shape != (2,):<br>
            raise ValueError(&quot;vector must be a 2D vector&quot;)<br>
        R = self.rotation_matrix()<br>
        return R @ vector<br>
<br>
    def inverse_transform_point(self, point: numpy.ndarray) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Transform a 2D point using the inverse of the pose.&quot;&quot;&quot;<br>
        point = numpy.asarray(point)<br>
        point = point.reshape(2)<br>
        R = self.rotation_matrix()<br>
        return R.T @ (point - self.lin)<br>
<br>
    def inverse_rotate_vector(self, vector: numpy.ndarray) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Rotate a 2D vector using the inverse of the pose's rotation.&quot;&quot;&quot;<br>
        vector = numpy.asarray(vector)<br>
        if vector.shape != (2,):<br>
            raise ValueError(&quot;vector must be a 2D vector&quot;)<br>
        R = self.rotation_matrix()<br>
        return R.T @ vector<br>
<br>
    def inverse_transform_vector(self, vector: numpy.ndarray) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Transform a 2D vector using the inverse of the pose (ignoring translation).&quot;&quot;&quot;<br>
        vector = numpy.asarray(vector)<br>
        if vector.shape != (2,):<br>
            raise ValueError(&quot;vector must be a 2D vector&quot;)<br>
        R = self.rotation_matrix()<br>
        return R.T @ vector<br>
<br>
    def __mul__(self, other):<br>
        &quot;&quot;&quot;Compose this pose with another pose.&quot;&quot;&quot;<br>
        if not isinstance(other, Pose2):<br>
            raise TypeError(&quot;Can only multiply Pose2 with Pose2&quot;)<br>
        # Compose rotations: angles add<br>
        new_ang = self.ang + other.ang<br>
        # Compose translations: rotate other's translation and add to self's<br>
        R = self.rotation_matrix()<br>
        new_lin = self.lin + R @ other.lin<br>
        return Pose2(ang=new_ang, lin=new_lin)<br>
<br>
    def __matmul__(self, other):<br>
        &quot;&quot;&quot;Compose this pose with another pose using @ operator.&quot;&quot;&quot;<br>
        return self * other<br>
<br>
    def compose(self, other: 'Pose2') -&gt; 'Pose2':<br>
        &quot;&quot;&quot;Compose this pose with another pose.&quot;&quot;&quot;<br>
        return self * other<br>
<br>
    @staticmethod<br>
    def rotation(angle: float):<br>
        &quot;&quot;&quot;Create a rotation pose by a given angle.&quot;&quot;&quot;<br>
        return Pose2(ang=angle, lin=numpy.array([0.0, 0.0]))<br>
<br>
    @staticmethod<br>
    def translation(x: float, y: float):<br>
        &quot;&quot;&quot;Create a translation pose.&quot;&quot;&quot;<br>
        return Pose2(ang=0.0, lin=numpy.array([x, y]))<br>
<br>
    @staticmethod<br>
    def move(dx: float, dy: float):<br>
        &quot;&quot;&quot;Move the pose by given deltas in local coordinates.&quot;&quot;&quot;<br>
        return Pose2.translation(dx, dy)<br>
<br>
    @staticmethod<br>
    def moveX(distance: float):<br>
        &quot;&quot;&quot;Move along X axis.&quot;&quot;&quot;<br>
        return Pose2.move(distance, 0.0)<br>
<br>
    @staticmethod<br>
    def moveY(distance: float):<br>
        &quot;&quot;&quot;Move along Y axis.&quot;&quot;&quot;<br>
        return Pose2.move(0.0, distance)<br>
<br>
    @staticmethod<br>
    def right(distance: float):<br>
        &quot;&quot;&quot;Move right (along X axis).&quot;&quot;&quot;<br>
        return Pose2.move(distance, 0.0)<br>
<br>
    @staticmethod<br>
    def forward(distance: float):<br>
        &quot;&quot;&quot;Move forward (along Y axis).&quot;&quot;&quot;<br>
        return Pose2.move(0.0, distance)<br>
<br>
    @staticmethod<br>
    def lerp(pose1: 'Pose2', pose2: 'Pose2', t: float) -&gt; 'Pose2':<br>
        &quot;&quot;&quot;Linearly interpolate between two poses.&quot;&quot;&quot;<br>
        lerped_ang = (1 - t) * pose1.ang + t * pose2.ang<br>
        lerped_lin = (1 - t) * pose1.lin + t * pose2.lin<br>
        return Pose2(ang=lerped_ang, lin=lerped_lin)<br>
<br>
    def normalize_angle(self):<br>
        &quot;&quot;&quot;Normalize the angle to [-π, π].&quot;&quot;&quot;<br>
        self.ang = math.atan2(math.sin(self.ang), math.cos(self.ang))<br>
        self._rot_matrix = None<br>
        self._mat = None<br>
<br>
    @property<br>
    def x(self):<br>
        &quot;&quot;&quot;Get X coordinate of translation.&quot;&quot;&quot;<br>
        return self.lin[0]<br>
<br>
    @property<br>
    def y(self):<br>
        &quot;&quot;&quot;Get Y coordinate of translation.&quot;&quot;&quot;<br>
        return self.lin[1]<br>
<br>
    @x.setter<br>
    def x(self, value: float):<br>
        &quot;&quot;&quot;Set X coordinate of translation.&quot;&quot;&quot;<br>
        self.lin[0] = value<br>
        self._mat = None<br>
<br>
    @y.setter<br>
    def y(self, value: float):<br>
        &quot;&quot;&quot;Set Y coordinate of translation.&quot;&quot;&quot;<br>
        self.lin[1] = value<br>
        self._mat = None<br>
<!-- END SCAT CODE -->
</body>
</html>
