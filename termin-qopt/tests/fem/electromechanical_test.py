#!/usr/bin/env python3
"""
Тесты для электромеханических элементов (fem/electromechanical.py)

Содержит тесты только для DCMotor - класса, связывающего электрическую
и механическую подсистемы.
"""

import unittest
import numpy as np
import sys
import os

# Добавить путь к модулю
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from termin.fem.multibody2d_3 import RigidBody2D
from termin.fem.electromechanic_2 import DCMotor
from termin.fem.electrical_2 import VoltageSource, Ground, ElectricalNode, Resistor
from termin.fem.dynamic_assembler import Variable, DynamicMatrixAssembler
from termin.fem.inertia2d import SpatialInertia2D


class TestDCMotor(unittest.TestCase):
    def test_dc_motor_creation(self):
        """Создание электромеханического двигателя постоянного тока"""

        assembler = DynamicMatrixAssembler()

        body = RigidBody2D(
            SpatialInertia2D(mass=2.0, inertia=0.5, com=np.array([0.0, 0.0])),
            gravity=np.array([0.0, 0.0]),
            assembler=assembler)

        body.velocity_var.set_value(np.array([0, 0, 1.0]))
        
        v1 = ElectricalNode("V1")
        v2 = ElectricalNode("V2")
        v0 = ElectricalNode("V0")

        vs = VoltageSource(v1, v0, U=12.0, assembler=assembler)
        r = Resistor(v1, v2, R=5.0, assembler=assembler)
        gnd = Ground(v0, assembler=assembler)

        dcmotor = DCMotor(
            node1=v2,
            node2=v0,
            connected_body=body,
            k_e=0.1,
            k_t=0.1,
            assembler=assembler)
            
        matrices = assembler.assemble_electromechanic_domain()
        A_ext, b_ext, variables = assembler.assemble_extended_system_for_electromechanic(matrices)

        
        print("A_ext:\n", A_ext)
        print("b_ext:\n", b_ext)
        print("variables:\n", variables)
        
        print("Matrix Diagnosis:")
        diagnosis = assembler.matrix_diagnosis(A_ext)
        for key, value in diagnosis.items():
            print(f"  {key}: {value}")

        print("Equations:")
        equations = assembler.system_to_human_readable(A_ext, b_ext, variables)
        print(equations)

        x = np.linalg.solve(A_ext, b_ext)

        print("result:")
        result_str = assembler.result_to_human_readable(x, variables)
        print(result_str)

