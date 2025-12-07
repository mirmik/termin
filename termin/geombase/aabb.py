
import numpy 
from weakref import WeakKeyDictionary
from termin.geomalgo.project import project_point_on_aabb, project_segment_on_aabb

class AABB:
    """Axis-Aligned Bounding Box in 3D space."""

    __slots__ = ('min_point', 'max_point')

    def __init__(self, min_point: numpy.ndarray, max_point: numpy.ndarray):
        self.min_point = min_point
        self.max_point = max_point

    def extend(self, point: numpy.ndarray):
        """Extend the AABB to include the given point."""
        self.min_point = numpy.minimum(self.min_point, point)
        self.max_point = numpy.maximum(self.max_point, point)

    def intersects(self, other: "AABB") -> bool:
        """Check if this AABB intersects with another AABB."""
        return numpy.all(self.max_point >= other.min_point) and numpy.all(other.max_point >= self.min_point)

    def __repr__(self):
        return f"AABB(min_point={self.min_point}, max_point={self.max_point})"

    @staticmethod
    def from_points(points: numpy.ndarray) -> "AABB":
        """Create an AABB that encompasses a set of points."""
        min_point = numpy.min(points, axis=0)
        max_point = numpy.max(points, axis=0)
        return AABB(min_point, max_point)

    def merge(self, other: "AABB") -> "AABB":
        """Merge this AABB with another AABB and return the resulting AABB."""
        new_min = numpy.minimum(self.min_point, other.min_point)
        new_max = numpy.maximum(self.max_point, other.max_point)
        return AABB(new_min, new_max)

    def get_corners_homogeneous(self) -> numpy.ndarray:
        """Get the 8 corners of the AABB in homogeneous coordinates."""
        corners = numpy.array([
            [self.min_point[0], self.min_point[1], self.min_point[2], 1.0],
            [self.min_point[0], self.min_point[1], self.max_point[2], 1.0], 
            [self.min_point[0], self.max_point[1], self.min_point[2], 1.0],
            [self.min_point[0], self.max_point[1], self.max_point[2], 1.0],
            [self.max_point[0], self.min_point[1], self.min_point[2], 1.0],
            [self.max_point[0], self.min_point[1], self.max_point[2], 1.0],
            [self.max_point[0], self.max_point[1], self.min_point[2], 1.0],
            [self.max_point[0], self.max_point[1], self.max_point[2], 1.0],
        ])
        return corners
    
    def project_point(self, point: numpy.ndarray) -> numpy.ndarray:
        """Project a point onto the AABB is performed with clamping."""
        return numpy.minimum(numpy.maximum(point, self.min_point), self.max_point)
    
    def project_segment_on_aabb(self, seg_start: numpy.ndarray, seg_end: numpy.ndarray):
        """Project a segment onto the AABB and return the closest points and distance."""
        return project_segment_on_aabb(seg_start, seg_end, self.min_point, self.max_point)
        
                                

class TransformAABB:
    """AABB associated with a Transform."""
    transform_to_taabb_map = WeakKeyDictionary()

    __slots__ = ('_transform', '_my_aabb', '_my_world_aabb', '_compiled_aabb',
                 '_last_inspected_version', '_last_tree_inspected_version')

    def __init__(self, transform: 'Transform', aabb: AABB):
        self._transform = transform
        self._my_aabb = aabb
        self._my_world_aabb = None
        self._compiled_aabb = None
        self._last_inspected_version = -1
        self._last_tree_inspected_version = -1
        TransformAABB.transform_to_taabb_map[transform] = self

    def compile_tree_aabb(self) -> AABB:
        if self._last_tree_inspected_version == self._transform._version_for_walking_to_distal:
            return self._compiled_aabb
        result = self.get_world_aabb()
        for child in self._transform.children:
            child_taabb = TransformAABB.transform_to_taabb_map.get(child)
            if child_taabb:
                child_aabb = child_taabb.compile_tree_aabb()
                result = result.merge(child_aabb)
        self._compiled_aabb = result
        self._last_tree_inspected_version = self._transform._version_for_walking_to_distal
        return self._compiled_aabb

    def get_world_aabb(self) -> AABB:
        """Get the AABB widened by the rotation of the transform."""
        if self._last_inspected_version == self._transform._version_only_my:
            return self._my_world_aabb
        matrix = self._transform.global_pose().as_matrix34()
        corners = self._my_aabb.get_corners_homogeneous()
        transformed_corners = numpy.dot(matrix, corners.T).T
        new_aabb = AABB.from_points(transformed_corners)
        self._my_world_aabb = new_aabb
        return new_aabb