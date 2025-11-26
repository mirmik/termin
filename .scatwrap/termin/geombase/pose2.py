<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/geombase/pose2.py</title>
</head>
<body>
<pre><code>
import math
import numpy


class Pose2:
    &quot;&quot;&quot;A 2D Pose represented by rotation angle and translation vector.&quot;&quot;&quot;

    def __init__(self, ang: float = 0.0, lin: numpy.ndarray = numpy.array([0.0, 0.0])):
        &quot;&quot;&quot;
        Args:
            ang: Rotation angle in radians
            lin: Translation vector [x, y]
        &quot;&quot;&quot;
        self.ang = ang
        self.lin = numpy.asarray(lin)
        if self.lin.shape != (2,):
            raise ValueError(&quot;lin must be a 2D vector&quot;)
        self._rot_matrix = None  # Lazy computation
        self._mat = None  # Lazy computation

    @staticmethod
    def identity():
        &quot;&quot;&quot;Create an identity pose (no rotation, no translation).&quot;&quot;&quot;
        return Pose2(ang=0.0, lin=numpy.array([0.0, 0.0]))

    def rotation_matrix(self):
        &quot;&quot;&quot;Get the 2x2 rotation matrix corresponding to the pose's orientation.&quot;&quot;&quot;
        if self._rot_matrix is None:
            c = math.cos(self.ang)
            s = math.sin(self.ang)
            self._rot_matrix = numpy.array([
                [c, -s],
                [s,  c]
            ])
        return self._rot_matrix

    def as_matrix(self):
        &quot;&quot;&quot;Get the 3x3 transformation matrix corresponding to the pose.&quot;&quot;&quot;
        if self._mat is None:
            R = self.rotation_matrix()
            t = self.lin
            self._mat = numpy.eye(3)
            self._mat[:2, :2] = R
            self._mat[:2, 2] = t
        return self._mat

    def inverse(self):
        &quot;&quot;&quot;Compute the inverse of the pose.&quot;&quot;&quot;
        inv_ang = -self.ang
        c = math.cos(inv_ang)
        s = math.sin(inv_ang)
        # Rotate translation by inverse rotation
        inv_lin = numpy.array([
            c * (-self.lin[0]) - s * (-self.lin[1]),
            s * (-self.lin[0]) + c * (-self.lin[1])
        ])
        return Pose2(inv_ang, inv_lin)

    def __repr__(self):
        return f&quot;Pose2(ang={self.ang}, lin={self.lin})&quot;

    def transform_point(self, point: numpy.ndarray) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Transform a 2D point using the pose.&quot;&quot;&quot;
        point = numpy.asarray(point)
        if point.shape != (2,):
            raise ValueError(&quot;point must be a 2D vector&quot;)
        R = self.rotation_matrix()
        return R @ point + self.lin

    def transform_vector(self, vector: numpy.ndarray) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Transform a 2D vector using the pose (ignoring translation).&quot;&quot;&quot;
        vector = numpy.asarray(vector)
        if vector.shape != (2,):
            raise ValueError(&quot;vector must be a 2D vector&quot;)
        R = self.rotation_matrix()
        return R @ vector

    def rotate_vector(self, vector: numpy.ndarray) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Rotate a 2D vector using the pose's rotation.&quot;&quot;&quot;
        vector = numpy.asarray(vector)
        if vector.shape != (2,):
            raise ValueError(&quot;vector must be a 2D vector&quot;)
        R = self.rotation_matrix()
        return R @ vector

    def inverse_transform_point(self, point: numpy.ndarray) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Transform a 2D point using the inverse of the pose.&quot;&quot;&quot;
        point = numpy.asarray(point)
        point = point.reshape(2)
        R = self.rotation_matrix()
        return R.T @ (point - self.lin)

    def inverse_rotate_vector(self, vector: numpy.ndarray) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Rotate a 2D vector using the inverse of the pose's rotation.&quot;&quot;&quot;
        vector = numpy.asarray(vector)
        if vector.shape != (2,):
            raise ValueError(&quot;vector must be a 2D vector&quot;)
        R = self.rotation_matrix()
        return R.T @ vector

    def inverse_transform_vector(self, vector: numpy.ndarray) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Transform a 2D vector using the inverse of the pose (ignoring translation).&quot;&quot;&quot;
        vector = numpy.asarray(vector)
        if vector.shape != (2,):
            raise ValueError(&quot;vector must be a 2D vector&quot;)
        R = self.rotation_matrix()
        return R.T @ vector

    def __mul__(self, other):
        &quot;&quot;&quot;Compose this pose with another pose.&quot;&quot;&quot;
        if not isinstance(other, Pose2):
            raise TypeError(&quot;Can only multiply Pose2 with Pose2&quot;)
        # Compose rotations: angles add
        new_ang = self.ang + other.ang
        # Compose translations: rotate other's translation and add to self's
        R = self.rotation_matrix()
        new_lin = self.lin + R @ other.lin
        return Pose2(ang=new_ang, lin=new_lin)

    def __matmul__(self, other):
        &quot;&quot;&quot;Compose this pose with another pose using @ operator.&quot;&quot;&quot;
        return self * other

    def compose(self, other: 'Pose2') -&gt; 'Pose2':
        &quot;&quot;&quot;Compose this pose with another pose.&quot;&quot;&quot;
        return self * other

    @staticmethod
    def rotation(angle: float):
        &quot;&quot;&quot;Create a rotation pose by a given angle.&quot;&quot;&quot;
        return Pose2(ang=angle, lin=numpy.array([0.0, 0.0]))

    @staticmethod
    def translation(x: float, y: float):
        &quot;&quot;&quot;Create a translation pose.&quot;&quot;&quot;
        return Pose2(ang=0.0, lin=numpy.array([x, y]))

    @staticmethod
    def move(dx: float, dy: float):
        &quot;&quot;&quot;Move the pose by given deltas in local coordinates.&quot;&quot;&quot;
        return Pose2.translation(dx, dy)

    @staticmethod
    def moveX(distance: float):
        &quot;&quot;&quot;Move along X axis.&quot;&quot;&quot;
        return Pose2.move(distance, 0.0)

    @staticmethod
    def moveY(distance: float):
        &quot;&quot;&quot;Move along Y axis.&quot;&quot;&quot;
        return Pose2.move(0.0, distance)

    @staticmethod
    def right(distance: float):
        &quot;&quot;&quot;Move right (along X axis).&quot;&quot;&quot;
        return Pose2.move(distance, 0.0)

    @staticmethod
    def forward(distance: float):
        &quot;&quot;&quot;Move forward (along Y axis).&quot;&quot;&quot;
        return Pose2.move(0.0, distance)

    @staticmethod
    def lerp(pose1: 'Pose2', pose2: 'Pose2', t: float) -&gt; 'Pose2':
        &quot;&quot;&quot;Linearly interpolate between two poses.&quot;&quot;&quot;
        lerped_ang = (1 - t) * pose1.ang + t * pose2.ang
        lerped_lin = (1 - t) * pose1.lin + t * pose2.lin
        return Pose2(ang=lerped_ang, lin=lerped_lin)

    def normalize_angle(self):
        &quot;&quot;&quot;Normalize the angle to [-π, π].&quot;&quot;&quot;
        self.ang = math.atan2(math.sin(self.ang), math.cos(self.ang))
        self._rot_matrix = None
        self._mat = None

    @property
    def x(self):
        &quot;&quot;&quot;Get X coordinate of translation.&quot;&quot;&quot;
        return self.lin[0]

    @property
    def y(self):
        &quot;&quot;&quot;Get Y coordinate of translation.&quot;&quot;&quot;
        return self.lin[1]

    @x.setter
    def x(self, value: float):
        &quot;&quot;&quot;Set X coordinate of translation.&quot;&quot;&quot;
        self.lin[0] = value
        self._mat = None

    @y.setter
    def y(self, value: float):
        &quot;&quot;&quot;Set Y coordinate of translation.&quot;&quot;&quot;
        self.lin[1] = value
        self._mat = None

</code></pre>
</body>
</html>
