"""
Tests for gizmo picking accuracy.

Verifies that ray casting from screen coordinates correctly hits gizmo colliders.
"""

import numpy as np
import pytest
from unittest.mock import MagicMock

from termin.geombase import Pose3, GeneralPose3, Vec3, Quat
from termin.visualization.core.camera import PerspectiveCameraComponent
from termin.visualization.core.entity import Entity
from termin.editor.gizmo.transform_gizmo import TransformGizmo
from termin.editor.gizmo.base import CylinderGeometry, TorusGeometry


def make_camera_entity(position: np.ndarray, look_at: np.ndarray) -> Entity:
    """Create a camera entity looking at a target point."""
    # Compute orientation: Y-forward convention
    forward = look_at - position
    forward = forward / np.linalg.norm(forward)

    # Build rotation that aligns +Y with forward direction
    # Default orientation: +Y forward, +Z up
    up = np.array([0, 0, 1], dtype=np.float32)

    # Handle case when looking straight up/down
    if abs(np.dot(forward, up)) > 0.99:
        up = np.array([0, 1, 0], dtype=np.float32)

    right = np.cross(forward, up)
    right = right / np.linalg.norm(right)
    up = np.cross(right, forward)

    # Rotation matrix: columns are right, forward, up
    rot_matrix = np.array([right, forward, up], dtype=np.float32).T

    # Convert to quaternion
    quat = rotation_matrix_to_quat(rot_matrix)

    entity = Entity(
        pose=GeneralPose3(ang=quat, lin=position),
        name="camera"
    )
    return entity


def rotation_matrix_to_quat(m: np.ndarray) -> np.ndarray:
    """Convert 3x3 rotation matrix to quaternion (x, y, z, w)."""
    trace = m[0, 0] + m[1, 1] + m[2, 2]

    if trace > 0:
        s = 0.5 / np.sqrt(trace + 1.0)
        w = 0.25 / s
        x = (m[2, 1] - m[1, 2]) * s
        y = (m[0, 2] - m[2, 0]) * s
        z = (m[1, 0] - m[0, 1]) * s
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = 2.0 * np.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2])
        w = (m[2, 1] - m[1, 2]) / s
        x = 0.25 * s
        y = (m[0, 1] + m[1, 0]) / s
        z = (m[0, 2] + m[2, 0]) / s
    elif m[1, 1] > m[2, 2]:
        s = 2.0 * np.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2])
        w = (m[0, 2] - m[2, 0]) / s
        x = (m[0, 1] + m[1, 0]) / s
        y = 0.25 * s
        z = (m[1, 2] + m[2, 1]) / s
    else:
        s = 2.0 * np.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1])
        w = (m[1, 0] - m[0, 1]) / s
        x = (m[0, 2] + m[2, 0]) / s
        y = (m[1, 2] + m[2, 1]) / s
        z = 0.25 * s

    return np.array([x, y, z, w], dtype=np.float32)


def world_to_screen(
    point: np.ndarray,
    view_matrix: np.ndarray,
    proj_matrix: np.ndarray,
    viewport_rect: tuple,
) -> tuple[float, float] | None:
    """Project world point to screen coordinates."""
    px, py, pw, ph = viewport_rect

    # Homogeneous coordinates
    p = np.array([point[0], point[1], point[2], 1.0], dtype=np.float32)

    # Apply view and projection
    clip = proj_matrix @ view_matrix @ p

    # Behind camera check
    if clip[3] <= 0:
        return None

    # Perspective divide
    ndc = clip[:3] / clip[3]

    # NDC to screen (Y is flipped)
    screen_x = px + (ndc[0] + 1.0) * 0.5 * pw
    screen_y = py + (1.0 - ndc[1]) * 0.5 * ph

    return screen_x, screen_y


class TestGizmoPickingBasic:
    """Basic tests for gizmo picking."""

    def test_ray_hits_gizmo_center(self):
        """Ray from gizmo's screen position should hit near gizmo origin."""
        # Setup: camera at (0, -5, 2) looking at origin
        camera_pos = np.array([0, -5, 2], dtype=np.float32)
        target_pos = np.array([0, 0, 0], dtype=np.float32)

        camera_entity = make_camera_entity(camera_pos, target_pos)
        camera = PerspectiveCameraComponent(fov_y_degrees=60.0, near=0.1, far=100.0)
        camera.entity = camera_entity
        camera.set_aspect(1.0)  # Square viewport

        # Target entity at origin
        target_entity = Entity(
            pose=GeneralPose3(lin=target_pos),
            name="target"
        )

        # Gizmo
        gizmo = TransformGizmo(size=1.0)
        gizmo.target = target_entity

        # Compute screen scale
        distance = np.linalg.norm(camera_pos - target_pos)
        screen_scale = max(0.1, distance * 0.1)
        gizmo.set_screen_scale(screen_scale)

        # Get matrices
        view = camera.get_view_matrix()
        proj = camera.get_projection_matrix()

        # Viewport
        viewport_rect = (0, 0, 800, 800)

        # Project gizmo center to screen
        screen_pos = world_to_screen(target_pos, view, proj, viewport_rect)
        assert screen_pos is not None, "Gizmo should be visible"

        screen_x, screen_y = screen_pos
        print(f"Gizmo center on screen: ({screen_x:.1f}, {screen_y:.1f})")

        # Cast ray from that screen position
        ray = camera.screen_point_to_ray(screen_x, screen_y, viewport_rect)
        ray_origin = np.array([ray.origin.x, ray.origin.y, ray.origin.z])
        ray_dir = np.array([ray.direction.x, ray.direction.y, ray.direction.z])

        print(f"Ray origin: {ray_origin}")
        print(f"Ray direction: {ray_dir}")

        # The ray should pass very close to the gizmo origin
        # Find closest point on ray to origin
        t = np.dot(target_pos - ray_origin, ray_dir)
        closest_point = ray_origin + ray_dir * t
        distance_to_origin = np.linalg.norm(closest_point - target_pos)

        print(f"Closest point on ray to origin: {closest_point}")
        print(f"Distance: {distance_to_origin}")

        assert distance_to_origin < 0.01, f"Ray should pass through origin, but distance is {distance_to_origin}"

    def test_ray_hits_x_axis_arrow(self):
        """Ray aimed at X axis arrow should hit it."""
        # Setup
        camera_pos = np.array([0, -5, 0], dtype=np.float32)
        target_pos = np.array([0, 0, 0], dtype=np.float32)

        camera_entity = make_camera_entity(camera_pos, target_pos)
        camera = PerspectiveCameraComponent(fov_y_degrees=60.0, near=0.1, far=100.0)
        camera.entity = camera_entity
        camera.set_aspect(1.0)

        target_entity = Entity(
            pose=GeneralPose3(lin=target_pos),
            name="target"
        )

        gizmo = TransformGizmo(size=1.0)
        gizmo.target = target_entity

        distance = np.linalg.norm(camera_pos - target_pos)
        screen_scale = max(0.1, distance * 0.1)
        gizmo.set_screen_scale(screen_scale)

        view = camera.get_view_matrix()
        proj = camera.get_projection_matrix()
        viewport_rect = (0, 0, 800, 800)

        # Point on X axis (middle of arrow)
        arrow_length = gizmo._scaled(gizmo._arrow_length)
        x_axis_point = target_pos + np.array([arrow_length * 0.5, 0, 0])

        screen_pos = world_to_screen(x_axis_point, view, proj, viewport_rect)
        assert screen_pos is not None

        screen_x, screen_y = screen_pos
        print(f"X axis arrow on screen: ({screen_x:.1f}, {screen_y:.1f})")

        # Cast ray
        ray = camera.screen_point_to_ray(screen_x, screen_y, viewport_rect)
        ray_origin = np.array([ray.origin.x, ray.origin.y, ray.origin.z])
        ray_dir = np.array([ray.direction.x, ray.direction.y, ray.direction.z])

        # Get colliders and test intersection
        colliders = gizmo.get_colliders()

        hit_any = False
        for collider in colliders:
            t = collider.geometry.ray_intersect(ray_origin, ray_dir)
            if t is not None:
                print(f"Hit collider {collider.id} at t={t}")
                hit_any = True

        assert hit_any, "Should hit at least one collider"


class TestGizmoPickingWithRotation:
    """Test picking with rotated target entity."""

    def test_rotated_entity_local_mode(self):
        """Gizmo in local mode should align with rotated entity."""
        camera_pos = np.array([0, -5, 2], dtype=np.float32)
        target_pos = np.array([0, 0, 0], dtype=np.float32)

        camera_entity = make_camera_entity(camera_pos, target_pos)
        camera = PerspectiveCameraComponent(fov_y_degrees=60.0, near=0.1, far=100.0)
        camera.entity = camera_entity
        camera.set_aspect(1.0)

        # Rotated target entity (45 degrees around Z)
        angle = np.pi / 4
        quat = np.array([0, 0, np.sin(angle/2), np.cos(angle/2)], dtype=np.float32)
        target_entity = Entity(
            pose=GeneralPose3(ang=quat, lin=target_pos),
            name="target"
        )

        gizmo = TransformGizmo(size=1.0)
        gizmo.target = target_entity
        gizmo.set_orientation_mode("local")

        distance = np.linalg.norm(camera_pos - target_pos)
        screen_scale = max(0.1, distance * 0.1)
        gizmo.set_screen_scale(screen_scale)

        view = camera.get_view_matrix()
        proj = camera.get_projection_matrix()
        viewport_rect = (0, 0, 800, 800)

        # In local mode, X axis should be rotated
        rotated_x = np.array([np.cos(angle), np.sin(angle), 0], dtype=np.float32)
        arrow_length = gizmo._scaled(gizmo._arrow_length)
        x_axis_point = target_pos + rotated_x * arrow_length * 0.5

        screen_pos = world_to_screen(x_axis_point, view, proj, viewport_rect)
        assert screen_pos is not None

        screen_x, screen_y = screen_pos

        ray = camera.screen_point_to_ray(screen_x, screen_y, viewport_rect)
        ray_origin = np.array([ray.origin.x, ray.origin.y, ray.origin.z])
        ray_dir = np.array([ray.direction.x, ray.direction.y, ray.direction.z])

        # Check that colliders are also rotated
        colliders = gizmo.get_colliders()

        # Find X translate collider
        from termin.editor.gizmo.transform_gizmo import TransformElement
        x_colliders = [c for c in colliders if c.id == TransformElement.TRANSLATE_X]

        assert len(x_colliders) > 0, "Should have X translate colliders"

        # Test hit
        hit_x = False
        for collider in x_colliders:
            t = collider.geometry.ray_intersect(ray_origin, ray_dir)
            if t is not None:
                hit_x = True
                print(f"Hit X collider at t={t}")
                break

        assert hit_x, "Should hit rotated X axis collider"


class TestMatrixConsistency:
    """Test that projection and unprojection are consistent."""

    def test_project_unproject_roundtrip(self):
        """Project a point, unproject the screen coords, should get ray through point."""
        camera_pos = np.array([2, -5, 3], dtype=np.float32)
        target_pos = np.array([1, 1, 0.5], dtype=np.float32)

        camera_entity = make_camera_entity(camera_pos, target_pos)
        camera = PerspectiveCameraComponent(fov_y_degrees=60.0, near=0.1, far=100.0)
        camera.entity = camera_entity
        camera.set_aspect(1.0)

        view = camera.get_view_matrix()
        proj = camera.get_projection_matrix()
        viewport_rect = (0, 0, 800, 800)

        # Test several world points
        test_points = [
            np.array([0, 0, 0], dtype=np.float32),
            np.array([1, 0, 0], dtype=np.float32),
            np.array([0, 1, 0], dtype=np.float32),
            np.array([0, 0, 1], dtype=np.float32),
            np.array([1, 2, 0.5], dtype=np.float32),
            np.array([-1, 3, 1], dtype=np.float32),
        ]

        for point in test_points:
            screen_pos = world_to_screen(point, view, proj, viewport_rect)
            if screen_pos is None:
                continue

            screen_x, screen_y = screen_pos

            # Unproject
            ray = camera.screen_point_to_ray(screen_x, screen_y, viewport_rect)
            ray_origin = np.array([ray.origin.x, ray.origin.y, ray.origin.z])
            ray_dir = np.array([ray.direction.x, ray.direction.y, ray.direction.z])

            # Find closest point on ray to world point
            t = np.dot(point - ray_origin, ray_dir)
            closest = ray_origin + ray_dir * t
            distance = np.linalg.norm(closest - point)

            print(f"Point {point} -> screen ({screen_x:.1f}, {screen_y:.1f}) -> ray distance {distance:.6f}")

            assert distance < 0.001, f"Ray should pass through point {point}, distance={distance}"


class TestColliderGeometry:
    """Test that collider geometry matches expected values."""

    def test_cylinder_positions(self):
        """Cylinder colliders should be at expected positions."""
        target_pos = np.array([1, 2, 3], dtype=np.float32)
        target_entity = Entity(
            pose=GeneralPose3(lin=target_pos),
            name="target"
        )

        gizmo = TransformGizmo(size=1.0)
        gizmo.target = target_entity
        gizmo.set_screen_scale(1.0)
        gizmo.set_orientation_mode("world")

        colliders = gizmo.get_colliders()

        from termin.editor.gizmo.transform_gizmo import TransformElement

        # Find X translate shaft collider
        for collider in colliders:
            if collider.id == TransformElement.TRANSLATE_X:
                if isinstance(collider.geometry, CylinderGeometry):
                    print(f"X shaft: start={collider.geometry.start}, end={collider.geometry.end}")

                    # Start should be at target position
                    np.testing.assert_array_almost_equal(
                        collider.geometry.start, target_pos, decimal=5,
                        err_msg="Cylinder start should be at target position"
                    )

                    # End should be along X axis
                    expected_dir = np.array([1, 0, 0], dtype=np.float32)
                    actual_dir = collider.geometry.end - collider.geometry.start
                    actual_dir = actual_dir / np.linalg.norm(actual_dir)
                    np.testing.assert_array_almost_equal(
                        actual_dir, expected_dir, decimal=5,
                        err_msg="Cylinder should point along X axis"
                    )
                    break


class TestAspectRatio:
    """Test picking with different aspect ratios."""

    @pytest.mark.parametrize("aspect,width,height", [
        (1.0, 800, 800),
        (16/9, 1920, 1080),
        (4/3, 1024, 768),
        (2.0, 1600, 800),
        (0.5, 400, 800),
    ])
    def test_ray_through_center_various_aspects(self, aspect, width, height):
        """Ray through center should work with any aspect ratio."""
        camera_pos = np.array([0, -5, 2], dtype=np.float32)
        target_pos = np.array([0, 0, 0], dtype=np.float32)

        camera_entity = make_camera_entity(camera_pos, target_pos)
        camera = PerspectiveCameraComponent(fov_y_degrees=60.0, near=0.1, far=100.0)
        camera.entity = camera_entity
        camera.set_aspect(aspect)

        view = camera.get_view_matrix()
        proj = camera.get_projection_matrix()
        viewport_rect = (0, 0, width, height)

        screen_pos = world_to_screen(target_pos, view, proj, viewport_rect)
        assert screen_pos is not None

        screen_x, screen_y = screen_pos

        ray = camera.screen_point_to_ray(screen_x, screen_y, viewport_rect)
        ray_origin = np.array([ray.origin.x, ray.origin.y, ray.origin.z])
        ray_dir = np.array([ray.direction.x, ray.direction.y, ray.direction.z])

        t = np.dot(target_pos - ray_origin, ray_dir)
        closest = ray_origin + ray_dir * t
        distance = np.linalg.norm(closest - target_pos)

        assert distance < 0.01, f"Aspect {aspect}: ray should hit center, distance={distance}"

    @pytest.mark.parametrize("aspect,width,height", [
        (16/9, 1920, 1080),
        (4/3, 1024, 768),
    ])
    def test_gizmo_x_axis_with_widescreen(self, aspect, width, height):
        """X axis gizmo should be hittable on widescreen."""
        camera_pos = np.array([0, -5, 0], dtype=np.float32)
        target_pos = np.array([0, 0, 0], dtype=np.float32)

        camera_entity = make_camera_entity(camera_pos, target_pos)
        camera = PerspectiveCameraComponent(fov_y_degrees=60.0, near=0.1, far=100.0)
        camera.entity = camera_entity
        camera.set_aspect(aspect)

        target_entity = Entity(
            pose=GeneralPose3(lin=target_pos),
            name="target"
        )

        gizmo = TransformGizmo(size=1.0)
        gizmo.target = target_entity

        distance = np.linalg.norm(camera_pos - target_pos)
        screen_scale = max(0.1, distance * 0.1)
        gizmo.set_screen_scale(screen_scale)

        view = camera.get_view_matrix()
        proj = camera.get_projection_matrix()
        viewport_rect = (0, 0, width, height)

        # Point on X axis
        arrow_length = gizmo._scaled(gizmo._arrow_length)
        x_point = target_pos + np.array([arrow_length * 0.5, 0, 0])

        screen_pos = world_to_screen(x_point, view, proj, viewport_rect)
        assert screen_pos is not None

        screen_x, screen_y = screen_pos

        ray = camera.screen_point_to_ray(screen_x, screen_y, viewport_rect)
        ray_origin = np.array([ray.origin.x, ray.origin.y, ray.origin.z])
        ray_dir = np.array([ray.direction.x, ray.direction.y, ray.direction.z])

        colliders = gizmo.get_colliders()
        hit_any = False
        for collider in colliders:
            t = collider.geometry.ray_intersect(ray_origin, ray_dir)
            if t is not None:
                hit_any = True
                break

        assert hit_any, f"Aspect {aspect}: should hit gizmo at X axis"


class TestOffCenterObject:
    """Test picking with object not at center of screen."""

    @pytest.mark.parametrize("target_offset", [
        np.array([2, 0, 0], dtype=np.float32),
        np.array([-2, 0, 0], dtype=np.float32),
        np.array([0, 2, 0], dtype=np.float32),
        np.array([0, 0, 2], dtype=np.float32),
        np.array([1, 1, 1], dtype=np.float32),
    ])
    def test_off_center_target(self, target_offset):
        """Object not at center should still be pickable."""
        camera_pos = np.array([0, -8, 3], dtype=np.float32)
        target_pos = target_offset.copy()

        # Camera still looks at origin area
        camera_entity = make_camera_entity(camera_pos, np.array([0, 0, 0]))
        camera = PerspectiveCameraComponent(fov_y_degrees=60.0, near=0.1, far=100.0)
        camera.entity = camera_entity
        camera.set_aspect(16/9)

        target_entity = Entity(
            pose=GeneralPose3(lin=target_pos),
            name="target"
        )

        gizmo = TransformGizmo(size=1.0)
        gizmo.target = target_entity

        distance = np.linalg.norm(camera_pos - target_pos)
        screen_scale = max(0.1, distance * 0.1)
        gizmo.set_screen_scale(screen_scale)

        view = camera.get_view_matrix()
        proj = camera.get_projection_matrix()
        viewport_rect = (0, 0, 1920, 1080)

        # Project gizmo center
        screen_pos = world_to_screen(target_pos, view, proj, viewport_rect)
        if screen_pos is None:
            pytest.skip("Target not visible from this camera angle")

        screen_x, screen_y = screen_pos

        # Check if on screen
        if not (0 <= screen_x < 1920 and 0 <= screen_y < 1080):
            pytest.skip("Target off screen")

        ray = camera.screen_point_to_ray(screen_x, screen_y, viewport_rect)
        ray_origin = np.array([ray.origin.x, ray.origin.y, ray.origin.z])
        ray_dir = np.array([ray.direction.x, ray.direction.y, ray.direction.z])

        # Ray should pass through target position
        t = np.dot(target_pos - ray_origin, ray_dir)
        closest = ray_origin + ray_dir * t
        distance = np.linalg.norm(closest - target_pos)

        assert distance < 0.01, f"Offset {target_offset}: ray should hit target, distance={distance}"


class TestScreenEdges:
    """Test picking at different screen positions (not just center)."""

    @pytest.mark.parametrize("screen_fraction_x,screen_fraction_y", [
        (0.5, 0.5),    # Center
        (0.25, 0.5),   # Left
        (0.75, 0.5),   # Right
        (0.5, 0.25),   # Top
        (0.5, 0.75),   # Bottom
        (0.1, 0.5),    # Far left
        (0.9, 0.5),    # Far right
        (0.5, 0.1),    # Far top
        (0.5, 0.9),    # Far bottom
        (0.1, 0.1),    # Top-left corner
        (0.9, 0.1),    # Top-right corner
        (0.1, 0.9),    # Bottom-left corner
        (0.9, 0.9),    # Bottom-right corner
    ])
    def test_roundtrip_at_screen_position(self, screen_fraction_x, screen_fraction_y):
        """Project->unproject should work at all screen positions."""
        camera_pos = np.array([0, -5, 2], dtype=np.float32)
        look_at = np.array([0, 0, 0], dtype=np.float32)

        camera_entity = make_camera_entity(camera_pos, look_at)
        camera = PerspectiveCameraComponent(fov_y_degrees=60.0, near=0.1, far=100.0)
        camera.entity = camera_entity
        camera.set_aspect(16/9)

        width, height = 1920, 1080
        viewport_rect = (0, 0, width, height)

        # Screen position
        screen_x = screen_fraction_x * width
        screen_y = screen_fraction_y * height

        # Get ray
        ray = camera.screen_point_to_ray(screen_x, screen_y, viewport_rect)
        ray_origin = np.array([ray.origin.x, ray.origin.y, ray.origin.z])
        ray_dir = np.array([ray.direction.x, ray.direction.y, ray.direction.z])

        # Get a 3D point at distance 5 along the ray
        world_point = ray_origin + ray_dir * 5.0

        view = camera.get_view_matrix()
        proj = camera.get_projection_matrix()

        # Project back to screen
        screen_back = world_to_screen(world_point, view, proj, viewport_rect)
        assert screen_back is not None

        reprojected_x, reprojected_y = screen_back

        # Should match original screen position
        error_x = abs(reprojected_x - screen_x)
        error_y = abs(reprojected_y - screen_y)

        print(f"Screen ({screen_x:.1f}, {screen_y:.1f}) -> world {world_point} -> screen ({reprojected_x:.1f}, {reprojected_y:.1f})")
        print(f"Error: x={error_x:.3f}, y={error_y:.3f}")

        assert error_x < 1.0, f"X error too large: {error_x} at ({screen_fraction_x}, {screen_fraction_y})"
        assert error_y < 1.0, f"Y error too large: {error_y} at ({screen_fraction_x}, {screen_fraction_y})"

    @pytest.mark.parametrize("aspect,width,height", [
        (16/9, 1920, 1080),
        (4/3, 1024, 768),
        (2.0, 1600, 800),
        (1.0, 800, 800),
    ])
    def test_grid_of_points(self, aspect, width, height):
        """Test a grid of screen points for roundtrip consistency."""
        camera_pos = np.array([0, -5, 2], dtype=np.float32)
        look_at = np.array([0, 0, 0], dtype=np.float32)

        camera_entity = make_camera_entity(camera_pos, look_at)
        camera = PerspectiveCameraComponent(fov_y_degrees=60.0, near=0.1, far=100.0)
        camera.entity = camera_entity
        camera.set_aspect(aspect)

        viewport_rect = (0, 0, width, height)
        view = camera.get_view_matrix()
        proj = camera.get_projection_matrix()

        max_error = 0.0
        worst_pos = None

        # Test 5x5 grid
        for i in range(5):
            for j in range(5):
                screen_x = (i + 0.5) / 5 * width
                screen_y = (j + 0.5) / 5 * height

                ray = camera.screen_point_to_ray(screen_x, screen_y, viewport_rect)
                ray_origin = np.array([ray.origin.x, ray.origin.y, ray.origin.z])
                ray_dir = np.array([ray.direction.x, ray.direction.y, ray.direction.z])

                world_point = ray_origin + ray_dir * 5.0
                screen_back = world_to_screen(world_point, view, proj, viewport_rect)

                if screen_back is None:
                    continue

                error = np.sqrt((screen_back[0] - screen_x)**2 + (screen_back[1] - screen_y)**2)
                if error > max_error:
                    max_error = error
                    worst_pos = (screen_x, screen_y, screen_back[0], screen_back[1])

        print(f"Aspect {aspect}: max error = {max_error:.3f} at {worst_pos}")
        assert max_error < 1.0, f"Aspect {aspect}: max roundtrip error too large: {max_error}"


class TestCameraAngles:
    """Test picking from various camera angles."""

    @pytest.mark.parametrize("camera_pos", [
        np.array([0, -5, 0], dtype=np.float32),    # Front
        np.array([5, 0, 0], dtype=np.float32),     # Right
        np.array([-5, 0, 0], dtype=np.float32),    # Left
        np.array([0, 5, 0], dtype=np.float32),     # Back
        np.array([0, 0, 5], dtype=np.float32),     # Top
        np.array([3, -3, 3], dtype=np.float32),    # Diagonal
        np.array([-2, -4, 1], dtype=np.float32),   # Another angle
    ])
    def test_various_camera_angles(self, camera_pos):
        """Picking should work from various camera angles."""
        target_pos = np.array([0, 0, 0], dtype=np.float32)

        camera_entity = make_camera_entity(camera_pos, target_pos)
        camera = PerspectiveCameraComponent(fov_y_degrees=60.0, near=0.1, far=100.0)
        camera.entity = camera_entity
        camera.set_aspect(16/9)

        target_entity = Entity(
            pose=GeneralPose3(lin=target_pos),
            name="target"
        )

        gizmo = TransformGizmo(size=1.0)
        gizmo.target = target_entity

        distance = np.linalg.norm(camera_pos - target_pos)
        screen_scale = max(0.1, distance * 0.1)
        gizmo.set_screen_scale(screen_scale)

        view = camera.get_view_matrix()
        proj = camera.get_projection_matrix()
        viewport_rect = (0, 0, 1920, 1080)

        screen_pos = world_to_screen(target_pos, view, proj, viewport_rect)
        assert screen_pos is not None, f"Camera at {camera_pos}: target should be visible"

        screen_x, screen_y = screen_pos

        ray = camera.screen_point_to_ray(screen_x, screen_y, viewport_rect)
        ray_origin = np.array([ray.origin.x, ray.origin.y, ray.origin.z])
        ray_dir = np.array([ray.direction.x, ray.direction.y, ray.direction.z])

        t = np.dot(target_pos - ray_origin, ray_dir)
        closest = ray_origin + ray_dir * t
        dist = np.linalg.norm(closest - target_pos)

        assert dist < 0.01, f"Camera at {camera_pos}: ray should hit target, distance={dist}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
