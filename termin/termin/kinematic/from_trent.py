from .transform import Transform3
from .kinematic import KinematicTransform3OneScrew, Rotator3, Actuator3
from termin.geombase import Pose3, Screw3
import numpy

def from_trent(dct: dict) -> Transform3:
    """Create a Transform3 or KinematicTransform3 from a Trent dictionary representation."""
    ttype = dct.get("type", "transform")
    local_pose_dict = dct.get("pose", {})
    position = numpy.array(local_pose_dict.get("position", [0.0, 0.0, 0.0]))
    orientation = numpy.array(local_pose_dict.get("orientation", [0.0, 0.0, 0.0, 1.0]))
    local_pose = Pose3(lin=position, ang=orientation)
    name = dct.get("name", "")
    
    if ttype == "transform":
        transform = Transform3(local_pose=local_pose, name=name)
    elif ttype == "rotator":
        axis = numpy.array(dct.get("axis", [0.0, 0.0, 1.0]))
        transform = Rotator3(axis=axis, parent=None, name=name, local_pose=local_pose, manual_output=True)
    elif ttype == "actuator":
        axis = numpy.array(dct.get("axis", [0.0, 0.0, 1.0]))
        transform = Actuator3(axis=axis, parent=None, name=name, local_pose=local_pose, manual_output=True)
    else:
        raise ValueError(f"Unknown transform type: {ttype}")
    
    for child_dct in dct.get("children", []):
        child_transform = from_trent(child_dct)
        transform.add_child(child_transform)
    
    return transform