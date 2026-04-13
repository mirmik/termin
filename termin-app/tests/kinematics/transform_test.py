import unittest
from termin.kinematic import Transform3
from termin.kinematic.kinematic import Rotator3, Actuator3
from termin.geombase import Pose3
from termin.kinematic.from_trent import from_trent
import numpy
import math


class TestTransform3(unittest.TestCase):
    def test_relocate_and_global_pose(self):
        transform = Transform3()

        pose = Pose3(
            ang=numpy.array([0.0, 0.0, math.sin(math.pi/4), math.cos(math.pi/4)]),
            lin=numpy.array([1.0, 2.0, 3.0])
        )
        transform.relocate(pose)
        global_pose = transform.global_pose()
        numpy.testing.assert_array_almost_equal(global_pose.ang, pose.ang)
        numpy.testing.assert_array_almost_equal(global_pose.lin, pose.lin)


    def test_hierarchy_global_pose(self):
        parent = Transform3()
        child = Transform3(parent=parent)

        parent_pose = Pose3(
            ang=numpy.array([0.0, 0.0, math.sin(math.pi/4), math.cos(math.pi/4)]),
            lin=numpy.array([1.0, 0.0, 0.0])
        )
        child_pose = Pose3(
            ang=numpy.array([0.0, 0.0, math.sin(math.pi/4), math.cos(math.pi/4)]),
            lin=numpy.array([0.0, 1.0, 0.0])
        )

        parent.relocate(parent_pose)
        child.relocate(child_pose)

        expected_global_child_pose = parent_pose * child_pose
        global_child_pose = child.global_pose()

        numpy.testing.assert_array_almost_equal(global_child_pose.ang, expected_global_child_pose.ang)
        numpy.testing.assert_array_almost_equal(global_child_pose.lin, expected_global_child_pose.lin)

    def test_transform_point(self):
        transform = Transform3()
        pose = Pose3.moveX(1.0) * Pose3.rotateZ(math.pi/2)
        transform.relocate(pose)

        point = numpy.array([1.0, 0.0, 0.0])
        transformed_point = transform.transform_point(point)
        expected_point = numpy.array([1.0, 1.0, 0.0])  # After 90 deg rotation around Z and translation

        numpy.testing.assert_array_almost_equal(transformed_point, expected_point)

    def test_to_trent(self):
        transform1 = Transform3()
        pose = Pose3(
            ang=numpy.array([0.0, 0.0, 0.0, 1.0]),
            lin=numpy.array([1.0, 2.0, 3.0])
        )
        transform1.relocate(pose)
        
        transform2 = Transform3(parent=transform1)
        pose2 = Pose3(
            ang=numpy.array([0.0, 0.0, math.sin(math.pi/2), math.cos(math.pi/2)]),
            lin=numpy.array([0.0, 0.0, 0.0])
        )
        transform2.relocate(pose2)

        dct = transform1.to_trent_with_children()

        expected_dct = {
            "type": "transform",
            "pose": {
                "position": [1.0, 2.0, 3.0],
                "orientation": [0.0, 0.0, 0.0, 1.0]
            },
            "name": "",
            "children": [
                {
                    "type": "transform",
                    "pose": {
                        "position": [0.0, 0.0, 0.0],
                        "orientation": [0.0, 0.0, math.sin(math.pi/2), math.cos(math.pi/2)]
                    },
                    "name": "",
                    "children": []
                }
            ]
        }

        self.assertEqual(dct, expected_dct)

    def test_from_trent(self):
        transform1 = Transform3()
        pose = Pose3(
            ang=numpy.array([0.0, 0.0, 0.0, 1.0]),
            lin=numpy.array([1.0, 2.0, 3.0])
        )
        transform1.relocate(pose)
        
        transform2 = Transform3(parent=transform1)
        pose2 = Pose3(
            ang=numpy.array([0.0, 0.0, math.sin(math.pi/2), math.cos(math.pi/2)]),
            lin=numpy.array([0.0, 0.0, 0.0])
        )
        transform2.relocate(pose2)

        dct = transform1.to_trent_with_children()

        expected_dct = {
            "type": "transform",
            "pose": {
                "position": [1.0, 2.0, 3.0],
                "orientation": [0.0, 0.0, 0.0, 1.0]
            },
            "name": "",
            "children": [
                {
                    "type": "transform",
                    "pose": {
                        "position": [0.0, 0.0, 0.0],
                        "orientation": [0.0, 0.0, math.sin(math.pi/2), math.cos(math.pi/2)]
                    },
                    "name": "",
                    "children": []
                }
            ]
        }

        reconstructed_transform = from_trent(dct)
        reconstructed_dct = reconstructed_transform.to_trent_with_children()

        print(reconstructed_dct)

        self.assertEqual(reconstructed_dct, expected_dct)
    
    def test_trent_with_rotator_and_actuator(self):
        
        rotator = Rotator3(axis=numpy.array([0.0, 0.0, 1.0]), name="rotator1")
        actuator = Actuator3(axis=numpy.array([1.0, 0.0, 0.0]), name="actuator1")
        end_effector = Transform3(name="end_effector")
        
        rotator.link(actuator)
        actuator.link(end_effector)

        expected_dct = {
            "type": "rotator",
            "pose": {
                "position": [0.0, 0.0, 0.0],
                "orientation": [0.0, 0.0, 0.0, 1.0]
            },
            "name": "rotator1",
            "axis": [0.0, 0.0, 1.0],
            "children": [
                {
                    "type": "transform",
                    "name": "rotator1_output",
                    "children": [
                        {
                            "type": "actuator",
                            "pose": {
                                "position": [0.0, 0.0, 0.0],
                                "orientation": [0.0, 0.0, 0.0, 1.0]
                            },
                            "axis": [1.0, 0.0, 0.0],
                            "name": "actuator1",
                            "children": [
                                {
                                    "type": "transform",
                                    "name": "actuator1_output",
                                    "children": [
                                        {
                                            "type": "transform",
                                            "pose": {
                                                "position": [0.0, 0.0, 0.0],
                                                "orientation": [0.0, 0.0, 0.0, 1.0]
                                            },
                                            "name": "end_effector",
                                            "children": []
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        dct = rotator.to_trent_with_children()
        self.maxDiff = None
        self.assertEqual(dct, expected_dct)

        restored_transform = from_trent(dct)
        restored_dct = restored_transform.to_trent_with_children()

        self.assertEqual(restored_dct, expected_dct)