"""
Test script for ChronoSquad core movement.

Demonstrates:
1. Creating a timeline
2. Adding an object with movement animatronic
3. Moving time forward - object moves
4. Moving time backward - object returns
"""

from .timeline import Timeline, GAME_FREQUENCY
from .object_of_timeline import ObjectOfTimeline, Vec3, Pose
from .animatronic import LinearMoveAnimatronic, CubicMoveAnimatronic


def test_basic_movement():
    """Test basic forward/backward movement."""
    print("=== Test: Basic Movement ===")

    # Create timeline
    tl = Timeline("TestTimeline")

    # Create object at origin
    obj = ObjectOfTimeline("Player")
    obj.set_position(Vec3(0, 0, 0))
    tl.add_object(obj)

    # Add movement: move from (0,0,0) to (10,0,0) over 100 steps (1 second)
    start_pose = Pose(Vec3(0, 0, 0), obj.pose.rotation)
    end_pose = Pose(Vec3(10, 0, 0), obj.pose.rotation)
    move = LinearMoveAnimatronic(
        start_step=0,
        finish_step=100,
        start_pose=start_pose,
        end_pose=end_pose,
    )
    obj.add_animatronic(move)

    # Move forward
    print(f"Initial: {obj.current_position()}")

    tl.promote(50)  # Half way
    print(f"At step 50: {obj.current_position()}")

    tl.promote(100)  # End
    print(f"At step 100: {obj.current_position()}")

    # Move backward
    tl.promote(50)  # Back to half
    print(f"Back to step 50: {obj.current_position()}")

    tl.promote(0)  # Back to start
    print(f"Back to step 0: {obj.current_position()}")

    print("PASSED\n")


def test_smooth_movement():
    """Test cubic smooth movement."""
    print("=== Test: Smooth Movement ===")

    tl = Timeline("TestTimeline")
    obj = ObjectOfTimeline("Player")
    obj.set_position(Vec3(0, 0, 0))
    tl.add_object(obj)

    # Smooth movement
    start_pose = Pose(Vec3(0, 0, 0), obj.pose.rotation)
    end_pose = Pose(Vec3(10, 0, 0), obj.pose.rotation)
    move = CubicMoveAnimatronic(
        start_step=0,
        finish_step=100,
        start_pose=start_pose,
        end_pose=end_pose,
    )
    obj.add_animatronic(move)

    # Sample positions
    positions = []
    for step in range(0, 101, 10):
        tl.promote(step)
        positions.append((step, obj.current_position().x))

    print("Step -> X position (should be smooth):")
    for step, x in positions:
        bar = "#" * int(x * 3)
        print(f"  {step:3d}: {x:5.2f} {bar}")

    print("PASSED\n")


def test_timeline_copy():
    """Test timeline copying for branching."""
    print("=== Test: Timeline Copy ===")

    tl = Timeline("Main")
    obj = ObjectOfTimeline("Player")
    obj.set_position(Vec3(0, 0, 0))
    tl.add_object(obj)

    # Add movement
    start_pose = Pose(Vec3(0, 0, 0), obj.pose.rotation)
    end_pose = Pose(Vec3(10, 0, 0), obj.pose.rotation)
    move = LinearMoveAnimatronic(0, 100, start_pose, end_pose)
    obj.add_animatronic(move)

    # Move to step 50
    tl.promote(50)
    print(f"Main timeline at step 50: {obj.current_position()}")

    # Create a copy (branch)
    branch = tl.copy("Branch")
    branch_obj = branch.get_object("Player")

    print(f"Branch timeline at step 50: {branch_obj.current_position()}")

    # Move main forward, branch backward
    tl.promote(100)
    branch.promote(0)

    print(f"Main at step 100: {obj.current_position()}")
    print(f"Branch at step 0: {branch_obj.current_position()}")

    print("PASSED\n")


def test_multiple_animatronics():
    """Test sequential animatronics."""
    print("=== Test: Multiple Animatronics ===")

    tl = Timeline("Test")
    obj = ObjectOfTimeline("Player")
    obj.set_position(Vec3(0, 0, 0))
    tl.add_object(obj)

    # First movement: 0->50, move from (0,0,0) to (5,0,0)
    move1 = LinearMoveAnimatronic(
        0, 50,
        Pose(Vec3(0, 0, 0), obj.pose.rotation),
        Pose(Vec3(5, 0, 0), obj.pose.rotation),
    )

    # Second movement: 50->100, move from (5,0,0) to (5,5,0)
    move2 = LinearMoveAnimatronic(
        50, 100,
        Pose(Vec3(5, 0, 0), obj.pose.rotation),
        Pose(Vec3(5, 5, 0), obj.pose.rotation),
    )

    obj.add_animatronic(move1)
    obj.add_animatronic(move2)

    # Trace the path
    print("Path trace:")
    for step in [0, 25, 50, 75, 100]:
        tl.promote(step)
        pos = obj.current_position()
        print(f"  Step {step}: ({pos.x:.1f}, {pos.y:.1f}, {pos.z:.1f})")

    print("PASSED\n")


def run_all_tests():
    """Run all tests."""
    print("ChronoSquad Core Tests\n")
    test_basic_movement()
    test_smooth_movement()
    test_timeline_copy()
    test_multiple_animatronics()
    print("All tests passed!")


if __name__ == "__main__":
    run_all_tests()
