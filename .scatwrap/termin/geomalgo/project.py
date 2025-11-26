<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/geomalgo/project.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import math<br>
from tracemalloc import start<br>
import numpy as np<br>
<br>
def project_point_on_plane(point, plane_point, plane_normal):<br>
    &quot;&quot;&quot;<br>
    Projects a point onto a plane defined by a point and a normal vector.<br>
<br>
    Parameters:<br>
    point (np.array): The 3D point to be projected (shape: (3,)).<br>
    plane_point (np.array): A point on the plane (shape: (3,)).<br>
    plane_normal (np.array): The normal vector of the plane (shape: (3,)).<br>
<br>
    Returns:<br>
    np.array: The projected point on the plane (shape: (3,)).<br>
    &quot;&quot;&quot;<br>
    point = np.asarray(point)<br>
    plane_point = np.asarray(plane_point)<br>
    plane_normal = np.asarray(plane_normal)<br>
    <br>
    # Normalize the plane normal<br>
    plane_normal = plane_normal / np.linalg.norm(plane_normal)<br>
    <br>
    # Vector from plane point to the point<br>
    vec = point - plane_point<br>
    <br>
    # Distance from the point to the plane along the normal<br>
    distance = np.dot(vec, plane_normal)<br>
    <br>
    # Projected point calculation<br>
    projected_point = point - distance * plane_normal<br>
    <br>
    return projected_point<br>
<br>
def project_point_on_line(point, line_point, line_direction):<br>
    &quot;&quot;&quot;<br>
    Projects a point onto a line defined by a point and a direction vector.<br>
<br>
    Parameters:<br>
    point (np.array): The 3D point to be projected (shape: (3,)).<br>
    line_point (np.array): A point on the line (shape: (3,)).<br>
    line_direction (np.array): The direction vector of the line (shape: (3,)).<br>
<br>
    Returns:<br>
    np.array: The projected point on the line (shape: (3,)).<br>
    &quot;&quot;&quot;<br>
    point = np.asarray(point)<br>
    line_point = np.asarray(line_point)<br>
    line_direction = np.asarray(line_direction)<br>
    <br>
    # Normalize the line direction<br>
    line_direction = line_direction / np.linalg.norm(line_direction)<br>
    <br>
    # Vector from line point to the point<br>
    vec = point - line_point<br>
    <br>
    # Projection length along the line direction<br>
    projection_length = np.dot(vec, line_direction)<br>
    <br>
    # Projected point calculation<br>
    projected_point = line_point + projection_length * line_direction<br>
    <br>
    return projected_point<br>
<br>
def project_point_on_aabb(point, aabb_min, aabb_max):<br>
    point = np.asarray(point)<br>
    aabb_min = np.asarray(aabb_min)<br>
    aabb_max = np.asarray(aabb_max)<br>
    <br>
    projected_point = np.maximum(aabb_min, np.minimum(point, aabb_max))<br>
    return projected_point<br>
<br>
def found_parameter(t0, t1, value):<br>
    if abs(t1 - t0) &lt; 1e-12:<br>
        return float('inf')<br>
    return (value - t0) / (t1 - t0)<br>
<br>
def parameter_of_noclamped_segment_projection(point, segment_start, segment_end):<br>
    A = np.asarray(segment_start)<br>
    B = np.asarray(segment_end)<br>
    P = np.asarray(point)<br>
    <br>
    AB = B - A<br>
<br>
    AB_sqr = np.dot(AB, AB)<br>
    if AB_sqr &lt; 1e-12:<br>
        return 0.0  # Segment is a point<br>
<br>
    AP = P - A    <br>
    t = np.dot(AP, AB) / AB_sqr<br>
    return t<br>
    <br>
def project_segment_on_aabb(segment_start, segment_end, aabb_min, aabb_max):<br>
    A = np.asarray(segment_start)<br>
    B = np.asarray(segment_end)<br>
    Min = np.asarray(aabb_min)<br>
    Max = np.asarray(aabb_max)<br>
    d = B - A<br>
<br>
    candidates = []<br>
<br>
    rank = len(aabb_max)<br>
    for i in range(rank):<br>
        t_of_min_intersection = found_parameter(A[i], B[i], Min[i])<br>
        t_of_max_intersection = found_parameter(A[i], B[i], Max[i])<br>
<br>
        if 0 &lt;= t_of_min_intersection &lt;= 1:<br>
            point_of_min_intersection = A + t_of_min_intersection * d<br>
            candidates.append(project_point_on_aabb(point_of_min_intersection, Min, Max))<br>
        if 0 &lt;= t_of_max_intersection &lt;= 1:<br>
            point_of_max_intersection = A + t_of_max_intersection * d<br>
            candidates.append(project_point_on_aabb(point_of_max_intersection, Min, Max))<br>
<br>
    min_distance_sq = float('inf')<br>
    closest_point_on_segment = None<br>
    closest_point_on_aabb = None<br>
    <br>
    A_projected = project_point_on_aabb(A, Min, Max)<br>
    B_projected = project_point_on_aabb(B, Min, Max)<br>
    distance_sq_A = np.sum((A - A_projected) ** 2)<br>
    distance_sq_B = np.sum((B - B_projected) ** 2)<br>
    if distance_sq_A &lt; distance_sq_B:<br>
        min_distance_sq = distance_sq_A<br>
        closest_point_on_segment = A<br>
        closest_point_on_aabb = A_projected<br>
    else:<br>
        min_distance_sq = distance_sq_B<br>
        closest_point_on_segment = B<br>
        closest_point_on_aabb = B_projected<br>
    <br>
    for candidate in candidates:<br>
        parameter_of_closest_on_segment = parameter_of_noclamped_segment_projection(candidate, A, B)<br>
        if 0.0 &lt;= parameter_of_closest_on_segment &lt;= 1.0:<br>
            closest_point_on_segment_candidate = A + parameter_of_closest_on_segment * d<br>
            distance_sq = np.sum((candidate - closest_point_on_segment_candidate) ** 2)<br>
            if distance_sq &lt; min_distance_sq:<br>
                min_distance_sq = distance_sq<br>
                closest_point_on_segment = closest_point_on_segment_candidate<br>
                closest_point_on_aabb = candidate<br>
<br>
    return closest_point_on_segment, closest_point_on_aabb, math.sqrt(min_distance_sq)<br>
    <br>
<br>
def closest_of_aabb_and_capsule(aabb_min, aabb_max, capsule_point1, capsule_point2, capsule_radius):<br>
    capsule_core_point, aabb_point, distance = project_segment_on_aabb(<br>
        capsule_point1, capsule_point2, aabb_min, aabb_max<br>
    )<br>
    if distance &lt;= capsule_radius:<br>
        return capsule_core_point, aabb_point, 0.0<br>
    direction = np.asarray(aabb_point - capsule_core_point, dtype=float)<br>
    direction_norm = np.linalg.norm(direction)<br>
    if direction_norm &lt; 1e-12:<br>
        # Capsule core point is inside AABB; choose arbitrary direction<br>
        direction = np.array([1.0, 0.0, 0.0])<br>
        direction_norm = 1.0<br>
    direction = direction / direction_norm<br>
    closest_capsule_point = capsule_core_point + direction * capsule_radius<br>
    return aabb_point, closest_capsule_point, distance - capsule_radius<br>
<br>
def closest_of_aabb_and_sphere(aabb_min, aabb_max, sphere_center, sphere_radius):<br>
    aabb_point = project_point_on_aabb(sphere_center, aabb_min, aabb_max)<br>
    direction = np.asarray(sphere_center - aabb_point, dtype=float)<br>
<br>
    print(aabb_max)<br>
    print(aabb_min)<br>
<br>
    distance = np.linalg.norm(direction)<br>
    if distance &lt;= sphere_radius:<br>
        return aabb_point, sphere_center, 0.0<br>
    if distance &lt; 1e-12:<br>
        # Sphere center is inside AABB; choose arbitrary direction<br>
        direction = np.array([1.0, 0.0, 0.0])<br>
        distance = 1.0<br>
    direction = direction / distance<br>
    closest_sphere_point = sphere_center - direction * sphere_radius<br>
<br>
    return aabb_point, closest_sphere_point, distance - sphere_radius<br>
<!-- END SCAT CODE -->
</body>
</html>
