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
&#9;&quot;&quot;&quot;<br>
&#9;Projects a point onto a plane defined by a point and a normal vector.<br>
<br>
&#9;Parameters:<br>
&#9;point (np.array): The 3D point to be projected (shape: (3,)).<br>
&#9;plane_point (np.array): A point on the plane (shape: (3,)).<br>
&#9;plane_normal (np.array): The normal vector of the plane (shape: (3,)).<br>
<br>
&#9;Returns:<br>
&#9;np.array: The projected point on the plane (shape: (3,)).<br>
&#9;&quot;&quot;&quot;<br>
&#9;point = np.asarray(point)<br>
&#9;plane_point = np.asarray(plane_point)<br>
&#9;plane_normal = np.asarray(plane_normal)<br>
&#9;<br>
&#9;# Normalize the plane normal<br>
&#9;plane_normal = plane_normal / np.linalg.norm(plane_normal)<br>
&#9;<br>
&#9;# Vector from plane point to the point<br>
&#9;vec = point - plane_point<br>
&#9;<br>
&#9;# Distance from the point to the plane along the normal<br>
&#9;distance = np.dot(vec, plane_normal)<br>
&#9;<br>
&#9;# Projected point calculation<br>
&#9;projected_point = point - distance * plane_normal<br>
&#9;<br>
&#9;return projected_point<br>
<br>
def project_point_on_line(point, line_point, line_direction):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Projects a point onto a line defined by a point and a direction vector.<br>
<br>
&#9;Parameters:<br>
&#9;point (np.array): The 3D point to be projected (shape: (3,)).<br>
&#9;line_point (np.array): A point on the line (shape: (3,)).<br>
&#9;line_direction (np.array): The direction vector of the line (shape: (3,)).<br>
<br>
&#9;Returns:<br>
&#9;np.array: The projected point on the line (shape: (3,)).<br>
&#9;&quot;&quot;&quot;<br>
&#9;point = np.asarray(point)<br>
&#9;line_point = np.asarray(line_point)<br>
&#9;line_direction = np.asarray(line_direction)<br>
&#9;<br>
&#9;# Normalize the line direction<br>
&#9;line_direction = line_direction / np.linalg.norm(line_direction)<br>
&#9;<br>
&#9;# Vector from line point to the point<br>
&#9;vec = point - line_point<br>
&#9;<br>
&#9;# Projection length along the line direction<br>
&#9;projection_length = np.dot(vec, line_direction)<br>
&#9;<br>
&#9;# Projected point calculation<br>
&#9;projected_point = line_point + projection_length * line_direction<br>
&#9;<br>
&#9;return projected_point<br>
<br>
def project_point_on_aabb(point, aabb_min, aabb_max):<br>
&#9;point = np.asarray(point)<br>
&#9;aabb_min = np.asarray(aabb_min)<br>
&#9;aabb_max = np.asarray(aabb_max)<br>
&#9;<br>
&#9;projected_point = np.maximum(aabb_min, np.minimum(point, aabb_max))<br>
&#9;return projected_point<br>
<br>
def found_parameter(t0, t1, value):<br>
&#9;if abs(t1 - t0) &lt; 1e-12:<br>
&#9;&#9;return float('inf')<br>
&#9;return (value - t0) / (t1 - t0)<br>
<br>
def parameter_of_noclamped_segment_projection(point, segment_start, segment_end):<br>
&#9;A = np.asarray(segment_start)<br>
&#9;B = np.asarray(segment_end)<br>
&#9;P = np.asarray(point)<br>
&#9;<br>
&#9;AB = B - A<br>
<br>
&#9;AB_sqr = np.dot(AB, AB)<br>
&#9;if AB_sqr &lt; 1e-12:<br>
&#9;&#9;return 0.0  # Segment is a point<br>
<br>
&#9;AP = P - A    <br>
&#9;t = np.dot(AP, AB) / AB_sqr<br>
&#9;return t<br>
&#9;<br>
def project_segment_on_aabb(segment_start, segment_end, aabb_min, aabb_max):<br>
&#9;A = np.asarray(segment_start)<br>
&#9;B = np.asarray(segment_end)<br>
&#9;Min = np.asarray(aabb_min)<br>
&#9;Max = np.asarray(aabb_max)<br>
&#9;d = B - A<br>
<br>
&#9;candidates = []<br>
<br>
&#9;rank = len(aabb_max)<br>
&#9;for i in range(rank):<br>
&#9;&#9;t_of_min_intersection = found_parameter(A[i], B[i], Min[i])<br>
&#9;&#9;t_of_max_intersection = found_parameter(A[i], B[i], Max[i])<br>
<br>
&#9;&#9;if 0 &lt;= t_of_min_intersection &lt;= 1:<br>
&#9;&#9;&#9;point_of_min_intersection = A + t_of_min_intersection * d<br>
&#9;&#9;&#9;candidates.append(project_point_on_aabb(point_of_min_intersection, Min, Max))<br>
&#9;&#9;if 0 &lt;= t_of_max_intersection &lt;= 1:<br>
&#9;&#9;&#9;point_of_max_intersection = A + t_of_max_intersection * d<br>
&#9;&#9;&#9;candidates.append(project_point_on_aabb(point_of_max_intersection, Min, Max))<br>
<br>
&#9;min_distance_sq = float('inf')<br>
&#9;closest_point_on_segment = None<br>
&#9;closest_point_on_aabb = None<br>
&#9;<br>
&#9;A_projected = project_point_on_aabb(A, Min, Max)<br>
&#9;B_projected = project_point_on_aabb(B, Min, Max)<br>
&#9;distance_sq_A = np.sum((A - A_projected) ** 2)<br>
&#9;distance_sq_B = np.sum((B - B_projected) ** 2)<br>
&#9;if distance_sq_A &lt; distance_sq_B:<br>
&#9;&#9;min_distance_sq = distance_sq_A<br>
&#9;&#9;closest_point_on_segment = A<br>
&#9;&#9;closest_point_on_aabb = A_projected<br>
&#9;else:<br>
&#9;&#9;min_distance_sq = distance_sq_B<br>
&#9;&#9;closest_point_on_segment = B<br>
&#9;&#9;closest_point_on_aabb = B_projected<br>
&#9;<br>
&#9;for candidate in candidates:<br>
&#9;&#9;parameter_of_closest_on_segment = parameter_of_noclamped_segment_projection(candidate, A, B)<br>
&#9;&#9;if 0.0 &lt;= parameter_of_closest_on_segment &lt;= 1.0:<br>
&#9;&#9;&#9;closest_point_on_segment_candidate = A + parameter_of_closest_on_segment * d<br>
&#9;&#9;&#9;distance_sq = np.sum((candidate - closest_point_on_segment_candidate) ** 2)<br>
&#9;&#9;&#9;if distance_sq &lt; min_distance_sq:<br>
&#9;&#9;&#9;&#9;min_distance_sq = distance_sq<br>
&#9;&#9;&#9;&#9;closest_point_on_segment = closest_point_on_segment_candidate<br>
&#9;&#9;&#9;&#9;closest_point_on_aabb = candidate<br>
<br>
&#9;return closest_point_on_segment, closest_point_on_aabb, math.sqrt(min_distance_sq)<br>
&#9;<br>
<br>
def closest_of_aabb_and_capsule(aabb_min, aabb_max, capsule_point1, capsule_point2, capsule_radius):<br>
&#9;capsule_core_point, aabb_point, distance = project_segment_on_aabb(<br>
&#9;&#9;capsule_point1, capsule_point2, aabb_min, aabb_max<br>
&#9;)<br>
&#9;if distance &lt;= capsule_radius:<br>
&#9;&#9;return capsule_core_point, aabb_point, 0.0<br>
&#9;direction = np.asarray(aabb_point - capsule_core_point, dtype=float)<br>
&#9;direction_norm = np.linalg.norm(direction)<br>
&#9;if direction_norm &lt; 1e-12:<br>
&#9;&#9;# Capsule core point is inside AABB; choose arbitrary direction<br>
&#9;&#9;direction = np.array([1.0, 0.0, 0.0])<br>
&#9;&#9;direction_norm = 1.0<br>
&#9;direction = direction / direction_norm<br>
&#9;closest_capsule_point = capsule_core_point + direction * capsule_radius<br>
&#9;return aabb_point, closest_capsule_point, distance - capsule_radius<br>
<br>
def closest_of_aabb_and_sphere(aabb_min, aabb_max, sphere_center, sphere_radius):<br>
&#9;aabb_point = project_point_on_aabb(sphere_center, aabb_min, aabb_max)<br>
&#9;direction = np.asarray(sphere_center - aabb_point, dtype=float)<br>
<br>
&#9;print(aabb_max)<br>
&#9;print(aabb_min)<br>
<br>
&#9;distance = np.linalg.norm(direction)<br>
&#9;if distance &lt;= sphere_radius:<br>
&#9;&#9;return aabb_point, sphere_center, 0.0<br>
&#9;if distance &lt; 1e-12:<br>
&#9;&#9;# Sphere center is inside AABB; choose arbitrary direction<br>
&#9;&#9;direction = np.array([1.0, 0.0, 0.0])<br>
&#9;&#9;distance = 1.0<br>
&#9;direction = direction / distance<br>
&#9;closest_sphere_point = sphere_center - direction * sphere_radius<br>
<br>
&#9;return aabb_point, closest_sphere_point, distance - sphere_radius<br>
<!-- END SCAT CODE -->
</body>
</html>
