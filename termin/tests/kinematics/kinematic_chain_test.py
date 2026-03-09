import unittest
from termin.kinematic import KinematicChain3
from termin.kinematic import KinematicTransform3, Rotator3, Actuator3
from termin.geombase import Pose3, Screw2, Screw3
from termin.kinematic import Transform, Transform3
import numpy

class TestKinematicChain3(unittest.TestCase):
    def test_chain_construction(self):
        base = Transform3()
        rotator = Rotator3(axis=numpy.array([0, 0, 1]), parent=base)
        actuator = Actuator3(axis=numpy.array([1, 0, 0]), parent=rotator)
        end_effector = Transform3(parent=actuator.output)

        chain = KinematicChain3(distal=end_effector)

        self.assertIs(chain.distal, end_effector)
        self.assertIs(chain.proximal, base)
        self.assertEqual(len(chain.kinunits()), 2)  # rotator and actuator

        self.assertIs(chain.kinunits()[0], actuator)
        self.assertIs(chain.kinunits()[1], rotator)

        self.assertIs(chain.units()[0], end_effector)
        self.assertIs(chain.units()[1], actuator.output)
        self.assertIs(chain.units()[2], actuator)
        self.assertIs(chain.units()[3], rotator.output)
        self.assertIs(chain.units()[4], rotator)
        self.assertIs(chain.units()[5], base)

        self.assertEqual(len(chain.units()), 6)  # base, rotator+1, actuator+1, end_effector

    def test_apply_coordinate_changes(self):
        base = Transform3()
        rotator = Rotator3(axis=numpy.array([0, 0, 1]), parent=base)
        actuator = Actuator3(axis=numpy.array([1, 0, 0]), parent=rotator)
        end_effector = Transform3(parent=actuator.output)

        chain = KinematicChain3(distal=end_effector)

        initial_rotator_angle = 0
        initial_actuator_displacement = 0

        delta_coords = [1.0, numpy.pi / 2]  # Rotate 90 degrees and extend by 1.0
        chain.apply_coordinate_changes(delta_coords)

        self.assertAlmostEqual(rotator.get_coord(), numpy.pi / 2)
        self.assertAlmostEqual(actuator.get_coord(), 1.0)

    def test_sensitivity_twists(self):
        base = Transform3()
        rotator = Rotator3(axis=numpy.array([0, 0, 1]), parent=base)
        actuator = Actuator3(axis=numpy.array([1, 0, 0]), parent=rotator)
        end_effector = Transform3(parent=actuator.output)

        chain = KinematicChain3(distal=end_effector)

        local_pose = Pose3.translation(0.0, 0.0, 0.0)
        twists = chain.sensitivity_twists(topbody=end_effector, local_pose=local_pose)

        self.assertEqual(len(twists), 2)  # One twist per kinematic unit

        self.assertIsInstance(twists[0], Screw3)  # Actuator twist
        self.assertIsInstance(twists[1], Screw3)  # Rotator twist

        # Check that the twists correspond to the correct axes
        numpy.testing.assert_array_almost_equal(twists[0].lin, numpy.array([1, 0, 0]))
        numpy.testing.assert_array_almost_equal(twists[0].ang, numpy.array([0, 0, 0]))
        numpy.testing.assert_array_almost_equal(twists[1].lin, numpy.array([0, 0, 0]))
        numpy.testing.assert_array_almost_equal(twists[1].ang, numpy.array([0, 0, 1]))

    def test_sensitivity_twists_with_basis(self):
        basis = Pose3.rotateZ(numpy.pi / 2)  # 90 degree rotation around Z
        base = Transform3(basis)
        rotator = Rotator3(axis=numpy.array([0, 0, 1]), parent=base)
        actuator = Actuator3(axis=numpy.array([1, 0, 0]), parent=rotator)
        end_effector = Transform3(parent=actuator.output)

        chain = KinematicChain3(distal=end_effector)

        local_pose = Pose3.translation(0.0, 0.0, 0.0)
        twists = chain.sensitivity_twists(topbody=end_effector, local_pose=local_pose, basis=basis)

        self.assertEqual(len(twists), 2)  # One twist per kinematic unit

        # Check that the twists are transformed correctly by the basis
        numpy.testing.assert_array_almost_equal(twists[0].lin, numpy.array([1, 0, 0]))  # Actuator along Y in basis
        numpy.testing.assert_array_almost_equal(twists[0].ang, numpy.array([0, 0, 0]))
        numpy.testing.assert_array_almost_equal(twists[1].lin, numpy.array([0, 0, 0]))
        numpy.testing.assert_array_almost_equal(twists[1].ang, numpy.array([0, 0, 1]))