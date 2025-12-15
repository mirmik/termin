"""GeneralPose3 - 3D pose with scale for visualization hierarchy.

This is a standalone class parallel to Pose3, designed for use in visualization
where scale inheritance matters. It is NOT a wrapper around Pose3.

Composition formula:
    parent * child:
        new_lin = parent.lin + qrot(parent.ang, parent.scale * child.lin)
        new_ang = qmul(parent.ang, child.ang)
        new_scale = parent.scale * child.scale  # element-wise
"""

import math
import numpy
import numpy as np
from termin.util import qmul, qrot, qslerp, qinv


class GeneralPose3:
    """A 3D Pose with scale, represented by rotation quaternion, translation vector, and scale."""

    __slots__ = ('ang', 'lin', 'scale', '_rot_matrix', '_mat', '_mat34')

    def __init__(
        self,
        ang: numpy.ndarray = None,
        lin: numpy.ndarray = None,
        scale: numpy.ndarray = None
    ):
        if ang is None:
            ang = numpy.array([0.0, 0.0, 0.0, 1.0])
        if lin is None:
            lin = numpy.array([0.0, 0.0, 0.0])
        if scale is None:
            scale = numpy.array([1.0, 1.0, 1.0])
        self.ang = ang
        self.lin = lin
        self.scale = scale
        self._rot_matrix = None
        self._mat = None
        self._mat34 = None

    def copy(self) -> 'GeneralPose3':
        """Create a copy of the GeneralPose3."""
        return GeneralPose3(
            ang=self.ang.copy(),
            lin=self.lin.copy(),
            scale=self.scale.copy()
        )

    @staticmethod
    def identity() -> 'GeneralPose3':
        return GeneralPose3(
            ang=numpy.array([0.0, 0.0, 0.0, 1.0]),
            lin=numpy.array([0.0, 0.0, 0.0]),
            scale=numpy.array([1.0, 1.0, 1.0])
        )

    def rotation_matrix(self) -> numpy.ndarray:
        """Get the 3x3 rotation matrix corresponding to the pose's orientation."""
        if self._rot_matrix is None:
            x, y, z, w = self.ang
            self._rot_matrix = numpy.array([
                [1 - 2*(y**2 + z**2), 2*(x*y - z*w), 2*(x*z + y*w)],
                [2*(x*y + z*w), 1 - 2*(x**2 + z**2), 2*(y*z - x*w)],
                [2*(x*z - y*w), 2*(y*z + x*w), 1 - 2*(x**2 + y**2)]
            ])
        return self._rot_matrix

    def as_matrix(self) -> numpy.ndarray:
        """Get the 4x4 transformation matrix with scale baked in.

        Returns TRS matrix: Translation * Rotation * Scale
        """
        if self._mat is None:
            R = self.rotation_matrix()
            S = numpy.diag(self.scale)
            RS = R @ S
            self._mat = numpy.eye(4)
            self._mat[:3, :3] = RS
            self._mat[:3, 3] = self.lin
        return self._mat

    def as_matrix34(self) -> numpy.ndarray:
        """Get the 3x4 transformation matrix with scale baked in."""
        if self._mat34 is None:
            R = self.rotation_matrix()
            S = numpy.diag(self.scale)
            RS = R @ S
            self._mat34 = numpy.zeros((3, 4))
            self._mat34[:, :3] = RS
            self._mat34[:, 3] = self.lin
        return self._mat34

    def inverse(self) -> 'GeneralPose3':
        """Compute the inverse of the pose.

        For pose P = TRS, inverse is S^-1 R^-1 T^-1
        """
        inv_scale = 1.0 / self.scale
        x, y, z, w = self.ang
        inv_ang = numpy.array([-x, -y, -z, w])
        # inv_lin = R^-1 * (-T) / S = qrot(inv_ang, -lin) * inv_scale
        inv_lin = qrot(inv_ang, -self.lin) * inv_scale
        return GeneralPose3(ang=inv_ang, lin=inv_lin, scale=inv_scale)

    def __repr__(self):
        return f"GeneralPose3(ang={self.ang}, lin={self.lin}, scale={self.scale})"

    def transform_point(self, point: numpy.ndarray) -> numpy.ndarray:
        """Transform a 3D point using the pose (with scale)."""
        return qrot(self.ang, self.scale * point) + self.lin

    def rotate_point(self, point: numpy.ndarray) -> numpy.ndarray:
        """Rotate a 3D point using the pose (ignoring translation, but applying scale)."""
        return qrot(self.ang, self.scale * point)

    def transform_vector(self, vector: numpy.ndarray) -> numpy.ndarray:
        """Transform a 3D vector using the pose (with scale, ignoring translation)."""
        return qrot(self.ang, self.scale * vector)

    def inverse_transform_point(self, pnt: numpy.ndarray) -> numpy.ndarray:
        inv_scale = 1.0 / self.scale
        return qrot(qinv(self.ang), pnt - self.lin) * inv_scale

    def inverse_transform_vector(self, vec: numpy.ndarray) -> numpy.ndarray:
        inv_scale = 1.0 / self.scale
        return qrot(qinv(self.ang), vec) * inv_scale

    def __mul__(self, other: 'GeneralPose3') -> 'GeneralPose3':
        """Compose this pose with another pose.

        Composition formula:
            new_lin = parent.lin + qrot(parent.ang, parent.scale * child.lin)
            new_ang = qmul(parent.ang, child.ang)
            new_scale = parent.scale * child.scale
        """
        if not isinstance(other, GeneralPose3):
            raise TypeError("Can only multiply GeneralPose3 with GeneralPose3")
        q = qmul(self.ang, other.ang)
        t = self.lin + qrot(self.ang, self.scale * other.lin)
        s = self.scale * other.scale
        return GeneralPose3(ang=q, lin=t, scale=s)

    def __matmul__(self, other: 'GeneralPose3') -> 'GeneralPose3':
        """Compose this pose with another pose using @ operator."""
        return self * other

    def compose(self, other: 'GeneralPose3') -> 'GeneralPose3':
        """Compose this pose with another pose."""
        return self * other

    def with_rotation(self, ang: numpy.ndarray) -> 'GeneralPose3':
        """Return a new GeneralPose3 with the given rotation."""
        return GeneralPose3(ang=ang, lin=self.lin.copy(), scale=self.scale.copy())

    def with_translation(self, lin: numpy.ndarray) -> 'GeneralPose3':
        """Return a new GeneralPose3 with the given translation."""
        return GeneralPose3(ang=self.ang.copy(), lin=lin, scale=self.scale.copy())

    def with_scale(self, scale: numpy.ndarray) -> 'GeneralPose3':
        """Return a new GeneralPose3 with the given scale."""
        return GeneralPose3(ang=self.ang.copy(), lin=self.lin.copy(), scale=scale)

    # --- Conversion to Pose3 ---

    def to_pose3(self) -> 'Pose3':
        """Convert to Pose3 by dropping scale.

        Use this at physics/visualization boundary.
        """
        from .pose3 import Pose3
        return Pose3(ang=self.ang.copy(), lin=self.lin.copy())

    # --- Factory methods ---

    @staticmethod
    def rotation(axis: numpy.ndarray, angle: float) -> 'GeneralPose3':
        """Create a rotation pose around a given axis by a given angle."""
        axis = axis / numpy.linalg.norm(axis)
        s = math.sin(angle / 2)
        c = math.cos(angle / 2)
        q = numpy.array([axis[0] * s, axis[1] * s, axis[2] * s, c])
        return GeneralPose3(ang=q)

    @staticmethod
    def translation(x: float, y: float, z: float) -> 'GeneralPose3':
        """Create a translation pose."""
        return GeneralPose3(lin=numpy.array([x, y, z]))

    @staticmethod
    def scaling(sx: float, sy: float = None, sz: float = None) -> 'GeneralPose3':
        """Create a scale-only pose.

        If only sx is given, uniform scale is applied.
        """
        if sy is None:
            sy = sx
        if sz is None:
            sz = sx
        return GeneralPose3(scale=numpy.array([sx, sy, sz]))

    @staticmethod
    def rotateX(angle: float) -> 'GeneralPose3':
        """Create a rotation pose around the X axis."""
        return GeneralPose3.rotation(numpy.array([1.0, 0.0, 0.0]), angle)

    @staticmethod
    def rotateY(angle: float) -> 'GeneralPose3':
        """Create a rotation pose around the Y axis."""
        return GeneralPose3.rotation(numpy.array([0.0, 1.0, 0.0]), angle)

    @staticmethod
    def rotateZ(angle: float) -> 'GeneralPose3':
        """Create a rotation pose around the Z axis."""
        return GeneralPose3.rotation(numpy.array([0.0, 0.0, 1.0]), angle)

    @staticmethod
    def move(dx: float, dy: float, dz: float) -> 'GeneralPose3':
        """Move the pose by given deltas in local coordinates."""
        return GeneralPose3.translation(dx, dy, dz)

    @staticmethod
    def moveX(distance: float) -> 'GeneralPose3':
        return GeneralPose3.move(distance, 0.0, 0.0)

    @staticmethod
    def moveY(distance: float) -> 'GeneralPose3':
        return GeneralPose3.move(0.0, distance, 0.0)

    @staticmethod
    def moveZ(distance: float) -> 'GeneralPose3':
        return GeneralPose3.move(0.0, 0.0, distance)

    @staticmethod
    def right(distance: float) -> 'GeneralPose3':
        return GeneralPose3.move(distance, 0.0, 0.0)

    @staticmethod
    def forward(distance: float) -> 'GeneralPose3':
        return GeneralPose3.move(0.0, distance, 0.0)

    @staticmethod
    def up(distance: float) -> 'GeneralPose3':
        return GeneralPose3.move(0.0, 0.0, distance)

    @staticmethod
    def lerp(gp1: 'GeneralPose3', gp2: 'GeneralPose3', t: float) -> 'GeneralPose3':
        """Linearly interpolate between two poses."""
        lerped_ang = qslerp(gp1.ang, gp2.ang, t)
        lerped_lin = (1 - t) * gp1.lin + t * gp2.lin
        lerped_scale = (1 - t) * gp1.scale + t * gp2.scale
        return GeneralPose3(ang=lerped_ang, lin=lerped_lin, scale=lerped_scale)

    def normalized(self) -> 'GeneralPose3':
        """Return a new GeneralPose3 with normalized quaternion."""
        norm = numpy.linalg.norm(self.ang)
        if norm > 0:
            ang = self.ang / norm
        else:
            ang = self.ang
        return GeneralPose3(ang=ang, lin=self.lin.copy(), scale=self.scale.copy())

    def distance(self, other: 'GeneralPose3') -> float:
        """Calculate Euclidean distance between the translation parts of two poses."""
        return numpy.linalg.norm(self.lin - other.lin)

    def to_axis_angle(self):
        """Convert quaternion to axis-angle representation."""
        x, y, z, w = self.ang
        angle = 2 * math.acos(numpy.clip(w, -1.0, 1.0))
        s = math.sqrt(1 - w*w)
        if s < 0.001:
            axis = numpy.array([1.0, 0.0, 0.0])
        else:
            axis = numpy.array([x / s, y / s, z / s])
        return axis, angle

    @staticmethod
    def from_axis_angle(axis: numpy.ndarray, angle: float) -> 'GeneralPose3':
        """Create a GeneralPose3 from axis-angle representation."""
        return GeneralPose3.rotation(axis, angle)

    def to_euler(self, order: str = 'xyz'):
        """Convert quaternion to Euler angles."""
        x, y, z, w = self.ang

        if order == 'xyz':
            sinr_cosp = 2 * (w * x + y * z)
            cosr_cosp = 1 - 2 * (x * x + y * y)
            roll = math.atan2(sinr_cosp, cosr_cosp)

            sinp = 2 * (w * y - z * x)
            sinp = numpy.clip(sinp, -1.0, 1.0)
            pitch = math.asin(sinp)

            siny_cosp = 2 * (w * z + x * y)
            cosy_cosp = 1 - 2 * (y * y + z * z)
            yaw = math.atan2(siny_cosp, cosy_cosp)

            return numpy.array([roll, pitch, yaw])
        else:
            raise NotImplementedError(f"Euler order '{order}' not implemented")

    @staticmethod
    def from_euler(
        roll: float, pitch: float, yaw: float, order: str = 'xyz'
    ) -> 'GeneralPose3':
        """Create a GeneralPose3 from Euler angles."""
        if order == 'xyz':
            cr = math.cos(roll * 0.5)
            sr = math.sin(roll * 0.5)
            cp = math.cos(pitch * 0.5)
            sp = math.sin(pitch * 0.5)
            cy = math.cos(yaw * 0.5)
            sy = math.sin(yaw * 0.5)

            qx = sr * cp * cy - cr * sp * sy
            qy = cr * sp * cy + sr * cp * sy
            qz = cr * cp * sy - sr * sp * cy
            qw = cr * cp * cy + sr * sp * sy

            return GeneralPose3(ang=numpy.array([qx, qy, qz, qw]))
        else:
            raise NotImplementedError(f"Euler order '{order}' not implemented")

    @staticmethod
    def looking_at(
        eye: numpy.ndarray,
        target: numpy.ndarray,
        up: numpy.ndarray = None
    ) -> 'GeneralPose3':
        """Create a pose at 'eye' position looking towards 'target'.

        Uses Y-forward convention:
        - Local +X = right
        - Local +Y = forward (direction to target)
        - Local +Z = up
        """
        if up is None:
            up = numpy.array([0.0, 0.0, 1.0])

        forward = target - eye
        forward = forward / numpy.linalg.norm(forward)

        right = numpy.cross(forward, up)
        right = right / numpy.linalg.norm(right)

        up_corrected = numpy.cross(right, forward)

        rot_mat = numpy.column_stack([right, forward, up_corrected])

        trace = numpy.trace(rot_mat)
        if trace > 0:
            s = 0.5 / math.sqrt(trace + 1.0)
            qw = 0.25 / s
            qx = (rot_mat[2, 1] - rot_mat[1, 2]) * s
            qy = (rot_mat[0, 2] - rot_mat[2, 0]) * s
            qz = (rot_mat[1, 0] - rot_mat[0, 1]) * s
        else:
            if rot_mat[0, 0] > rot_mat[1, 1] and rot_mat[0, 0] > rot_mat[2, 2]:
                s = 2.0 * math.sqrt(1.0 + rot_mat[0, 0] - rot_mat[1, 1] - rot_mat[2, 2])
                qw = (rot_mat[2, 1] - rot_mat[1, 2]) / s
                qx = 0.25 * s
                qy = (rot_mat[0, 1] + rot_mat[1, 0]) / s
                qz = (rot_mat[0, 2] + rot_mat[2, 0]) / s
            elif rot_mat[1, 1] > rot_mat[2, 2]:
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

        return GeneralPose3(ang=numpy.array([qx, qy, qz, qw]), lin=eye.copy())

    @staticmethod
    def from_matrix(matrix: numpy.ndarray) -> 'GeneralPose3':
        """Create GeneralPose3 from a 4x4 or 3x4 transformation matrix.

        Extracts translation, rotation (quaternion), and scale from the matrix.
        """
        if matrix.shape == (3, 4):
            mat = numpy.eye(4)
            mat[:3, :] = matrix
            matrix = mat

        # Extract translation
        lin = matrix[:3, 3].copy()

        # Extract scale from column norms
        sx = numpy.linalg.norm(matrix[:3, 0])
        sy = numpy.linalg.norm(matrix[:3, 1])
        sz = numpy.linalg.norm(matrix[:3, 2])
        scale = numpy.array([sx, sy, sz])

        # Extract rotation matrix (normalized)
        rot_mat = numpy.zeros((3, 3))
        rot_mat[:, 0] = matrix[:3, 0] / sx if sx > 1e-8 else matrix[:3, 0]
        rot_mat[:, 1] = matrix[:3, 1] / sy if sy > 1e-8 else matrix[:3, 1]
        rot_mat[:, 2] = matrix[:3, 2] / sz if sz > 1e-8 else matrix[:3, 2]

        # Convert rotation matrix to quaternion
        trace = numpy.trace(rot_mat)
        if trace > 0:
            s = 0.5 / math.sqrt(trace + 1.0)
            qw = 0.25 / s
            qx = (rot_mat[2, 1] - rot_mat[1, 2]) * s
            qy = (rot_mat[0, 2] - rot_mat[2, 0]) * s
            qz = (rot_mat[1, 0] - rot_mat[0, 1]) * s
        else:
            if rot_mat[0, 0] > rot_mat[1, 1] and rot_mat[0, 0] > rot_mat[2, 2]:
                s = 2.0 * math.sqrt(1.0 + rot_mat[0, 0] - rot_mat[1, 1] - rot_mat[2, 2])
                qw = (rot_mat[2, 1] - rot_mat[1, 2]) / s
                qx = 0.25 * s
                qy = (rot_mat[0, 1] + rot_mat[1, 0]) / s
                qz = (rot_mat[0, 2] + rot_mat[2, 0]) / s
            elif rot_mat[1, 1] > rot_mat[2, 2]:
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

        return GeneralPose3(
            ang=numpy.array([qx, qy, qz, qw]),
            lin=lin,
            scale=scale
        )

    # --- Properties ---

    @property
    def x(self) -> float:
        """Get X coordinate of translation."""
        return self.lin[0]

    @property
    def y(self) -> float:
        """Get Y coordinate of translation."""
        return self.lin[1]

    @property
    def z(self) -> float:
        """Get Z coordinate of translation."""
        return self.lin[2]

    @x.setter
    def x(self, value: float):
        """Set X coordinate of translation."""
        self.lin[0] = value
        self._mat = None
        self._mat34 = None

    @y.setter
    def y(self, value: float):
        """Set Y coordinate of translation."""
        self.lin[1] = value
        self._mat = None
        self._mat34 = None

    @z.setter
    def z(self, value: float):
        """Set Z coordinate of translation."""
        self.lin[2] = value
        self._mat = None
        self._mat34 = None

    def rotate_vector(self, vec: numpy.ndarray) -> numpy.ndarray:
        """Rotate a 3D vector using the pose's rotation (with scale)."""
        return qrot(self.ang, self.scale * vec)

    def invalidate_cache(self):
        """Invalidate cached matrices. Call after modifying ang, lin, or scale directly."""
        self._rot_matrix = None
        self._mat = None
        self._mat34 = None
