import unittest
from termin.kinematic import *
from termin.kinematic import Transform3
from termin.geombase import Pose3
import numpy
import math

class TestRotator3(unittest.TestCase):
    def test_rotation(self):
        rotator = Rotator3(axis=numpy.array([0, 0, 1]))
        trsf = Transform3(Pose3.translation(1.0, 0.0, 0.0))
        rotator.link(trsf)

        angle = math.pi / 2  # 90 degrees
        rotator.set_coord(angle)

        rotated_point = trsf.transform_point(numpy.array([1.0, 0.0, 0.0]))
        expected_point = numpy.array([0.0, 2.0, 0.0])
        numpy.testing.assert_array_almost_equal(rotated_point, expected_point)

        # check childs
        count_of_rotator_childs = len(rotator.children)
        self.assertEqual(count_of_rotator_childs, 1)

        count_of_rotator_output_childs = len(rotator.children)
        self.assertEqual(count_of_rotator_output_childs, 1)

        count_of_trsf_childs = len(trsf.children)
        self.assertEqual(count_of_trsf_childs, 0)

        # check parent
        self.assertIs(trsf.parent, rotator.output) 
        self.assertIs(rotator.output.parent, rotator)
        self.assertIsNone(rotator.parent)