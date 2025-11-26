<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/geombase/pose3.py</title>
</head>
<body>
<pre><code>
import math
import numpy
import numpy as np
from termin.util import qmul, qrot, qslerp, qinv

class Pose3:
    &quot;&quot;&quot;A 3D Pose represented by rotation quaternion and translation vector.&quot;&quot;&quot;

    def __init__(self, ang: numpy.ndarray = None, lin: numpy.ndarray = None):
        if ang is None:
            ang = numpy.array([0.0, 0.0, 0.0, 1.0])
        if lin is None:
            lin = numpy.array([0.0, 0.0, 0.0])
        self._ang = ang
        self._lin = lin
        self._rot_matrix = None  # Lazy computation
        self._mat = None  # Lazy computation
        self._mat34 = None  # Lazy computation

    @property
    def ang(self) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Get the rotation quaternion.&quot;&quot;&quot;
        return self._ang

    @property
    def lin(self) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Get the translation vector.&quot;&quot;&quot;
        return self._lin

    @staticmethod
    def identity():
        return Pose3(
            ang=numpy.array([0.0, 0.0, 0.0, 1.0]),
            lin=numpy.array([0.0, 0.0, 0.0])
        )

    def rotation_matrix(self):
        &quot;&quot;&quot;Get the 3x3 rotation matrix corresponding to the pose's orientation.&quot;&quot;&quot;
        if self._rot_matrix is None:
            x, y, z, w = self.ang
            self._rot_matrix = numpy.array([
                [1 - 2*(y**2 + z**2), 2*(x*y - z*w), 2*(x*z + y*w)],
                [2*(x*y + z*w), 1 - 2*(x**2 + z**2), 2*(y*z - x*w)],
                [2*(x*z - y*w), 2*(y*z + x*w), 1 - 2*(x**2 + y**2)]
            ])
        return self._rot_matrix

    def as_matrix(self):
        &quot;&quot;&quot;Get the 4x4 transformation matrix corresponding to the pose.&quot;&quot;&quot;
        if self._mat is None:
            R = self.rotation_matrix()
            t = self.lin
            self._mat = numpy.eye(4)
            self._mat[:3, :3] = R
            self._mat[:3, 3] = t
        return self._mat

    def as_matrix34(self):
        &quot;&quot;&quot;Get the 3x4 transformation matrix corresponding to the pose.&quot;&quot;&quot;
        if self._mat34 is None:
            R = self.rotation_matrix()
            t = self.lin
            self._mat34 = numpy.zeros((3, 4))
            self._mat34[:, :3] = R
            self._mat34[:, 3] = t
        return self._mat34

    def inverse(self):
        &quot;&quot;&quot;Compute the inverse of the pose.&quot;&quot;&quot;
        x, y, z, w = self.ang
        tx, ty, tz = self.lin
        inv_ang = numpy.array([-x, -y, -z, w])
        inv_lin = qrot(inv_ang, -self.lin)
        return Pose3(inv_ang, inv_lin)

    def __repr__(self):
        return f&quot;Pose3(ang={self.ang}, lin={self.lin})&quot;

    def transform_point(self, point: numpy.ndarray) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Transform a 3D point using the pose.&quot;&quot;&quot;
        return qrot(self.ang, point) + self.lin

    def rotate_point(self, point: numpy.ndarray) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Rotate a 3D point using the pose (ignoring translation).&quot;&quot;&quot;
        return qrot(self.ang, point)

    def transform_vector(self, vector: numpy.ndarray) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Transform a 3D vector using the pose (ignoring translation).&quot;&quot;&quot;
        return qrot(self.ang, vector)

    def inverse_transform_point(self, pnt):
        return qrot(qinv(self.ang), pnt - self.lin)
    
    def inverse_transform_vector(self, vec):
        return qrot(qinv(self.ang), vec)

    def __mul__(self, other):
        &quot;&quot;&quot;Compose this pose with another pose.&quot;&quot;&quot;
        if not isinstance(other, Pose3):
            raise TypeError(&quot;Can only multiply Pose3 with Pose3&quot;)
        q = qmul(self.ang, other.ang)
        t = self.lin + qrot(self.ang, other.lin)
        return Pose3(ang=q, lin=t)

    def __matmul__(self, other):
        &quot;&quot;&quot;Compose this pose with another pose using @ operator.&quot;&quot;&quot;
        return self * other
    
    def compose(self, other: 'Pose3') -&gt; 'Pose3':
        &quot;&quot;&quot;Compose this pose with another pose.&quot;&quot;&quot;
        return self * other

    def with_rotation(self, ang: numpy.ndarray) -&gt; 'Pose3':
        &quot;&quot;&quot;Return a new Pose3 with the given rotation and the same translation.&quot;&quot;&quot;
        return Pose3(ang=ang, lin=self.lin)

    def with_translation(self, lin: numpy.ndarray) -&gt; 'Pose3':
        &quot;&quot;&quot;Return a new Pose3 with the given translation and the same rotation.&quot;&quot;&quot;
        return Pose3(ang=self.ang, lin=lin)

    @staticmethod
    def rotation(axis: numpy.ndarray, angle: float):
        &quot;&quot;&quot;Create a rotation pose around a given axis by a given angle.&quot;&quot;&quot;
        axis = axis / numpy.linalg.norm(axis)
        s = math.sin(angle / 2)
        c = math.cos(angle / 2)
        q = numpy.array([axis[0] * s, axis[1] * s, axis[2] * s, c])
        print(&quot;Rotation axis:&quot;, axis)
        print(&quot;Rotation angle (radians):&quot;, angle)
        print(&quot;Rotation sin(angle/2):&quot;, s)
        print(&quot;Rotation cos(angle/2):&quot;, c)
        print(&quot;Rotation quaternion:&quot;, q)
        return Pose3(ang=q, lin=numpy.array([0.0, 0.0, 0.0]))

    @staticmethod
    def translation(x: float, y: float, z: float):
        &quot;&quot;&quot;Create a translation pose.&quot;&quot;&quot;
        return Pose3(ang=numpy.array([0.0, 0.0, 0.0, 1.0]), lin=numpy.array([x, y, z]))

    @staticmethod
    def rotateX(angle: float):
        &quot;&quot;&quot;Create a rotation pose around the X axis.&quot;&quot;&quot;
        return Pose3.rotation(numpy.array([1.0, 0.0, 0.0]), angle)

    @staticmethod
    def rotateY(angle: float):
        &quot;&quot;&quot;Create a rotation pose around the Y axis.&quot;&quot;&quot;
        return Pose3.rotation(numpy.array([0.0, 1.0, 0.0]), angle)
    
    @staticmethod
    def rotateZ(angle: float):
        &quot;&quot;&quot;Create a rotation pose around the Z axis.&quot;&quot;&quot;
        return Pose3.rotation(numpy.array([0.0, 0.0, 1.0]), angle)

    @staticmethod
    def move(dx: float, dy: float, dz: float):
        &quot;&quot;&quot;Move the pose by given deltas in local coordinates.&quot;&quot;&quot;
        return Pose3.translation(dx, dy, dz)

    @staticmethod
    def moveX(distance: float):
        return Pose3.move(distance, 0.0, 0.0)
    
    @staticmethod
    def moveY(distance: float):
        return Pose3.move(0.0, distance, 0.0)

    @staticmethod
    def moveZ(distance: float):
        return Pose3.move(0.0, 0.0, distance)

    @staticmethod
    def right(distance: float):
        return Pose3.move(distance, 0.0, 0.0)

    @staticmethod
    def forward(distance: float):
        return Pose3.move(0.0, distance, 0.0)

    @staticmethod
    def up(distance: float):
        return Pose3.move(0.0, 0.0, distance)


    @staticmethod
    def lerp(pose1: 'Pose3', pose2: 'Pose3', t: float) -&gt; 'Pose3':
        &quot;&quot;&quot;Linearly interpolate between two poses.&quot;&quot;&quot;
        lerped_ang = qslerp(pose1.ang, pose2.ang, t)
        lerped_lin = (1 - t) * pose1.lin + t * pose2.lin
        return Pose3(ang=lerped_ang, lin=lerped_lin)

    # def normalize(self):
    #     &quot;&quot;&quot;Normalize the quaternion to unit length.&quot;&quot;&quot;
    #     norm = numpy.linalg.norm(self.ang)
    #     if norm &gt; 0:
    #         self.ang = self.ang / norm
    #         self._rot_matrix = None
    #         self._mat = None
    #         self._mat34 = None

    def normalized(self) -&gt; 'Pose3':
        &quot;&quot;&quot;Return a new Pose3 with normalized quaternion.&quot;&quot;&quot;
        norm = numpy.linalg.norm(self.ang)
        if norm &gt; 0:
            ang = self.ang / norm
        else:
            ang = self.ang
        return Pose3(ang=ang, lin=self.lin)

    def distance(self, other: 'Pose3') -&gt; float:
        &quot;&quot;&quot;Calculate Euclidean distance between the translation parts of two poses.&quot;&quot;&quot;
        return numpy.linalg.norm(self.lin - other.lin)

    def to_axis_angle(self):
        &quot;&quot;&quot;Convert quaternion to axis-angle representation.
        Returns: (axis, angle) where axis is a 3D unit vector and angle is in radians.
        &quot;&quot;&quot;
        x, y, z, w = self.ang
        angle = 2 * math.acos(numpy.clip(w, -1.0, 1.0))
        s = math.sqrt(1 - w*w)
        if s &lt; 0.001:  # If angle is close to 0
            axis = numpy.array([1.0, 0.0, 0.0])
        else:
            axis = numpy.array([x / s, y / s, z / s])
        return axis, angle

    @staticmethod
    def from_axis_angle(axis: numpy.ndarray, angle: float):
        &quot;&quot;&quot;Create a Pose3 from axis-angle representation.&quot;&quot;&quot;
        return Pose3.rotation(axis, angle)

    def to_euler(self, order: str = 'xyz'):
        &quot;&quot;&quot;Convert quaternion to Euler angles.
        Args:
            order: String specifying rotation order (e.g., 'xyz', 'zyx')
        Returns:
            numpy array of three angles in radians
        &quot;&quot;&quot;
        x, y, z, w = self.ang
        
        if order == 'xyz':
            # Roll (x-axis rotation)
            sinr_cosp = 2 * (w * x + y * z)
            cosr_cosp = 1 - 2 * (x * x + y * y)
            roll = math.atan2(sinr_cosp, cosr_cosp)
            
            # Pitch (y-axis rotation)
            sinp = 2 * (w * y - z * x)
            sinp = numpy.clip(sinp, -1.0, 1.0)
            pitch = math.asin(sinp)
            
            # Yaw (z-axis rotation)
            siny_cosp = 2 * (w * z + x * y)
            cosy_cosp = 1 - 2 * (y * y + z * z)
            yaw = math.atan2(siny_cosp, cosy_cosp)
            
            return numpy.array([roll, pitch, yaw])
        else:
            raise NotImplementedError(f&quot;Euler order '{order}' not implemented&quot;)

    @staticmethod
    def from_euler(roll: float, pitch: float, yaw: float, order: str = 'xyz'):
        &quot;&quot;&quot;Create a Pose3 from Euler angles.
        Args:
            roll, pitch, yaw: Rotation angles in radians
            order: String specifying rotation order (default: 'xyz')
        &quot;&quot;&quot;
        if order == 'xyz':
            # Compute half angles
            cr = math.cos(roll * 0.5)
            sr = math.sin(roll * 0.5)
            cp = math.cos(pitch * 0.5)
            sp = math.sin(pitch * 0.5)
            cy = math.cos(yaw * 0.5)
            sy = math.sin(yaw * 0.5)
            
            # Compute quaternion
            qx = sr * cp * cy - cr * sp * sy
            qy = cr * sp * cy + sr * cp * sy
            qz = cr * cp * sy - sr * sp * cy
            qw = cr * cp * cy + sr * sp * sy
            
            return Pose3(ang=numpy.array([qx, qy, qz, qw]), lin=numpy.array([0.0, 0.0, 0.0]))
        else:
            raise NotImplementedError(f&quot;Euler order '{order}' not implemented&quot;)

    @staticmethod
    def looking_at(eye: numpy.ndarray, target: numpy.ndarray, up: numpy.ndarray = numpy.array([0.0, 0.0, 1.0])):
        &quot;&quot;&quot;Create a pose at 'eye' position looking towards 'target'.
        Args:
            eye: Position of the pose
            target: Point to look at
            up: Up vector (default: z-axis)
        &quot;&quot;&quot;
        forward = target - eye
        forward = forward / numpy.linalg.norm(forward)
        
        right = numpy.cross(forward, up)
        right = right / numpy.linalg.norm(right)
        
        up_corrected = numpy.cross(right, forward)
        
        # Build rotation matrix
        rot_mat = numpy.column_stack([right, up_corrected, -forward])
        
        # Convert rotation matrix to quaternion
        trace = numpy.trace(rot_mat)
        if trace &gt; 0:
            s = 0.5 / math.sqrt(trace + 1.0)
            qw = 0.25 / s
            qx = (rot_mat[2, 1] - rot_mat[1, 2]) * s
            qy = (rot_mat[0, 2] - rot_mat[2, 0]) * s
            qz = (rot_mat[1, 0] - rot_mat[0, 1]) * s
        else:
            if rot_mat[0, 0] &gt; rot_mat[1, 1] and rot_mat[0, 0] &gt; rot_mat[2, 2]:
                s = 2.0 * math.sqrt(1.0 + rot_mat[0, 0] - rot_mat[1, 1] - rot_mat[2, 2])
                qw = (rot_mat[2, 1] - rot_mat[1, 2]) / s
                qx = 0.25 * s
                qy = (rot_mat[0, 1] + rot_mat[1, 0]) / s
                qz = (rot_mat[0, 2] + rot_mat[2, 0]) / s
            elif rot_mat[1, 1] &gt; rot_mat[2, 2]:
                s = 2.0 * math.sqrt(1.0 + rot_mat[1, 1] - rot_mat[0, 0] - rot_mat[2, 2])
                qw = (rot_mat[0, 2] - rot_mat[2, 0]) / s
                qx = (rot_mat[0, 1] + rot_mat[1, 0]) / s
                qy = 0.25 * s
                qz = (rot_mat[1, 2] + rot_mat[2, 1]) / s
            else:
                s = 2.0 * math.sqrt(1.0 + rot_mat[2, 2] - rot_mat[0, 0] - rot_mat[1, 1])
                qw = (rot_mat[1, 0] - rot_mat[0, 1]) / s
                qx = (rot_mat[0, 2] + rot_mat[2, 0]) / s
                qy = (rot_mat[1, 2] + rot_mat[2, 1]) / s
                qz = 0.25 * s
        
        return Pose3(ang=numpy.array([qx, qy, qz, qw]), lin=eye)

    @property
    def x(self):
        &quot;&quot;&quot;Get X coordinate of translation.&quot;&quot;&quot;
        return self.lin[0]

    @property
    def y(self):
        &quot;&quot;&quot;Get Y coordinate of translation.&quot;&quot;&quot;
        return self.lin[1]

    @property
    def z(self):
        &quot;&quot;&quot;Get Z coordinate of translation.&quot;&quot;&quot;
        return self.lin[2]

    @x.setter
    def x(self, value: float):
        &quot;&quot;&quot;Set X coordinate of translation.&quot;&quot;&quot;
        self.lin[0] = value
        self._mat = None
        self._mat34 = None

    @y.setter
    def y(self, value: float):
        &quot;&quot;&quot;Set Y coordinate of translation.&quot;&quot;&quot;
        self.lin[1] = value
        self._mat = None
        self._mat34 = None

    @z.setter
    def z(self, value: float):
        &quot;&quot;&quot;Set Z coordinate of translation.&quot;&quot;&quot;
        self.lin[2] = value
        self._mat = None
        self._mat34 = None

    @staticmethod
    def from_vector_vw_order(vec: numpy.ndarray) -&gt; 'Pose3':
        &quot;&quot;&quot;Create Pose3 from a 7D vector in (vx, vy, vz, wx, wy, wz, w) order.&quot;&quot;&quot;
        if vec.shape != (7,):
            raise ValueError(&quot;Input vector must be of shape (7,)&quot;)
        ang = vec[3:7]
        lin = vec[0:3]
        return Pose3(ang=ang, lin=lin)

    def to_vector_vw_order(self) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Convert Pose3 to a 7D vector in (vx, vy, vz, wx, wy, wz, w) order.&quot;&quot;&quot;
        vec = numpy.zeros(7)
        vec[0:3] = self.lin
        vec[3:7] = self.ang
        return vec

    def rotate_vector(self, vec: numpy.ndarray) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Rotate a 3D vector using the pose's rotation.&quot;&quot;&quot;
        return qrot(self.ang, vec)
</code></pre>
</body>
</html>
