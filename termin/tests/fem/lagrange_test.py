# #!/usr/bin/env python3
# """
# Тесты для связей через множители Лагранжа
# """

# import unittest
# import numpy as np
# import sys
# import os

# sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# from termin.fem.assembler import (
#     Variable, MatrixAssembler, LagrangeConstraint, BilinearContribution, LoadContribution
# )


# class TestLagrangeConstraint(unittest.TestCase):
#     """Тесты для связей через множители Лагранжа"""
    
#     def test_simple_fixed_constraint(self):
#         """
#         Простейшая связь: u = 0
        
#         Система: k*u = F, связь: u = 0
#         Должно получиться u = 0, λ = F (реакция связи)
#         """
#         assembler = MatrixAssembler()
        
#         u = Variable("u", 1)
#         assembler.variables = [u]
        
#         # Пружина с жесткостью k=1
#         k = 1.0
#         K = np.array([[k]])
#         spring = BilinearContribution([u], K)
        
#         # Приложенная сила F=10
#         F = 10.0
#         force = LoadContribution(u, np.array([F]))
        
#         assembler.contributions = [spring, force]
        
#         # Связь: u = 0
#         constraint = LagrangeConstraint(
#             variables=[u],
#             coefficients=[np.array([[1.0]])],  # 1*u = 0
#             rhs=np.array([0.0])
#         )
#         assembler.constraints = [constraint]
        
#         # Решение
#         x = assembler.solve_and_set(check_conditioning=False, use_constraints=True)
        
#         # Проверки
#         # 1. u должно быть нулевым (связь выполнена точно)
#         self.assertAlmostEqual(u.value, 0.0, places=10)
        
#         # 2. Множитель Лагранжа должен равняться приложенной силе
#         lagrange = assembler.get_lagrange_multipliers()
#         self.assertIsNotNone(lagrange)
#         self.assertAlmostEqual(lagrange[0], F, places=10)
    
#     def test_two_variables_equality(self):
#         """
#         Связь равенства двух переменных: u1 = u2
        
#         Система:
#         k1*u1 = F1
#         k2*u2 = F2
#         Связь: u1 - u2 = 0
#         """
#         assembler = MatrixAssembler()
        
#         u1 = Variable("u1", 1)
#         u2 = Variable("u2", 1)
#         assembler.variables = [u1, u2]
        
#         # Пружины
#         k1 = 2.0
#         k2 = 3.0
#         spring1 = BilinearContribution([u1], np.array([[k1]]))
#         spring2 = BilinearContribution([u2], np.array([[k2]]))
        
#         # Силы
#         F1 = 10.0
#         F2 = 15.0
#         force1 = LoadContribution(u1, np.array([F1]))
#         force2 = LoadContribution(u2, np.array([F2]))
        
#         assembler.contributions = [spring1, spring2, force1, force2]
        
#         # Связь: u1 - u2 = 0
#         constraint = LagrangeConstraint(
#             variables=[u1, u2],
#             coefficients=[
#                 np.array([[1.0]]),   # коэффициент при u1
#                 np.array([[-1.0]])   # коэффициент при u2
#             ],
#             rhs=np.array([0.0])
#         )
#         assembler.constraints = [constraint]
        
#         # Решение
#         x = assembler.solve_and_set(check_conditioning=False, use_constraints=True)
        
#         # Проверки
#         # 1. u1 должно равняться u2
#         self.assertAlmostEqual(u1.value, u2.value, places=10)
        
#         # 2. Проверить баланс сил
#         # (k1 + k2) * u = F1 + F2
#         u_expected = (F1 + F2) / (k1 + k2)
#         self.assertAlmostEqual(u1.value, u_expected, places=10)
        
#         # 3. Множитель Лагранжа - это сила в связи
#         lagrange = assembler.get_lagrange_multipliers()
#         self.assertIsNotNone(lagrange)
#         # λ = F1 - k1*u1 = F2 - k2*u2 (должны совпадать)
#         lambda_from_u1 = F1 - k1 * u1.value
#         lambda_from_u2 = F2 - k2 * u2.value
#         self.assertAlmostEqual(lambda_from_u1, lambda_from_u2, places=10)
#         self.assertAlmostEqual(lagrange[0], lambda_from_u1, places=10)
    
#     def test_2d_vector_constraint(self):
#         """
#         Связь для векторной переменной: vx = 0, vy = 0
        
#         Тело с массой m под действием силы F, закрепленное в точке.
#         """
#         assembler = MatrixAssembler()
        
#         v = Variable("v", 2)  # [vx, vy]
#         assembler.variables = [v]
        
#         # Масса (диагональная матрица)
#         m = 1.0
#         M = m * np.eye(2)
#         mass = BilinearContribution([v], M)
        
#         # Приложенная сила [Fx, Fy]
#         F = np.array([5.0, 10.0])
#         force = LoadContribution(v, F)
        
#         assembler.contributions = [mass, force]
        
#         # Связь: vx = 0, vy = 0
#         constraint = LagrangeConstraint(
#             variables=[v],
#             coefficients=[np.eye(2)],  # [[1, 0], [0, 1]] * [vx, vy] = [0, 0]
#             rhs=np.zeros(2)
#         )
#         assembler.constraints = [constraint]
        
#         # Решение
#         x = assembler.solve_and_set(check_conditioning=False, use_constraints=True)
        
#         # Проверки
#         # 1. Скорость должна быть нулевой
#         self.assertAlmostEqual(v.value[0], 0.0, places=10)
#         self.assertAlmostEqual(v.value[1], 0.0, places=10)
        
#         # 2. Множители Лагранжа - это силы реакции
#         lagrange = assembler.get_lagrange_multipliers()
#         self.assertIsNotNone(lagrange)
#         self.assertEqual(len(lagrange), 2)
#         # Реакция должна уравновешивать приложенную силу
#         self.assertAlmostEqual(lagrange[0], F[0], places=10)
#         self.assertAlmostEqual(lagrange[1], F[1], places=10)


# if __name__ == '__main__':
#     unittest.main()
