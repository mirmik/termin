import numpy
from termin.ga201.motor import Motor2


class PoseObject:
    def __init__(self, pose=Motor2()):
        self._position = pose

    def position(self):
        return self._position

    def update_position(self, pose):
        self._position = pose


class ReferencedPoseObject:
    def __init__(self, pose=Motor2(), parent=None):
        self._pose_in_frame = pose
        self._parent = parent

    def position(self):
        return self._parent.position() * self._pose_in_frame

    def relative_position(self):
        return self._pose_in_frame

    def parent(self):
        return self._parent