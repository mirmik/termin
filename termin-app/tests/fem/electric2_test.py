#!/usr/bin/env python3
"""
Тесты для электрических элементов (fem/electrical.py)
"""

import unittest
import numpy as np
import sys
import os
import math


# Добавить путь к модулю
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from termin.fem.electrical_2 import (
    Resistor, Capacitor, Inductor, 
    VoltageSource, CurrentSource, Ground, ElectricalNode
)
from termin.fem.assembler import Variable, MatrixAssembler
from termin.fem.dynamic_assembler import DynamicMatrixAssembler


class TestResistor(unittest.TestCase):
    """Тесты для резистора"""
    
    def test_resistor(self):
        """Создание резистора"""

        v1 = ElectricalNode("V1")
        v2 = ElectricalNode("V2")

        v1.value = np.array([11.0])
        v2.value = np.array([15.0])

        assembler = DynamicMatrixAssembler()

        vs = VoltageSource(v1, v2, 5.0, assembler)
        r = Resistor(v1, v2, 10.0, assembler)
        ground = Ground(v2, assembler)

        index_maps = {
            "voltage": assembler.index_map_by_tag("voltage"),
            "current": assembler.index_map_by_tag("current"),
        }

        print(index_maps)
        assert v1 in index_maps["voltage"]
        assert v2 in index_maps["voltage"]

        matrices = assembler.assemble_electric_domain()        
        A_ext, b_ext, variables = assembler.assemble_extended_system_for_electric(matrices)

        print("A_ext:\n", A_ext)
        print("b_ext:\n", b_ext)
        print("variables:\n", variables)

        x = np.linalg.solve(A_ext, b_ext)

        print("result:\n", x)
        assert np.isclose(x[0], 5.0)  # V1
        assert np.isclose(x[1], 0.0)  # V2
        assert np.isclose(x[2], 0.5)  # I_vs
        assert np.isclose(x[3], 0.0)  # Ground current


class TestCapacitor(unittest.TestCase):
    """Тесты для конденсатора"""

    def test_capacitor(self):
        v0 = ElectricalNode("V0")
        v1 = ElectricalNode("V1")
        v2 = ElectricalNode("V2")

        assembler = DynamicMatrixAssembler()

        vs = VoltageSource(v1, v0, 5.0, assembler)
        r = Resistor(v1, v2, 10.0, assembler)
        c = Capacitor(v2, v0, 0.1, assembler)
        ground = Ground(v0, assembler)

        index_maps = {
            "voltage": assembler.index_map_by_tag("voltage"),
            "current": assembler.index_map_by_tag("current"),
            "charge": assembler.index_map_by_tag("charge"),
        }

        print(index_maps)
        assert v1 in index_maps["voltage"]
        assert v2 in index_maps["voltage"]
        assert v0 in index_maps["voltage"]

        matrices = assembler.assemble_electric_domain()        
        A_ext, b_ext, variables = assembler.assemble_extended_system_for_electric(matrices)

        print("A_ext:\n", A_ext)
        print("b_ext:\n", b_ext)
        print("variables:\n", variables)
        print("dt:", assembler.time_step)

        print("Equations:")
        equations = assembler.system_to_human_readable(A_ext, b_ext, variables)
        print(equations)

        x = np.linalg.solve(A_ext, b_ext)

        print("result:\n", x)

        assert np.isclose(x[0], 5.0)  # V1
        assert np.isclose(x[1], 0.0)  # V2
        assert np.isclose(x[3], 0.5, atol=0.1)  # I_vs

    def test_capacitor_graph(self):
        v0 = ElectricalNode("V0")
        v1 = ElectricalNode("V1")
        v2 = ElectricalNode("V2")

        assembler = DynamicMatrixAssembler()

        vs = VoltageSource(v1, v0, 5.0, assembler)
        r = Resistor(v1, v2, 10.0, assembler)
        c = Capacitor(v2, v0, 0.1, assembler)
        ground = Ground(v0, assembler)

        assembler.time_step = 0.01

        index_maps = {
            "voltage": assembler.index_map_by_tag("voltage"),
            "current": assembler.index_map_by_tag("current")
        }

        for i in range(50):
            matrices = assembler.assemble_electric_domain()        
            A_ext, b_ext, variables = assembler.assemble_extended_system_for_electric(matrices)
            x = np.linalg.solve(A_ext, b_ext)
            assembler.upload_solution(variables, x)

            real = c.voltage_difference()
            
            t = (i) * assembler.time_step
            print(f"Time: {t:.3f} s")
            expected = 5.0 * (1.0 - math.exp(-t))
            print(f"  Capacitor voltage: {real.item():.4f} V, expected: {expected:.4f} V")

            c.finish_timestep()

            assert np.isclose(real, expected, atol=0.1)
        

class TestInductor(unittest.TestCase):
    """Тесты для индуктора"""

    def test_inductor(self):
        v0 = ElectricalNode("V0")
        v1 = ElectricalNode("V1")
        v2 = ElectricalNode("V2")

        assembler = DynamicMatrixAssembler()

        vs = VoltageSource(v1, v0, 10.0, assembler)
        l = Inductor(v1, v2, 0.5, assembler)
        r = Resistor(v2, v0, 100.0, assembler)
        ground = Ground(v0, assembler)

        index_maps = {
            "voltage": assembler.index_map_by_tag("voltage"),
            "current": assembler.index_map_by_tag("current"),
        }

        assert v1 in index_maps["voltage"]
        assert v0 in index_maps["voltage"]

        matrices = assembler.assemble_electric_domain()        
        A_ext, b_ext, variables = assembler.assemble_extended_system_for_electric(matrices)

        print("A_ext:\n", A_ext)
        print("b_ext:\n", b_ext)
        print("variables:\n", variables)
        print("dt:", assembler.time_step)

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

        assert np.isclose(x[0], 10.0)  # V1
        assert np.isclose(x[1], 0.0)   # V0


    def test_inductor_graph(self):
        v0 = ElectricalNode("V0")
        v1 = ElectricalNode("V1")
        v2 = ElectricalNode("V2")

        assembler = DynamicMatrixAssembler()

        vs = VoltageSource(v1, v0, 10.0, assembler)
        l = Inductor(v1, v2, 10, assembler)
        r = Resistor(v2, v0, 100.0, assembler)
        ground = Ground(v0, assembler)

        assembler.time_step = 0.01

        index_maps = {
            "voltage": assembler.index_map_by_tag("voltage"),
            "current": assembler.index_map_by_tag("current")
        }

        for i in range(50):
            matrices = assembler.assemble_electric_domain()        
            A_ext, b_ext, variables = assembler.assemble_extended_system_for_electric(matrices)
            x = np.linalg.solve(A_ext, b_ext)
            assembler.upload_solution(variables, x)

            real = l.current()
            
            t = (i) * assembler.time_step
            print(f"Time: {t:.3f} s")
            expected = 0.1 * (1 - math.exp(-10 * t))
            print(f"  Inductor current: {real.item():.4f} A, expected: {expected:.4f} A")

            l.finish_timestep()

            assert np.isclose(real, expected, atol=0.01)

class TestCurrentSource(unittest.TestCase):
    """Тесты для источника тока"""

    def test_current_source(self):
        v0 = ElectricalNode("V0")
        v1 = ElectricalNode("V1")

        assembler = DynamicMatrixAssembler()

        cs = CurrentSource(v1, v0, 2.0, assembler)
        r = Resistor(v1, v0, 5.0, assembler)
        ground = Ground(v0, assembler)

        index_maps = {
            "voltage": assembler.index_map_by_tag("voltage"),
            "current": assembler.index_map_by_tag("current"),
        }

        assert v1 in index_maps["voltage"]
        assert v0 in index_maps["voltage"]

        matrices = assembler.assemble_electric_domain()        
        A_ext, b_ext, variables = assembler.assemble_extended_system_for_electric(matrices)

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

        assert np.isclose(x[0], 10.0)  # V1
        assert np.isclose(x[1], 0.0)   # V0