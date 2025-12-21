from termin.geombase import Pose3, GeneralPose3
from termin.colliders.collider import Collider
from termin.kinematic import Transform3
import numpy

class AttachedCollider:
    """A collider attached to a Transform3 with a local pose."""
    def __init__(self, collider: Collider, transform: 'Transform3', local_pose: Pose3 = Pose3.identity()):
        self._transform = transform
        self._local_pose = local_pose
        self._collider = collider

    def transformed_collider(self) -> Collider:
        """Get the collider in world coordinates."""
        global_pose = self._transform.global_pose()
        local_pose = self._local_pose

        # Extract scale from GeneralPose3 before converting to Pose3
        scale = None
        if isinstance(global_pose, GeneralPose3):
            scale = global_pose.scale
            global_pose = global_pose.to_pose3()
        if isinstance(local_pose, GeneralPose3):
            local_pose = local_pose.to_pose3()

        world_transform = global_pose * local_pose
        wcol = self._collider.transform_by(world_transform)

        # Apply scale if present
        if scale is not None and hasattr(wcol, 'scale_by'):
            wcol = wcol.scale_by(scale)

        return wcol

    def local_pose(self) -> Pose3:
        """Get the local pose of the collider."""
        return self._local_pose

    def transform(self) -> 'Transform3':
        """Get the Transform3 to which this collider is attached."""
        return self._transform

    def distance(self, other: "AttachedCollider") -> float:
        """Return the distance between this attached collider and another attached collider."""
        return self.transformed_collider().distance(other.transformed_collider())
 
    def closest_to_ray(self, ray: "Ray3"):
        """
        Делегируем вычисление трансформированному коллайдеру.
        """
        return self.transformed_collider().closest_to_ray(ray)
    
    def closest_to_collider(self, other: "AttachedCollider"):
        """Return the closest points and distance between this attached collider and another attached collider."""
        return self.transformed_collider().closest_to_collider(other.transformed_collider())

    def avoidance(self, other: "AttachedCollider") -> numpy.ndarray:
        """Compute an avoidance vector to maintain a minimum distance from another attached collider."""
        return self.transformed_collider().avoidance(other.transformed_collider())
