#!/usr/bin/env python3
# coding:utf-8

import unittest
import numpy as np
import warnings
from termin.fem.dynamic_assembler import DynamicMatrixAssembler
from termin.fem.multibody2d_3 import (
    RigidBody2D, ForceOnBody2D, FixedRotationJoint2D, RevoluteJoint2D
)
from numpy import linalg
from termin.geombase.screw import Screw2
from termin.geombase.pose2 import Pose2
from termin.fem.inertia2d import SpatialInertia2D


class TestIntegrationMultibody2D(unittest.TestCase):
    """Интеграционные тесты для многотельной системы"""

    def test_rigid_body_with_gravity(self):
        """Создание простой системы с одним твердым телом и гравитацией"""
        assembler = DynamicMatrixAssembler()
        
        body = RigidBody2D(
            inertia=SpatialInertia2D(mass=2.0, inertia=1.0, com=np.zeros(2)),
            gravity=np.array([0.0, -9.81]),
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
        assert np.isclose(x[1], -9.81)
        assert np.isclose(x[2], 0.0)

    def test_noncentral_gravity(self):
        """Создание простой системы с одним твердым телом и гравитацией"""
        assembler = DynamicMatrixAssembler()
        
        body = RigidBody2D(
            inertia=SpatialInertia2D(mass=2.0, inertia=1.0, com=np.array([0.5, 0.0])),
            gravity=np.array([0.0, -9.81]),
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


        print("A_ext: \n")
        print(A_ext)

        print("b_ext: \n")
        print(b_ext)

        print("variables: \n")
        print(variables)

        print("Result: \n")
        print(x)

        diagnosis = assembler.matrix_diagnosis(A_ext)
        print("Matrix Diagnosis: ")
        for key, value in diagnosis.items():
            print(f"  {key}: {value}")

        eqs = assembler.system_to_human_readable(A_ext, b_ext, variables)

        print("Equations: ")
        print(eqs)

        assert np.isclose(x[0], 0.0)
        assert np.isclose(x[1], -9.81)
        assert np.isclose(x[2], 0.0)

    def test_rigid_body_with_external_force(self):
        """Создание простой системы с одним твердым телом и внешней силой"""
        assembler = DynamicMatrixAssembler()
        
        body = RigidBody2D(
            inertia=SpatialInertia2D(mass=3.0, inertia=2.0, com=np.zeros(2)),
            gravity=np.array([0.0, 0.0]),
            assembler=assembler)

        force = ForceOnBody2D(
            body=body,
            wrench=Screw2(ang=0.0, lin=np.array([6.0, 0.0])),
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

        assert np.isclose(x[0], 2.0)  # vx = Fx/m = 6/3 = 2
        assert np.isclose(x[1], 0.0)
        assert np.isclose(x[2], 0.0) 

    def test_rigid_body_with_external_torque(self):
        """Создание простой системы с одним твердым телом и внешним моментом"""
        assembler = DynamicMatrixAssembler()
        
        body = RigidBody2D(
            inertia=SpatialInertia2D(mass=4.0, inertia=8.0, com=np.zeros(2)),
            gravity=np.array([0.0, 0.0]),
            assembler=assembler)

        force = ForceOnBody2D(
            body=body,
            wrench=Screw2(ang=16.0, lin=np.array([0.0, 0.0])),
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
        assert np.isclose(x[2], 2.0)  # omega = torque/J = 16/8 = 2
    
    def test_rigid_body_with_fixed_rotation_joint(self):
        """Создание простой системы с одним твердым телом и фиксированным шарниром"""
        assembler = DynamicMatrixAssembler()
        
        body = RigidBody2D(
            inertia=SpatialInertia2D(mass=5.0, inertia=5.0, com=np.zeros(2)),
            gravity=np.array([0.0, -10.00]),
            assembler=assembler)

        body.set_pose(Pose2(lin=[1.0, 0.0], ang=0.0))

        joint = FixedRotationJoint2D(
            body=body,
            coords_of_joint=np.array([0.0, 0.0]),
            assembler=assembler)

        assert joint.radius()[0] == -1.0
        assert joint.radius()[1] == 0.0
        assert assembler.total_variables_by_tag("acceleration") == 3
        assert assembler.total_variables_by_tag("force") == 2

        index_maps = assembler.index_maps()
        self.assertIn("acceleration", index_maps)
        self.assertIn("force", index_maps)
        self.assertEqual(len(index_maps["force"]), 1)
        self.assertEqual(len(index_maps["acceleration"]), 1)
        self.assertIn(body.acceleration_var, index_maps["acceleration"])
        self.assertIn(joint.internal_force, index_maps["force"])

        matrices = assembler.assemble()
        A_ext, b_ext, variables = assembler.assemble_extended_system(matrices)
        x = linalg.solve(A_ext, b_ext)

        assert np.isclose(x[0], 0.0)
        assert np.isclose(x[1], -5.0)
        assert np.isclose(x[2], -5.0)

    def test_rigid_body_with_fixed_rotation_joint_nonnull_angvel(self):
        """Создание простой системы с одним твердым телом и фиксированным шарниром"""
        assembler = DynamicMatrixAssembler()
        
        body = RigidBody2D(
            inertia=SpatialInertia2D(mass=5.0, inertia=5.0, com=np.zeros(2)),
            gravity=np.array([0.0, 0.0]),
            assembler=assembler)

        body.set_pose(Pose2(lin=[1.0, 0.0], ang=0.0))
        body.velocity_var.set_value([0.0, 6.0, 6.0]) 

        joint = FixedRotationJoint2D(
            body=body,
            coords_of_joint=np.array([0.0, 0.0]),
            assembler=assembler)

        matrices = assembler.assemble()
        A_ext, b_ext, variables = assembler.assemble_extended_system(matrices)
        x = linalg.solve(A_ext, b_ext)

        print("A_ext: \n")
        print(A_ext)

        print("b_ext: \n")
        print(b_ext)

        print ("variables: \n")
        print(variables)

        print("Result: \n")
        print(x)

        diagnosis = assembler.matrix_diagnosis(A_ext)
        print("Matrix Diagnosis: ")
        for key, value in diagnosis.items():
            print(f"  {key}: {value}")

        eqs = assembler.system_to_human_readable(A_ext, b_ext, variables)

        print("Equations: ")
        print(eqs)

        # assert False

        assert np.isclose(x[0], -36.0)
        assert np.isclose(x[1], 0.0)
        assert np.isclose(x[2], 0.0)
        assert np.isclose(x[3], -360)
        assert np.isclose(x[4], 0.0)

    def test_simple_pendulum_in_bottom_position(self):
        """Создание простой системы с одним твердым телом и фиксированным шарниром"""
        assembler = DynamicMatrixAssembler()
        
        body = RigidBody2D(
            inertia=SpatialInertia2D(mass=5.0, inertia=5.0, com=np.zeros(2)),
            gravity=np.array([0.0, -10.00]),
            assembler=assembler)

        body.set_pose(Pose2(lin=[0.0, -1.0], ang=0.0))

        joint = FixedRotationJoint2D(
            body=body,
            assembler=assembler)

        assembler.time_step = 0.01  # временной шаг

        matrices = assembler.assemble()
        A_ext, b_ext, variables = assembler.assemble_extended_system(matrices)
        x = linalg.solve(A_ext, b_ext)
        q_ddot, holonomic_lambdas, nonholonomic_lambdas = assembler.sort_results(x)

        assert np.isclose(body.acceleration_var.value[0], 0.0)
        assert np.isclose(body.acceleration_var.value[1], 0.0)
        assert np.isclose(body.acceleration_var.value[2], 0.0)

    def rotation_symmetric(self):
        """Создание простой системы с одним твердым телом и фиксированным шарниром"""
        assembler = DynamicMatrixAssembler()
        
        body = RigidBody2D(
            inertia=SpatialInertia2D(mass=5.0, inertia=5.0, com=np.zeros(2)),
            gravity=np.array([0.0, -10.00]),
            assembler=assembler)

        body.set_pose(Pose2(lin=[0.0, -1.0], ang=0.0))

        joint = FixedRotationJoint2D(
            body=body,
            assembler=assembler)

        assembler.time_step = 0.01  # временной шаг

        matrices = assembler.assemble()
        A_ext, b_ext, variables = assembler.assemble_extended_system(matrices)
        x = linalg.solve(A_ext, b_ext)
        q_ddot, holonomic_lambdas, nonholonomic_lambdas = assembler.sort_results(x)

    
        assembler2 = DynamicMatrixAssembler()
        
        body2 = RigidBody2D(
            inertia=SpatialInertia2D(mass=5.0, inertia=5.0, com=np.zeros(2)),
            gravity=np.array([-10.0, 0.00]),
            assembler=assembler2)

        body2.set_pose(Pose2(lin=[-1.0, 0.0], ang=0.0))

        joint2 = FixedRotationJoint2D(
            body=body2,
            assembler=assembler2)

        assembler2.time_step = 0.01  # временной шаг

        matrices = assembler2.assemble()
        A_ext2, b_ext2, variables2 = assembler2.assemble_extended_system(matrices)
        x = linalg.solve(A_ext2, b_ext2)
        q_ddot, holonomic_lambdas, nonholonomic_lambdas = assembler2.sort_results(x)

        assert np.isclose(A_ext, A_ext2).all()
        assert np.isclose(b_ext, b_ext2).all()


    def test_simple_pendulum(self):
        """Создание простой системы с одним твердым телом и фиксированным шарниром"""
        assembler = DynamicMatrixAssembler()
        
        body = RigidBody2D(
            inertia=SpatialInertia2D(mass=5.0, inertia=5.0, com=np.zeros(2)),
            gravity=np.array([0.0, -10.00]),
            assembler=assembler)

        body.set_pose(Pose2(lin=np.array([1.0, 0.0]), ang=0.0)) # это установка позиции (хотя может показаться, что это скорость. но это позиция)

        joint = FixedRotationJoint2D(
            body=body,
            coords_of_joint=np.array([0.0, 0.0]),
            assembler=assembler)

        assembler.time_step = 0.01  # временной шаг

        left_side = False
        right_side = False

        for step in range(500):
            matrices = assembler.assemble()
            A_ext, b_ext, variables = assembler.assemble_extended_system(matrices)
            x = linalg.solve(A_ext, b_ext)

            q_ddot, holonomic_lambdas, nonholonomic_lambdas = assembler.sort_results(x)
            q_dot, q = assembler.integrate_with_constraint_projection(q_ddot, matrices)
            
            pose = body.pose()
            print(f"Pose: lin = {pose.lin}, {np.linalg.norm(pose.lin)}")

            if pose.lin[0] < 0.0:
                left_side = True
            if pose.lin[0] > 0.0:
                right_side = True

            assert np.isclose(np.linalg.norm(pose.lin), 1.0, atol=1e-3)

        eps = 1e-15
        pose = body.pose()
        assert left_side and right_side
        

    def test_simple_pendulum_noncentral(self):
        """Создание простой системы с одним твердым телом и фиксированным шарниром"""
        assembler = DynamicMatrixAssembler()
        
        body = RigidBody2D(
            inertia=SpatialInertia2D(mass=5.0, inertia=5.0, com=np.array([0.25, 0.0])),
            gravity=np.array([0.0, -10.00]),
            assembler=assembler)

        body.set_pose(Pose2(lin=np.array([0.75, 0.0]), ang=0.0))
        print(assembler.collect_variables("position"))

        joint = FixedRotationJoint2D(
            body=body,
            coords_of_joint=np.array([0.0, 0.0]),
            assembler=assembler)

        assembler.time_step = 0.01  # временной шаг

        
        matrices = assembler.assemble()
        A_ext, b_ext, variables = assembler.assemble_extended_system(matrices)
        x = linalg.solve(A_ext, b_ext)

            
        print("A_ext: \n")
        print(A_ext)

        print("b_ext: \n")
        print(b_ext)

        print ("variables: \n")
        print(variables)

        print("Result: \n")
        print(x)

        diagnosis = assembler.matrix_diagnosis(A_ext)
        print("Matrix Diagnosis: ")
        for key, value in diagnosis.items():
            print(f"  {key}: {value}")

        eqs = assembler.system_to_human_readable(A_ext, b_ext, variables)

        print("Equations: ")
        print(eqs)

        print(assembler.collect_variables("velocity"))
        print(assembler.collect_variables("position"))
            
        
        q_ddot, holonomic_lambdas, nonholonomic_lambdas = assembler.sort_results(x)
        q_dot, q = assembler.integrate_with_constraint_projection(q_ddot, matrices)

        assert np.isclose(q_ddot[2], -5.0)
        

    def test_double_pendulum(self):
        """Создание простой системы с двумя твердыми телами и фиксированными шарнирами"""
        assembler = DynamicMatrixAssembler()
        
        body1 = RigidBody2D(
            inertia=SpatialInertia2D(mass=6.0, inertia=7.0, com=np.array([0.0, 0.0])),
            gravity=np.array([0.0, -9.81]),
            assembler=assembler,
            name="body1")

        body1.set_pose(Pose2(lin=np.array([5.0, 0.0]), ang=0.0))

        joint1 = FixedRotationJoint2D(
            body=body1,
            assembler=assembler)

        body2 = RigidBody2D(
            inertia=SpatialInertia2D(mass=8.0, inertia=9.0, com=np.zeros(2)),
            gravity=np.array([0.0, -9.81]),
            assembler=assembler,
            name="body2")

        body2.set_pose(Pose2(lin=np.array([6.0, 0.0]), ang=0.0))

        joint2 = RevoluteJoint2D(
            bodyA=body1,
            bodyB=body2,
            coords_of_joint=np.array([1.0, 0.0]),
            assembler=assembler)

        assembler.time_step = 0.01  # временной шаг

        for step in range(500):
            matrices = assembler.assemble()
            A_ext, b_ext, variables = assembler.assemble_extended_system(matrices)
            x = linalg.solve(A_ext, b_ext)

            eqs = assembler.system_to_human_readable(A_ext, b_ext, variables)

            print("A_ext: \n")
            print(A_ext)

            print("b_ext: \n")
            print(b_ext)

            print ("variables: \n")
            print(variables)

            print("Result: \n")
            print(x)

            diagnosis = assembler.matrix_diagnosis(A_ext)
            print("Matrix Diagnosis: ")
            for key, value in diagnosis.items():
                print(f"  {key}: {value}")

            print("Equations: ")
            print(eqs)
            #assert False

            q_ddot, holonomic_lambdas, nonholonomic_lambdas = assembler.sort_results(x)
            q_dot, q = assembler.integrate_with_constraint_projection(q_ddot, matrices)

            print(f"Step {step}: position1 = {q[0:2]}, position2 = {q[3:5]}, norm1 = {np.linalg.norm(q[0:2])}, norm2 = {np.linalg.norm(q[0:2] - q[3:5])}")
        eps = 1e-15
        #assert 1-eps < np.linalg.norm((q[0:2])) < 1+eps
        #assert 1-eps < np.linalg.norm((q[0:2] - q[3:5])) < 1+eps

    def test_double_pendulum_bottom_position(self):
        """Создание простой системы с двумя твердыми телами и фиксированными шарнирами"""
        assembler = DynamicMatrixAssembler()
        
        body1 = RigidBody2D(
            inertia=SpatialInertia2D(mass=6.0, inertia=7.0, com=np.zeros(2)),
            gravity=np.array([0.0, -9.81]),
            assembler=assembler,
            name="body1")

        body1.set_pose(Pose2(lin=np.array([0.0, -2.0]), ang=0.0))

        joint1 = FixedRotationJoint2D(
            body=body1,
            assembler=assembler)

        body2 = RigidBody2D(
            inertia=SpatialInertia2D(mass=8.0, inertia=9.0, com=np.zeros(2)),
            gravity=np.array([0.0, -9.81]),
            assembler=assembler,
            name="body2")

        body2.set_pose(Pose2(lin=np.array([0.0, -4.0]), ang=0.0))

        joint2 = RevoluteJoint2D(
            bodyA=body1,
            bodyB=body2,
            coords_of_joint=np.array([0.0, -2.0]),
            assembler=assembler)

        assembler.time_step = 0.01  # временной шаг

        for step in range(500):
            matrices = assembler.assemble()
            A_ext, b_ext, variables = assembler.assemble_extended_system(matrices)
            x = linalg.solve(A_ext, b_ext)

            eqs = assembler.system_to_human_readable(A_ext, b_ext, variables)

            q_ddot, holonomic_lambdas, nonholonomic_lambdas = assembler.sort_results(x)
            q_dot, q = assembler.integrate_with_constraint_projection(q_ddot, matrices)

            print(f"Step {step}: position1 = {q[0:2]}, position2 = {q[3:5]}, norm1 = {np.linalg.norm(q[0:2])}, norm2 = {np.linalg.norm(q[0:2] - q[3:5])}")
        eps = 1e-15
        
        assert -eps < np.linalg.norm((q[0])) < +eps