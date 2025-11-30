#!/usr/bin/env python3
# coding:utf-8

import unittest
import numpy as np
import warnings
from termin.fem.dynamic_assembler import DynamicMatrixAssembler
from termin.fem.multibody3d_3 import (
    RigidBody3D, FixedRotationJoint3D #ForceOnBody3D, , RevoluteJoint3D
)
from termin.geombase.pose3 import Pose3
from numpy import linalg
from termin.fem.inertia3d import SpatialInertia3D


class TestIntegrationMultibody3D(unittest.TestCase):
    """Интеграционные тесты для многотельной системы"""

    def test_rigid_body_with_gravity(self):
        """Создание простой системы с одним твердым телом и гравитацией"""
        assembler = DynamicMatrixAssembler()
        
        body = RigidBody3D(
            inertia=SpatialInertia3D(mass=2.0, inertia=np.diag([1.0, 1.0, 1.0]), com=np.zeros(3)),
            gravity=np.array([0.0, 0.0, -9.81]),
            assembler=assembler)

        index_map = assembler.index_map()
        self.assertIn(body.acceleration_var, index_map)

        matrices = assembler.assemble()

        self.assertIn("mass", matrices)
        self.assertIn("load", matrices)
        self.assertIn("stiffness", matrices)
        self.assertIn("damping", matrices)

        A_ext, b_ext, variables = assembler.assemble_extended_system(matrices)
        x = linalg.solve(A_ext, b_ext)

        assert np.isclose(x[0], 0.0)
        assert np.isclose(x[1], 0.0)
        assert np.isclose(x[2], -9.81)

    def test_rigid_body_with_gravity_noncentral_x(self):
        """Создание простой системы с одним твердым телом и гравитацией"""
        assembler = DynamicMatrixAssembler()
        
        body = RigidBody3D(
            inertia=SpatialInertia3D(mass=2.0, inertia=np.diag([1.0, 1.0, 1.0]), com=np.array([1.5, 0.0, 0.0])),
            gravity=np.array([0.0, 0.0, -9.81]),
            assembler=assembler)

        index_map = assembler.index_map()
        self.assertIn(body.acceleration_var, index_map)

        matrices = assembler.assemble()

        self.assertIn("mass", matrices)
        self.assertIn("load", matrices)
        self.assertIn("stiffness", matrices)
        self.assertIn("damping", matrices)

        A_ext, b_ext, variables = assembler.assemble_extended_system(matrices)
        x = linalg.solve(A_ext, b_ext)

        print("A_ext:")
        print(A_ext)

        print("b_ext:")
        print(b_ext)

        print("variables:")
        print(variables)

        x = linalg.solve(A_ext, b_ext)
        print("Result:")
        print(x)

        diagnosis = assembler.matrix_diagnosis(A_ext)
        print("Matrix Diagnosis: ")
        for key, value in diagnosis.items():
            print(f"  {key}: {value}")

        print("Equations: ")
        eqs = assembler.system_to_human_readable(A_ext, b_ext, variables)
        print(eqs)

        #assert False

        assert np.isclose(x[0], 0.0)
        assert np.isclose(x[1], 0.0)
        assert np.isclose(x[2], -9.81)
        assert np.isclose(x[3], 0.0)
        assert np.isclose(x[4], 0.0)
        assert np.isclose(x[5], 0.0)

    def test_rigid_body_with_gravity_noncentral_y(self):
        """Создание простой системы с одним твердым телом и гравитацией"""
        assembler = DynamicMatrixAssembler()
        
        body = RigidBody3D(
            inertia=SpatialInertia3D(mass=2.0, inertia=np.diag([1.0, 1.0, 1.0]), com=np.array([0.0, 1.5, 0.0])),
            gravity=np.array([0.0, 0.0, -9.81]),
            assembler=assembler)

        index_map = assembler.index_map()
        self.assertIn(body.acceleration_var, index_map)

        matrices = assembler.assemble()

        self.assertIn("mass", matrices)
        self.assertIn("load", matrices)
        self.assertIn("stiffness", matrices)
        self.assertIn("damping", matrices)

        A_ext, b_ext, variables = assembler.assemble_extended_system(matrices)
        x = linalg.solve(A_ext, b_ext)

        print("A_ext:")
        print(A_ext)

        print("b_ext:")
        print(b_ext)

        print("variables:")
        print(variables)

        x = linalg.solve(A_ext, b_ext)
        print("Result:")
        print(x)

        diagnosis = assembler.matrix_diagnosis(A_ext)
        print("Matrix Diagnosis: ")
        for key, value in diagnosis.items():
            print(f"  {key}: {value}")

        print("Equations: ")
        eqs = assembler.system_to_human_readable(A_ext, b_ext, variables)
        print(eqs)

        assert np.isclose(x[0], 0.0)
        assert np.isclose(x[1], 0.0)
        assert np.isclose(x[2], -9.81)
        assert np.isclose(x[3], 0.0)
        assert np.isclose(x[4], 0.0)
        assert np.isclose(x[5], 0.0)
    
    def test_rigid_body_with_fixed_rotation_joint(self):
        """Создание простой системы с одним твердым телом и фиксированным шарниром"""
        assembler = DynamicMatrixAssembler()
        
        body = RigidBody3D(
            inertia=SpatialInertia3D(mass=5.0, inertia=np.diag([5.0, 5.0, 5.0]), com=np.zeros(3)),
            gravity=np.array([0.0, 0.0, -10.00]),
            assembler=assembler)

        body.set_pose(Pose3(lin=np.array([1.0, 0.0, 0.0])))

        joint = FixedRotationJoint3D(
            body=body,
            assembler=assembler,
            coords_of_joint = np.array([0.0, 0.0, 0.0]))

        
        assert joint.radius is not None
        assert joint.radius()[0] == -1.0
        assert joint.radius()[1] == 0.0
        assert assembler.total_variables_by_tag("acceleration") == 6
        assert assembler.total_variables_by_tag("force") == 3

        index_maps = assembler.index_maps()
        self.assertIn("acceleration", index_maps)
        self.assertIn("force", index_maps)
        self.assertEqual(len(index_maps["force"]), 1)
        self.assertEqual(len(index_maps["acceleration"]), 1)
        self.assertIn(body.acceleration_var, index_maps["acceleration"])
        self.assertIn(joint.internal_force, index_maps["force"])

        matrices = assembler.assemble()
        A_ext, b_ext, variables = assembler.assemble_extended_system(matrices)        
        print("A_ext:")
        print(A_ext)

        print("b_ext:")
        print(b_ext)

        print("variables:")
        print(variables)

        x = linalg.solve(A_ext, b_ext)
        print("Result:")
        print(x)

        diagnosis = assembler.matrix_diagnosis(A_ext)
        print("Matrix Diagnosis: ")
        for key, value in diagnosis.items():
            print(f"  {key}: {value}")

        print("Equations: ")
        eqs = assembler.system_to_human_readable(A_ext, b_ext, variables)
        print(eqs)
        
        #assert False
            
        assert np.isclose(x[0], 0.0)
        assert np.isclose(x[1], 0.0)
        assert np.isclose(x[2], -5.0)

    def test_rigid_body_with_fixed_rotation_joint_outcenter(self):
        """Создание простой системы с одним твердым телом и фиксированным шарниром"""
        assembler = DynamicMatrixAssembler()
        
        body = RigidBody3D(
            inertia=SpatialInertia3D(mass=5.0, inertia=np.diag([5.0, 5.0, 5.0]), com=np.array([0.75, 0.0, 0.0])),
            gravity=np.array([0.0, 0.0, -10.00]),
            assembler=assembler)

        body.set_pose(Pose3(lin=np.array([0.25, 0.0, 0.0])))
        #body.acceleration_var.set_value_by_rank(np.array([0.0, 0.0, 1.0, 0.0, 0.0, 0.0]), rank=1)

        joint = FixedRotationJoint3D(
            body=body,
            assembler=assembler,
            coords_of_joint = np.array([0.0, 0.0, 0.0]))

        #joint.update_radius()

        assert joint.radius is not None
        #assert joint.radius[0] == -1.0
        #assert joint.radius[1] == 0.0
        assert assembler.total_variables_by_tag("acceleration") == 6
        assert assembler.total_variables_by_tag("force") == 3

        index_maps = assembler.index_maps()
        self.assertIn("acceleration", index_maps)
        self.assertIn("force", index_maps)
        self.assertEqual(len(index_maps["force"]), 1)
        self.assertEqual(len(index_maps["acceleration"]), 1)
        self.assertIn(body.acceleration_var, index_maps["acceleration"])
        self.assertIn(joint.internal_force, index_maps["force"])

        matrices = assembler.assemble()
        A_ext, b_ext, variables = assembler.assemble_extended_system(matrices)        
        print("A_ext:")
        print(A_ext)

        print("b_ext:")
        print(b_ext)

        print("variables:")
        print(variables)

        x = linalg.solve(A_ext, b_ext)
        print("Result:")
        print(x)

        diagnosis = assembler.matrix_diagnosis(A_ext)
        print("Matrix Diagnosis: ")
        for key, value in diagnosis.items():
            print(f"  {key}: {value}")

        print("Equations: ")
        eqs = assembler.system_to_human_readable(A_ext, b_ext, variables)
        print(eqs)
        
            
        #assert np.isclose(x[0], 0.0)
        #assert np.isclose(x[1], 0.0)
        #assert np.isclose(x[2], -5.0)