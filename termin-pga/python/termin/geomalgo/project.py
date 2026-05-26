import math
from tracemalloc import start
import numpy as np

def project_point_on_plane(point, plane_point, plane_normal):
    """
    Projects a point onto a plane defined by a point and a normal vector.

    Parameters:
    point (np.array): The 3D point to be projected (shape: (3,)).
    plane_point (np.array): A point on the plane (shape: (3,)).
    plane_normal (np.array): The normal vector of the plane (shape: (3,)).

    Returns:
    np.array: The projected point on the plane (shape: (3,)).
    """
    point = np.asarray(point)
    plane_point = np.asarray(plane_point)
    plane_normal = np.asarray(plane_normal)
    
    # Normalize the plane normal
    plane_normal = plane_normal / np.linalg.norm(plane_normal)
    
    # Vector from plane point to the point
    vec = point - plane_point
    
    # Distance from the point to the plane along the normal
    distance = np.dot(vec, plane_normal)
    
    # Projected point calculation
    projected_point = point - distance * plane_normal
    
    return projected_point

def project_point_on_line(point, line_point, line_direction):
    """
    Projects a point onto a line defined by a point and a direction vector.

    Parameters:
    point (np.array): The 3D point to be projected (shape: (3,)).
    line_point (np.array): A point on the line (shape: (3,)).
    line_direction (np.array): The direction vector of the line (shape: (3,)).

    Returns:
    np.array: The projected point on the line (shape: (3,)).
    """
    point = np.asarray(point)
    line_point = np.asarray(line_point)
    line_direction = np.asarray(line_direction)
    
    # Normalize the line direction
    line_direction = line_direction / np.linalg.norm(line_direction)
    
    # Vector from line point to the point
    vec = point - line_point
    
    # Projection length along the line direction
    projection_length = np.dot(vec, line_direction)
    
    # Projected point calculation
    projected_point = line_point + projection_length * line_direction
    
    return projected_point

def project_point_on_aabb(point, aabb_min, aabb_max):
    point = np.asarray(point)
    aabb_min = np.asarray(aabb_min)
    aabb_max = np.asarray(aabb_max)
    
    projected_point = np.maximum(aabb_min, np.minimum(point, aabb_max))
    return projected_point

def found_parameter(t0, t1, value):
    if abs(t1 - t0) < 1e-12:
        return float('inf')
    return (value - t0) / (t1 - t0)

def parameter_of_noclamped_segment_projection(point, segment_start, segment_end):
    A = np.asarray(segment_start)
    B = np.asarray(segment_end)
    P = np.asarray(point)
    
    AB = B - A

    AB_sqr = np.dot(AB, AB)
    if AB_sqr < 1e-12:
        return 0.0  # Segment is a point

    AP = P - A    
    t = np.dot(AP, AB) / AB_sqr
    return t
    
def project_segment_on_aabb(segment_start, segment_end, aabb_min, aabb_max):
    A = np.asarray(segment_start)
    B = np.asarray(segment_end)
    Min = np.asarray(aabb_min)
    Max = np.asarray(aabb_max)
    d = B - A

    candidates = []

    rank = len(aabb_max)
    for i in range(rank):
        t_of_min_intersection = found_parameter(A[i], B[i], Min[i])
        t_of_max_intersection = found_parameter(A[i], B[i], Max[i])

        if 0 <= t_of_min_intersection <= 1:
            point_of_min_intersection = A + t_of_min_intersection * d
            candidates.append(project_point_on_aabb(point_of_min_intersection, Min, Max))
        if 0 <= t_of_max_intersection <= 1:
            point_of_max_intersection = A + t_of_max_intersection * d
            candidates.append(project_point_on_aabb(point_of_max_intersection, Min, Max))

    min_distance_sq = float('inf')
    closest_point_on_segment = None
    closest_point_on_aabb = None
    
    A_projected = project_point_on_aabb(A, Min, Max)
    B_projected = project_point_on_aabb(B, Min, Max)
    distance_sq_A = np.sum((A - A_projected) ** 2)
    distance_sq_B = np.sum((B - B_projected) ** 2)
    if distance_sq_A < distance_sq_B:
        min_distance_sq = distance_sq_A
        closest_point_on_segment = A
        closest_point_on_aabb = A_projected
    else:
        min_distance_sq = distance_sq_B
        closest_point_on_segment = B
        closest_point_on_aabb = B_projected
    
    for candidate in candidates:
        parameter_of_closest_on_segment = parameter_of_noclamped_segment_projection(candidate, A, B)
        if 0.0 <= parameter_of_closest_on_segment <= 1.0:
            closest_point_on_segment_candidate = A + parameter_of_closest_on_segment * d
            distance_sq = np.sum((candidate - closest_point_on_segment_candidate) ** 2)
            if distance_sq < min_distance_sq:
                min_distance_sq = distance_sq
                closest_point_on_segment = closest_point_on_segment_candidate
                closest_point_on_aabb = candidate

    return closest_point_on_segment, closest_point_on_aabb, math.sqrt(min_distance_sq)
    

def closest_of_aabb_and_capsule(aabb_min, aabb_max, capsule_point1, capsule_point2, capsule_radius):
    capsule_core_point, aabb_point, distance = project_segment_on_aabb(
        capsule_point1, capsule_point2, aabb_min, aabb_max
    )
    if distance <= capsule_radius:
        return capsule_core_point, aabb_point, 0.0
    direction = np.asarray(aabb_point - capsule_core_point, dtype=float)
    direction_norm = np.linalg.norm(direction)
    if direction_norm < 1e-12:
        # Capsule core point is inside AABB; choose arbitrary direction
        direction = np.array([1.0, 0.0, 0.0])
        direction_norm = 1.0
    direction = direction / direction_norm
    closest_capsule_point = capsule_core_point + direction * capsule_radius
    return aabb_point, closest_capsule_point, distance - capsule_radius

def closest_of_aabb_and_sphere(aabb_min, aabb_max, sphere_center, sphere_radius):
    aabb_point = project_point_on_aabb(sphere_center, aabb_min, aabb_max)
    direction = np.asarray(sphere_center - aabb_point, dtype=float)

    distance = np.linalg.norm(direction)
    if distance <= sphere_radius:
        return aabb_point, sphere_center, 0.0
    if distance < 1e-12:
        # Sphere center is inside AABB; choose arbitrary direction
        direction = np.array([1.0, 0.0, 0.0])
        distance = 1.0
    direction = direction / distance
    closest_sphere_point = sphere_center - direction * sphere_radius

    return aabb_point, closest_sphere_point, distance - sphere_radius
