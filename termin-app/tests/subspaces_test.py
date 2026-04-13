import unittest
import numpy as np
from termin.linalg.subspaces import (nullspace_projector, nullspace_basis,
                          nullspace_basis_svd, nullspace_basis_qr,
                          rowspace_projector, rowspace_basis,
                          colspace_projector, colspace_basis,
                          left_nullspace_projector, left_nullspace_basis,
                          vector_projector, subspace_projector,
                          orthogonal_complement,
                          is_in_subspace, subspace_dimension, 
                          orthogonalize, gram_schmidt, orthogonalize_svd,
                          subspace_intersection, projector_basis, is_projector,
                          affine_projector)


class TestNullspaceProjector(unittest.TestCase):
    """Тесты для функции nullspace_projector"""
    
    def test_idempotence(self):
        """Проектор должен быть идемпотентным: P @ P = P"""
        A = np.array([[1., 2., 3.],
                      [2., 4., 6.]])
        P = nullspace_projector(A)
        
        # P @ P = P
        np.testing.assert_allclose(P @ P, P, atol=1e-10)
    
    def test_nullspace_property(self):
        """A @ P должно быть нулевой матрицей"""
        A = np.array([[1., 2., 3.],
                      [2., 4., 6.]])
        P = nullspace_projector(A)
        
        # A @ P = 0
        result = A @ P
        np.testing.assert_allclose(result, np.zeros_like(result), atol=1e-10)
    
    def test_symmetry(self):
        """Проектор должен быть симметричным для вещественных матриц"""
        A = np.array([[1., 2., 3.],
                      [4., 5., 6.]])
        P = nullspace_projector(A)
        
        # P = P.T
        np.testing.assert_allclose(P, P.T, atol=1e-10)
    
    def test_full_rank_matrix(self):
        """Для матрицы полного ранга проектор должен быть нулевым"""
        # Квадратная невырожденная матрица
        A = np.array([[1., 0., 0.],
                      [0., 1., 0.],
                      [0., 0., 1.]])
        P = nullspace_projector(A)
        
        # Нуль-пространство пустое -> P = 0
        np.testing.assert_allclose(P, np.zeros((3, 3)), atol=1e-10)
    
    def test_zero_matrix(self):
        """Для нулевой матрицы проектор должен быть единичной матрицей"""
        A = np.zeros((2, 3))
        P = nullspace_projector(A)
        
        # Всё пространство - нуль-пространство -> P = I
        np.testing.assert_allclose(P, np.eye(3), atol=1e-10)
    
    def test_rank_one_matrix(self):
        """Матрица ранга 1 в R³"""
        # Проекция на ось X
        A = np.array([[1., 0., 0.]])
        P = nullspace_projector(A)
        
        # Нуль-пространство = плоскость YZ
        # Проектор должен зануллять X-компоненту
        v = np.array([5., 3., 2.])
        v_proj = P @ v
        
        self.assertAlmostEqual(v_proj[0], 0.0, places=10)
        self.assertAlmostEqual(v_proj[1], 3.0, places=10)
        self.assertAlmostEqual(v_proj[2], 2.0, places=10)
    
    def test_projection_in_nullspace(self):
        """Проекция произвольного вектора должна попадать в нуль-пространство"""
        A = np.array([[1., 2., 3.],
                      [2., 4., 6.]])
        P = nullspace_projector(A)
        
        # Произвольный вектор
        v = np.array([7., -3., 11.])
        v_proj = P @ v
        
        # A @ v_proj должно быть нулевым
        result = A @ v_proj
        np.testing.assert_allclose(result, np.zeros(2), atol=1e-10)
    
    def test_orthogonality(self):
        """Проекция должна быть ортогональной к дополнению"""
        A = np.array([[1., 2., 3.]])
        P = nullspace_projector(A)
        
        v = np.array([6., 5., 4.])
        v_proj = P @ v
        v_orth = v - v_proj  # Компонента вне нуль-пространства

        # Проверка размерностей
        self.assertEqual(v_proj.shape, v.shape)
        self.assertEqual(P.shape[0], 3)
        
        # Проекция и ортогональная компонента должны быть перпендикулярны
        dot_product = np.dot(v_proj, v_orth)
        self.assertAlmostEqual(dot_product, 0.0, places=10)
    
    def test_rectangular_matrix(self):
        """Прямоугольная матрица m > n"""
        A = np.array([[1., 2.],
                      [3., 4.],
                      [5., 6.]])
        P = nullspace_projector(A)
        
        # Проверка размера
        self.assertEqual(P.shape, (2, 2))
        
        # Проверка основных свойств
        np.testing.assert_allclose(P @ P, P, atol=1e-10)
        result = A @ P
        np.testing.assert_allclose(result, np.zeros_like(result), atol=1e-10)
    
    def test_collinear_rows(self):
        """Матрица с коллинеарными строками (низкий ранг)"""
        # Три коллинеарных строки
        A = np.array([[1., 2., 3., 4.],
                      [2., 4., 6., 8.],
                      [3., 6., 9., 12.]])
        P = nullspace_projector(A)
        
        # Ранг = 1, размерность нуль-пространства = 3
        # Проверка свойств
        np.testing.assert_allclose(P @ P, P, atol=1e-10)
        result = A @ P
        np.testing.assert_allclose(result, np.zeros_like(result), atol=1e-10)
    
    def test_complex_matrix(self):
        """Проектор для комплексной матрицы"""
        A = np.array([[1. + 1j, 2.],
                      [3., 4. - 1j]])
        P = nullspace_projector(A)
        
        # Проверка идемпотентности
        np.testing.assert_allclose(P @ P, P, atol=1e-10)
        
        # Для комплексных матриц: P должен быть эрмитовым (не просто симметричным)
        np.testing.assert_allclose(P, P.T.conj(), atol=1e-10)
    
    def test_dtype_preservation(self):
        """Проектор должен сохранять тип данных"""
        # Float32
        A_f32 = np.array([[1., 2.], [3., 4.]], dtype=np.float32)
        P_f32 = nullspace_projector(A_f32)
        self.assertEqual(P_f32.dtype, np.float32)
        
        # Float64
        A_f64 = np.array([[1., 2.], [3., 4.]], dtype=np.float64)
        P_f64 = nullspace_projector(A_f64)
        self.assertEqual(P_f64.dtype, np.float64)
        
        # Complex128
        A_c128 = np.array([[1.+0j, 2.], [3., 4.]], dtype=np.complex128)
        P_c128 = nullspace_projector(A_c128)
        self.assertEqual(P_c128.dtype, np.complex128)


class TestNullspace(unittest.TestCase):
    """Тесты для функции nullspace_basis (базис нуль-пространства)"""
    
    def test_empty_nullspace(self):
        """Матрица полного ранга - пустое нуль-пространство"""
        A = np.array([[1., 0., 0.],
                      [0., 1., 0.],
                      [0., 0., 1.]])
        N = nullspace_basis(A)
        
        # Размерность = 0
        self.assertEqual(N.shape, (3, 0))
    
    def test_rank_deficient_matrix(self):
        """Матрица неполного ранга"""
        # Вторая строка = 2 * первая (ранг = 1)
        A = np.array([[1., 2., 3.],
                      [2., 4., 6.]])
        N = nullspace_basis(A)
        
        # Размерность нуль-пространства = n - rank = 3 - 1 = 2
        self.assertEqual(N.shape[0], 3)
        self.assertEqual(N.shape[1], 2)
        
        # Проверка: A @ N ≈ 0
        result = A @ N
        np.testing.assert_allclose(result, np.zeros_like(result), atol=1e-10)
    
    def test_orthonormality(self):
        """Базис должен быть ортонормированным"""
        A = np.array([[1., 2., 3., 4.],
                      [2., 4., 6., 8.]])
        N = nullspace_basis(A)
        
        # N.T @ N = I
        gram = N.T @ N
        expected_gram = np.eye(N.shape[1])
        np.testing.assert_allclose(gram, expected_gram, atol=1e-10)
    
    def test_zero_matrix(self):
        """Нулевая матрица - полное пространство является нуль-пространством"""
        A = np.zeros((2, 4))
        N = nullspace_basis(A)
        
        # Размерность = 4 (все пространство)
        self.assertEqual(N.shape, (4, 4))
        
        # Проверка A @ N = 0
        result = A @ N
        np.testing.assert_allclose(result, np.zeros_like(result), atol=1e-10)
        
        # Базис должен быть ортонормированным
        gram = N.T @ N
        np.testing.assert_allclose(gram, np.eye(4), atol=1e-10)
    
    def test_projection_onto_x_axis(self):
        """Матрица проекции на ось X"""
        A = np.array([[1., 0., 0.]])
        N = nullspace_basis(A)
        
        # Нуль-пространство = плоскость YZ (размерность 2)
        self.assertEqual(N.shape, (3, 2))
        
        # A @ N = 0
        result = A @ N
        np.testing.assert_allclose(result, np.zeros((1, 2)), atol=1e-10)
        
        # Все векторы базиса должны иметь нулевую X-компоненту
        for i in range(N.shape[1]):
            self.assertAlmostEqual(N[0, i], 0.0, places=10)
    
    def test_consistency_with_projector(self):
        """Базис согласован с проектором: N @ N.T = P"""
        A = np.array([[1., 2., 3., 4.],
                      [2., 4., 6., 8.]])
        
        N = nullspace_basis(A)
        P = nullspace_projector(A)
        
        # Проектор через базис
        P_from_basis = N @ N.T if N.shape[1] > 0 else np.zeros((A.shape[1], A.shape[1]))
        
        np.testing.assert_allclose(P_from_basis, P, atol=1e-10)
    
    def test_single_vector_nullspace(self):
        """Нуль-пространство размерности 1"""
        # Две коллинеарные строки
        A = np.array([[1., 0., 0.],
                      [0., 1., 0.]])
        N = nullspace_basis(A)
        
        # Нуль-пространство = ось Z
        self.assertEqual(N.shape, (3, 1))
        
        # Вектор базиса должен быть направлен по Z
        self.assertAlmostEqual(N[0, 0], 0.0, places=10)
        self.assertAlmostEqual(N[1, 0], 0.0, places=10)
        self.assertAlmostEqual(abs(N[2, 0]), 1.0, places=10)
    
    def test_custom_tolerance(self):
        """Использование пользовательского порога"""
        A = np.array([[1., 2.],
                      [2., 4.]])  # Вырожденная матрица
        
        # С разными порогами
        N1 = nullspace_basis(A, rtol=1e-10)
        N2 = nullspace_basis(A, rtol=1e-3)
        
        # Оба должны найти нуль-пространство размерности 1
        self.assertEqual(N1.shape[1], 1)
        self.assertEqual(N2.shape[1], 1)
    
    def test_complex_matrix(self):
        """Нуль-пространство комплексной матрицы"""
        A = np.array([[1. + 1j, 2.],
                      [2., 4. - 4j]])
        N = nullspace_basis(A)
        
        # Проверка A @ N ≈ 0
        result = A @ N
        np.testing.assert_allclose(result, np.zeros_like(result), atol=1e-10)
        
        # Ортонормированность для комплексных векторов
        gram = N.T.conj() @ N
        expected = np.eye(N.shape[1])
        np.testing.assert_allclose(gram, expected, atol=1e-10)
    
    def test_rectangular_tall(self):
        """Высокая прямоугольная матрица (m > n)"""
        A = np.array([[1., 2.],
                      [3., 4.],
                      [5., 6.]])
        N = nullspace_basis(A)
        
        # Ранг = 2 (полный для столбцов), нуль-пространство пустое
        self.assertEqual(N.shape, (2, 0))
    
    def test_rectangular_wide(self):
        """Широкая прямоугольная матрица (m < n)"""
        A = np.array([[1., 2., 3., 4.]])
        N = nullspace_basis(A)
        
        # Размерность нуль-пространства = 4 - 1 = 3
        self.assertEqual(N.shape, (4, 3))
        
        # Проверка
        result = A @ N
        np.testing.assert_allclose(result, np.zeros((1, 3)), atol=1e-10)


    def test_jacobian_nullspace_projection(self):
        """Тестирование проектора нуль-пространства на якобиане задачи оптимизации"""
        # Якобиан задачи с вырожденностью
        J = np.array([[1., 0., 0.],
                      [0., 1., 0.],
                      [0., 0., 0.]])
        P = nullspace_projector(J)
        
        # Проекция градиента функции потерь
        gradient = np.array([1., 0., -1.])
        projected_gradient = P @ gradient
        
        # Проверка что проекция лежит в нуль-пространстве
        result = J @ projected_gradient
        np.testing.assert_allclose(projected_gradient, np.array([0., 0., -1.]), atol=1e-10)
        np.testing.assert_allclose(result, np.zeros(J.shape[0]), atol=1e-10)


class TestRowspaceProjector(unittest.TestCase):
    """Тесты для функции rowspace_projector"""
    
    def test_idempotence(self):
        """Проектор должен быть идемпотентным: P @ P = P"""
        A = np.array([[1., 2., 3.],
                      [2., 4., 6.]])
        P = rowspace_projector(A)
        
        # P @ P = P
        np.testing.assert_allclose(P @ P, P, atol=1e-10)
    
    def test_symmetry(self):
        """Проектор должен быть симметричным для вещественных матриц"""
        A = np.array([[1., 2., 3.],
                      [4., 5., 6.]])
        P = rowspace_projector(A)
        
        # P = P^T
        np.testing.assert_allclose(P, P.T, atol=1e-10)
    
    def test_complement_to_nullspace(self):
        """Проектор на rowspace + проектор на nullspace = единичная матрица"""
        A = np.array([[1., 2., 3.],
                      [2., 4., 6.]])
        
        P_row = rowspace_projector(A)
        P_null = nullspace_projector(A)
        
        # P_row + P_null = I
        np.testing.assert_allclose(P_row + P_null, np.eye(3), atol=1e-10)
    
    def test_orthogonality(self):
        """Проекции на rowspace и nullspace ортогональны"""
        A = np.array([[1., 2., 3.],
                      [2., 4., 6.]])
        
        P_row = rowspace_projector(A)
        P_null = nullspace_projector(A)
        
        # P_row @ P_null = 0
        np.testing.assert_allclose(P_row @ P_null, np.zeros((3, 3)), atol=1e-10)
    
    def test_full_rank_matrix(self):
        """Для матрицы полного ранга проектор должен быть единичной матрицей"""
        A = np.array([[1., 0., 0.],
                      [0., 1., 0.],
                      [0., 0., 1.]])
        P = rowspace_projector(A)
        
        # P = I для полноранговой квадратной матрицы
        np.testing.assert_allclose(P, np.eye(3), atol=1e-10)
    
    def test_zero_matrix(self):
        """Для нулевой матрицы проектор должен быть нулевой матрицей"""
        A = np.zeros((2, 3))
        P = rowspace_projector(A)
        
        # P = 0
        np.testing.assert_allclose(P, np.zeros((3, 3)), atol=1e-10)
    
    def test_rank_one_matrix(self):
        """Матрица ранга 1 в R³"""
        A = np.array([[1., 2., 3.]])
        P = rowspace_projector(A)
        
        # Размерность пространства строк = 1
        # Проектор должен проецировать на направление [1, 2, 3]
        v = np.array([1., 2., 3.])
        v_normalized = v / np.linalg.norm(v)
        
        # Проекция v на себя = v
        projected = P @ v
        np.testing.assert_allclose(projected / np.linalg.norm(projected), 
                                   v_normalized, atol=1e-10)
    
    def test_projection_in_rowspace(self):
        """Проекция произвольного вектора должна лежать в пространстве строк"""
        A = np.array([[1., 0., 0.],
                      [0., 1., 0.]])
        P = rowspace_projector(A)
        
        # Произвольный вектор
        v = np.array([1., 2., 3.])
        projected = P @ v
        
        # Проекция должна иметь нулевую Z-компоненту (лежит в плоскости XY)
        self.assertAlmostEqual(projected[2], 0.0, places=10)
        
        # Повторная проекция не меняет вектор (он уже в подпространстве)
        np.testing.assert_allclose(P @ projected, projected, atol=1e-10)
    
    def test_complex_matrix(self):
        """Проектор для комплексной матрицы"""
        A = np.array([[1. + 1j, 2.],
                      [2., 4. - 4j]])
        P = rowspace_projector(A)
        
        # Проектор эрмитов для комплексных матриц: P = P^H
        np.testing.assert_allclose(P, P.T.conj(), atol=1e-10)
        
        # Идемпотентность
        np.testing.assert_allclose(P @ P, P, atol=1e-10)


class TestRowspaceBasis(unittest.TestCase):
    """Тесты для функции rowspace_basis"""
    
    def test_orthonormality(self):
        """Базис должен быть ортонормированным"""
        A = np.array([[1., 2., 3., 4.],
                      [2., 4., 6., 8.]])
        R = rowspace_basis(A)
        
        # R^T @ R = I
        gram = R.T @ R
        expected = np.eye(R.shape[1])
        np.testing.assert_allclose(gram, expected, atol=1e-10)
    
    def test_zero_matrix(self):
        """Нулевая матрица - пустое пространство строк"""
        A = np.zeros((2, 4))
        R = rowspace_basis(A)
        
        # Пространство строк пустое
        self.assertEqual(R.shape, (4, 0))
    
    def test_full_rank_matrix(self):
        """Матрица полного ранга"""
        A = np.array([[1., 0., 0.],
                      [0., 1., 0.],
                      [0., 0., 1.]])
        R = rowspace_basis(A)
        
        # Пространство строк = всё R³
        self.assertEqual(R.shape, (3, 3))
        
        # Базис ортонормирован
        gram = R.T @ R
        np.testing.assert_allclose(gram, np.eye(3), atol=1e-10)
    
    def test_consistency_with_projector(self):
        """Базис согласован с проектором: R @ R.T = P"""
        A = np.array([[1., 2., 3., 4.],
                      [2., 4., 6., 8.]])
        
        R = rowspace_basis(A)
        P = rowspace_projector(A)
        
        # Проектор через базис
        P_from_basis = R @ R.T if R.shape[1] > 0 else np.zeros((A.shape[1], A.shape[1]))
        
        np.testing.assert_allclose(P_from_basis, P, atol=1e-10)
    
    def test_complement_to_nullspace(self):
        """Rowspace и nullspace образуют полный базис"""
        A = np.array([[1., 2., 3.],
                      [2., 4., 6.]])
        
        R = rowspace_basis(A)
        N = nullspace_basis(A)
        
        # Размерности: rank(A) + nullity(A) = n
        self.assertEqual(R.shape[1] + N.shape[1], A.shape[1])
        
        # Объединённая матрица должна иметь полный ранг
        combined = np.hstack([R, N])
        rank = np.linalg.matrix_rank(combined)
        self.assertEqual(rank, A.shape[1])
    
    def test_orthogonality_with_nullspace(self):
        """Базисы rowspace и nullspace ортогональны"""
        A = np.array([[1., 2., 3., 4.],
                      [0., 1., 2., 3.]])
        
        R = rowspace_basis(A)
        N = nullspace_basis(A)
        
        # R^T @ N = 0
        if R.shape[1] > 0 and N.shape[1] > 0:
            cross_product = R.T @ N
            np.testing.assert_allclose(cross_product, np.zeros((R.shape[1], N.shape[1])), 
                                      atol=1e-10)
    
    def test_rank_one_matrix(self):
        """Матрица ранга 1"""
        A = np.array([[2., 4., 6.]])
        R = rowspace_basis(A)
        
        # Пространство строк одномерное
        self.assertEqual(R.shape, (3, 1))
        
        # Базисный вектор нормирован
        self.assertAlmostEqual(np.linalg.norm(R), 1.0, places=10)
    
    def test_tall_matrix(self):
        """Высокая матрица (больше строк, чем столбцов)"""
        A = np.array([[1., 0.],
                      [0., 1.],
                      [1., 1.]])  # 3x2, ранг 2
        R = rowspace_basis(A)
        
        # Пространство строк = всё R²
        self.assertEqual(R.shape, (2, 2))
        
        # Ортонормированность
        gram = R.T @ R
        np.testing.assert_allclose(gram, np.eye(2), atol=1e-10)
    
    def test_wide_matrix(self):
        """Широкая матрица (больше столбцов, чем строк)"""
        A = np.array([[1., 2., 3., 4.],
                      [0., 1., 2., 3.]])  # 2x4, ранг 2
        R = rowspace_basis(A)
        
        # Пространство строк размерности 2
        self.assertEqual(R.shape, (4, 2))
        
        # Ортонормированность
        gram = R.T @ R
        np.testing.assert_allclose(gram, np.eye(2), atol=1e-10)

    def test_custom_tolerance(self):
        """Использование пользовательского порога"""
        A = np.array([[1., 2.],
                      [2., 4.]])  # Вырожденная матрица, ранг 1
        
        R1 = rowspace_basis(A, rtol=1e-10)
        R2 = rowspace_basis(A, rtol=1e-3)
        
        # Оба должны найти пространство строк размерности 1
        self.assertEqual(R1.shape[1], 1)
        self.assertEqual(R2.shape[1], 1)
    
    def test_complex_matrix(self):
        """Пространство строк комплексной матрицы"""
        A = np.array([[1. + 1j, 2.],
                      [2., 4. - 4j]])
        R = rowspace_basis(A)
        
        # Должно существовать пространство строк
        self.assertGreater(R.shape[1], 0)
        
        # Ортонормированность для комплексных векторов
        gram = R.T.conj() @ R
        expected = np.eye(R.shape[1])
        np.testing.assert_allclose(gram, expected, atol=1e-10)


class TestNullspaceBasisQR(unittest.TestCase):
    """Тесты для nullspace_basis_qr"""

    def test_equivalence_with_svd(self):
        """V⊥ = ker(A): проверяем совпадение с SVD-базисом"""
        A = np.array([[1., 2., 3.],
                      [0., 1., 4.]])
        N_perp = nullspace_basis_qr(A)
        N_null = nullspace_basis_svd(A)

        np.testing.assert_allclose(A @ N_perp, np.zeros((A.shape[0], N_perp.shape[1])), atol=1e-10)
        self.assertEqual(N_perp.shape[1], N_null.shape[1])

        proj_perp = N_perp @ N_perp.T.conj()
        np.testing.assert_allclose(proj_perp @ N_null, N_null, atol=1e-10)

    def test_restriction_inside_subspace(self):
        """Сценарий HQP: (J @ N) z = 0 ⇒ J @ (N @ z) = 0"""
        J = np.array([[1., -1., 0.],
                      [0., 0., 1.]])
        N = np.array([[1., 0.],
                      [0., 1.],
                      [0., 0.]])

        A_red = J @ N
        N_red = nullspace_basis_qr(A_red)
        directions = N @ N_red

        self.assertEqual(directions.shape[1], 1)
        np.testing.assert_allclose(J @ directions, np.zeros((J.shape[0], directions.shape[1])), atol=1e-10)


class TestNullspaceBasisSwitch(unittest.TestCase):
    """Проверяем переключатель метода в nullspace_basis"""

    def test_qr_method_matches_helper(self):
        A = np.array([[1., 2., 3.],
                      [2., 4., 6.]])
        N_qr = nullspace_basis(A, method="qr")
        N_expected = nullspace_basis_qr(A)
        np.testing.assert_allclose(N_qr, N_expected, atol=1e-10)

    def test_invalid_method(self):
        A = np.array([[1., 0.],
                      [0., 1.]])
        with self.assertRaises(ValueError):
            nullspace_basis(A, method="foo")


class TestColspaceProjector(unittest.TestCase):
    """Тесты для функции colspace_projector"""
    
    def test_idempotence(self):
        """Проектор должен быть идемпотентным: P @ P = P"""
        A = np.array([[1., 0.],
                      [2., 0.],
                      [3., 0.]])
        P = colspace_projector(A)
        
        # P @ P = P
        np.testing.assert_allclose(P @ P, P, atol=1e-10)
    
    def test_symmetry(self):
        """Проектор должен быть симметричным для вещественных матриц"""
        A = np.array([[1., 2., 3.],
                      [4., 5., 6.]])
        P = colspace_projector(A)
        
        # P = P^T
        np.testing.assert_allclose(P, P.T, atol=1e-10)
    
    def test_complement_to_left_nullspace(self):
        """Проектор на colspace + проектор на left_nullspace = единичная матрица"""
        A = np.array([[1., 2.],
                      [2., 4.],
                      [3., 6.]])
        
        P_col = colspace_projector(A)
        P_left_null = left_nullspace_projector(A)
        
        # P_col + P_left_null = I
        np.testing.assert_allclose(P_col + P_left_null, np.eye(3), atol=1e-10)
    
    def test_orthogonality(self):
        """Проекции на colspace и left_nullspace ортогональны"""
        A = np.array([[1., 2.],
                      [2., 4.],
                      [3., 6.]])
        
        P_col = colspace_projector(A)
        P_left_null = left_nullspace_projector(A)
        
        # P_col @ P_left_null = 0
        np.testing.assert_allclose(P_col @ P_left_null, np.zeros((3, 3)), atol=1e-10)
    
    def test_full_rank_matrix(self):
        """Для матрицы полного ранга по столбцам проектор = единичная матрица"""
        A = np.array([[1., 0.],
                      [0., 1.],
                      [1., 1.]])  # 3x2, ранг 2
        P = colspace_projector(A)
        
        # rank(A) = m не выполнено (2 < 3), но для полного ранга по столбцам
        # проектор проецирует на всё подпространство размерности 2
        self.assertEqual(P.shape, (3, 3))
        np.testing.assert_allclose(P @ P, P, atol=1e-10)
    
    def test_zero_matrix(self):
        """Для нулевой матрицы проектор должен быть нулевой матрицей"""
        A = np.zeros((3, 2))
        P = colspace_projector(A)
        
        # P = 0
        np.testing.assert_allclose(P, np.zeros((3, 3)), atol=1e-10)
    
    def test_projection_makes_solvable(self):
        """Проекция правой части делает систему разрешимой"""
        A = np.array([[1., 0.],
                      [0., 1.],
                      [0., 0.]])  # 3x2, ранг 2
        
        b = np.array([1., 2., 999.])  # Не в colspace!
        P = colspace_projector(A)
        b_proj = P @ b
        
        # b_proj в colspace, поэтому Ax = b_proj разрешима
        # Проверяем что z-компонента обнулилась
        self.assertAlmostEqual(b_proj[2], 0.0, places=10)
    
    def test_dimension(self):
        """Размерность проектора = m x m"""
        A = np.array([[1., 2., 3.],
                      [4., 5., 6.]])  # 2x3
        P = colspace_projector(A)
        
        self.assertEqual(P.shape, (2, 2))


class TestColspaceBasis(unittest.TestCase):
    """Тесты для функции colspace_basis"""
    
    def test_orthonormality(self):
        """Базис должен быть ортонормированным"""
        A = np.array([[1., 2.],
                      [3., 4.],
                      [5., 6.],
                      [7., 8.]])
        C = colspace_basis(A)
        
        # C^T @ C = I
        gram = C.T @ C
        expected = np.eye(C.shape[1])
        np.testing.assert_allclose(gram, expected, atol=1e-10)
    
    def test_zero_matrix(self):
        """Нулевая матрица - пустое пространство столбцов"""
        A = np.zeros((4, 2))
        C = colspace_basis(A)
        
        # Пространство столбцов пустое
        self.assertEqual(C.shape, (4, 0))
    
    def test_full_rank_matrix(self):
        """Матрица полного ранга по столбцам"""
        A = np.array([[1., 0.],
                      [0., 1.],
                      [1., 1.]])  # 3x2, ранг 2
        C = colspace_basis(A)
        
        # Пространство столбцов размерности 2
        self.assertEqual(C.shape, (3, 2))
        
        # Базис ортонормирован
        gram = C.T @ C
        np.testing.assert_allclose(gram, np.eye(2), atol=1e-10)
    
    def test_consistency_with_projector(self):
        """Базис согласован с проектором: C @ C.T = P"""
        A = np.array([[1., 2.],
                      [3., 4.],
                      [5., 6.]])
        
        C = colspace_basis(A)
        P = colspace_projector(A)
        
        # Проектор через базис
        P_from_basis = C @ C.T if C.shape[1] > 0 else np.zeros((A.shape[0], A.shape[0]))
        
        np.testing.assert_allclose(P_from_basis, P, atol=1e-10)
    
    def test_complement_to_left_nullspace(self):
        """Colspace и left_nullspace образуют полный базис"""
        A = np.array([[1., 2.],
                      [2., 4.],
                      [3., 6.]])  # ранг 1
        
        C = colspace_basis(A)
        L = left_nullspace_basis(A)
        
        # Размерности: rank(A) + (m - rank(A)) = m
        self.assertEqual(C.shape[1] + L.shape[1], A.shape[0])
        
        # Объединённая матрица должна иметь полный ранг
        combined = np.hstack([C, L])
        rank = np.linalg.matrix_rank(combined)
        self.assertEqual(rank, A.shape[0])
    
    def test_orthogonality_with_left_nullspace(self):
        """Базисы colspace и left_nullspace ортогональны"""
        A = np.array([[1., 2., 3.],
                      [4., 5., 6.],
                      [7., 8., 9.]])  # ранг 2
        
        C = colspace_basis(A)
        L = left_nullspace_basis(A)
        
        # C^T @ L = 0
        if C.shape[1] > 0 and L.shape[1] > 0:
            cross_product = C.T @ L
            np.testing.assert_allclose(cross_product, np.zeros((C.shape[1], L.shape[1])), 
                                      atol=1e-10)
    
    def test_rank_one_matrix(self):
        """Матрица ранга 1"""
        A = np.array([[1.],
                      [2.],
                      [3.]])
        C = colspace_basis(A)
        
        # Пространство столбцов одномерное
        self.assertEqual(C.shape, (3, 1))
        
        # Базисный вектор нормирован
        self.assertAlmostEqual(np.linalg.norm(C), 1.0, places=10)
    
    def test_dimension(self):
        """Размерность базиса = (m, rank)"""
        A = np.array([[1., 2., 3.],
                      [4., 5., 6.]])  # 2x3, ранг 2
        C = colspace_basis(A)
        
        self.assertEqual(C.shape, (2, 2))


class TestLeftNullspaceProjector(unittest.TestCase):
    """Тесты для функции left_nullspace_projector"""
    
    def test_idempotence(self):
        """Проектор должен быть идемпотентным: P @ P = P"""
        A = np.array([[1., 2.],
                      [2., 4.],
                      [3., 6.]])
        P = left_nullspace_projector(A)
        
        # P @ P = P
        np.testing.assert_allclose(P @ P, P, atol=1e-10)
    
    def test_left_nullspace_property(self):
        """P @ A должно быть нулевой матрицей"""
        A = np.array([[1., 2.],
                      [2., 4.],
                      [3., 6.]])
        P = left_nullspace_projector(A)
        
        # P @ A = 0 (эквивалентно A^T @ P = 0)
        result = P @ A
        np.testing.assert_allclose(result, np.zeros_like(result), atol=1e-10)
    
    def test_symmetry(self):
        """Проектор должен быть симметричным для вещественных матриц"""
        A = np.array([[1., 2., 3.],
                      [4., 5., 6.]])
        P = left_nullspace_projector(A)
        
        # P = P.T
        np.testing.assert_allclose(P, P.T, atol=1e-10)
    
    def test_full_rank_rows(self):
        """Для матрицы полного ранга по строкам проектор должен быть нулевым"""
        A = np.array([[1., 0., 0.],
                      [0., 1., 0.]])  # 2x3, ранг 2 = m
        P = left_nullspace_projector(A)
        
        # Левое нуль-пространство пустое -> P = 0
        np.testing.assert_allclose(P, np.zeros((2, 2)), atol=1e-10)
    
    def test_zero_matrix(self):
        """Для нулевой матрицы проектор должен быть единичной матрицей"""
        A = np.zeros((3, 2))
        P = left_nullspace_projector(A)
        
        # Всё пространство R^m является левым нуль-пространством
        np.testing.assert_allclose(P, np.eye(3), atol=1e-10)
    
    def test_dimension(self):
        """Размерность проектора = m x m"""
        A = np.array([[1., 2., 3.],
                      [4., 5., 6.]])  # 2x3
        P = left_nullspace_projector(A)
        
        self.assertEqual(P.shape, (2, 2))


class TestLeftNullspaceBasis(unittest.TestCase):
    """Тесты для функции left_nullspace_basis"""
    
    def test_orthonormality(self):
        """Базис должен быть ортонормированным"""
        A = np.array([[1., 2., 3.],
                      [2., 4., 6.],
                      [3., 6., 9.]])  # ранг 1
        L = left_nullspace_basis(A)
        
        # L^T @ L = I
        gram = L.T @ L
        expected = np.eye(L.shape[1])
        np.testing.assert_allclose(gram, expected, atol=1e-10)
    
    def test_left_nullspace_property(self):
        """A^T @ L = 0"""
        A = np.array([[1., 2.],
                      [2., 4.],
                      [3., 6.]])
        L = left_nullspace_basis(A)
        
        # A^T @ L = 0
        result = A.T @ L
        np.testing.assert_allclose(result, np.zeros_like(result), atol=1e-10)
    
    def test_zero_matrix(self):
        """Нулевая матрица - полное пространство R^m"""
        A = np.zeros((3, 2))
        L = left_nullspace_basis(A)
        
        # Левое нуль-пространство = всё R³
        self.assertEqual(L.shape, (3, 3))
        
        # Базис ортонормирован
        gram = L.T @ L
        np.testing.assert_allclose(gram, np.eye(3), atol=1e-10)
    
    def test_full_rank_rows(self):
        """Матрица полного ранга по строкам"""
        A = np.array([[1., 0., 0.],
                      [0., 1., 0.]])  # 2x3, ранг 2 = m
        L = left_nullspace_basis(A)
        
        # Левое нуль-пространство пустое
        self.assertEqual(L.shape, (2, 0))
    
    def test_consistency_with_projector(self):
        """Базис согласован с проектором: L @ L.T = P"""
        A = np.array([[1., 2., 3.],
                      [2., 4., 6.],
                      [3., 6., 9.]])
        
        L = left_nullspace_basis(A)
        P = left_nullspace_projector(A)
        
        # Проектор через базис
        P_from_basis = L @ L.T if L.shape[1] > 0 else np.zeros((A.shape[0], A.shape[0]))
        
        np.testing.assert_allclose(P_from_basis, P, atol=1e-10)
    
    def test_equivalence_with_nullspace_of_transpose(self):
        """left_nullspace(A) = nullspace(A^T)"""
        A = np.array([[1., 2., 3.],
                      [2., 4., 6.],
                      [3., 6., 9.]])
        
        L = left_nullspace_basis(A)
        N_AT = nullspace_basis(A.T)
        
        # Размерности совпадают
        self.assertEqual(L.shape, N_AT.shape)
        
        # Подпространства совпадают (проверяем через проекторы)
        P_L = L @ L.T if L.shape[1] > 0 else np.zeros((A.shape[0], A.shape[0]))
        P_N = N_AT @ N_AT.T if N_AT.shape[1] > 0 else np.zeros((A.shape[0], A.shape[0]))
        
        np.testing.assert_allclose(P_L, P_N, atol=1e-10)
    
    def test_rank_deficient_square(self):
        """Квадратная вырожденная матрица"""
        A = np.array([[1., 2., 3.],
                      [2., 4., 6.],
                      [3., 6., 9.]])  # ранг 1
        L = left_nullspace_basis(A)
        
        # Размерность = m - rank = 3 - 1 = 2
        self.assertEqual(L.shape, (3, 2))
    
    def test_dimension(self):
        """Размерность базиса = (m, m - rank)"""
        A = np.array([[1., 2., 3.],
                      [4., 5., 6.]])  # 2x3, ранг 2
        L = left_nullspace_basis(A)
        
        # m - rank = 2 - 2 = 0
        self.assertEqual(L.shape, (2, 0))


class TestVectorProjector(unittest.TestCase):
    """Тесты для функции vector_projector"""
    
    def test_idempotence(self):
        """Проектор должен быть идемпотентным: P @ P = P"""
        u = np.array([1., 2., 3.])
        P = vector_projector(u)
        
        np.testing.assert_allclose(P @ P, P, atol=1e-10)
    
    def test_symmetry(self):
        """Проектор должен быть симметричным для вещественных векторов"""
        u = np.array([3., 4., 5.])
        P = vector_projector(u)
        
        np.testing.assert_allclose(P, P.T, atol=1e-10)
    
    def test_rank_one(self):
        """Проектор должен иметь ранг 1"""
        u = np.array([1., 2., 3.])
        P = vector_projector(u)
        
        rank = np.linalg.matrix_rank(P)
        self.assertEqual(rank, 1)
    
    def test_trace_one(self):
        """След проектора должен быть равен 1"""
        u = np.array([2., 3., 4.])
        P = vector_projector(u)
        
        trace = np.trace(P)
        self.assertAlmostEqual(trace, 1.0, places=10)
    
    def test_projection_on_x_axis(self):
        """Проекция на ось X"""
        u = np.array([1., 0., 0.])
        P = vector_projector(u)
        
        v = np.array([3., 4., 5.])
        result = P @ v
        
        expected = np.array([3., 0., 0.])
        np.testing.assert_allclose(result, expected, atol=1e-10)
    
    def test_projection_on_diagonal(self):
        """Проекция на диагональ (1,1,1)"""
        u = np.array([1., 1., 1.])
        P = vector_projector(u)
        
        v = np.array([6., 0., 0.])
        result = P @ v
        
        # Проекция [6,0,0] на [1,1,1] = (6/3)*[1,1,1] = [2,2,2]
        expected = np.array([2., 2., 2.])
        np.testing.assert_allclose(result, expected, atol=1e-10)
    
    def test_normalized_vector(self):
        """Проектор не зависит от нормы вектора"""
        u1 = np.array([1., 2., 3.])
        u2 = 5.0 * u1  # Масштабированный вектор
        
        P1 = vector_projector(u1)
        P2 = vector_projector(u2)
        
        np.testing.assert_allclose(P1, P2, atol=1e-10)
    
    def test_zero_vector_raises(self):
        """Нулевой вектор должен вызывать ошибку"""
        u = np.array([0., 0., 0.])
        
        with self.assertRaises(ValueError):
            vector_projector(u)
    
    def test_column_vector_input(self):
        """Работа с вектором-столбцом"""
        u = np.array([[1.], [2.], [3.]])
        P = vector_projector(u)
        
        self.assertEqual(P.shape, (3, 3))
        np.testing.assert_allclose(P @ P, P, atol=1e-10)
    
    def test_complex_vector(self):
        """Проектор для комплексного вектора"""
        u = np.array([1. + 1j, 2., 3.])
        P = vector_projector(u)
        
        # Эрмитовость для комплексных
        np.testing.assert_allclose(P, P.T.conj(), atol=1e-10)
        
        # Идемпотентность
        np.testing.assert_allclose(P @ P, P, atol=1e-10)


class TestSubspaceProjector(unittest.TestCase):
    """Тесты для функции subspace_projector"""
    
    def test_single_vector(self):
        """Проектор на одномерное подпространство = vector_projector"""
        u = np.array([1., 2., 3.])
        
        P1 = subspace_projector(u)
        P2 = vector_projector(u)
        
        np.testing.assert_allclose(P1, P2, atol=1e-10)
    
    def test_xy_plane(self):
        """Проектор на плоскость XY"""
        u1 = np.array([1., 0., 0.])
        u2 = np.array([0., 1., 0.])
        
        P = subspace_projector(u1, u2)
        
        # Проекция точки (3, 4, 5) на плоскость XY
        v = np.array([3., 4., 5.])
        result = P @ v
        expected = np.array([3., 4., 0.])
        
        np.testing.assert_allclose(result, expected, atol=1e-10)
    
    def test_diagonal_plane(self):
        """Проектор на плоскость через диагонали"""
        u1 = np.array([1., 1., 0.])
        u2 = np.array([0., 1., 1.])
        
        P = subspace_projector(u1, u2)
        
        # Проверка идемпотентности
        np.testing.assert_allclose(P @ P, P, atol=1e-10)
        
        # Проверка симметричности
        np.testing.assert_allclose(P, P.T, atol=1e-10)
        
        # Ранг должен быть 2
        rank = np.linalg.matrix_rank(P)
        self.assertEqual(rank, 2)
    
    def test_idempotence(self):
        """Проектор должен быть идемпотентным"""
        u1 = np.array([1., 2., 3., 4.])
        u2 = np.array([0., 1., 0., 1.])
        u3 = np.array([1., 0., 1., 0.])
        
        P = subspace_projector(u1, u2, u3)
        
        np.testing.assert_allclose(P @ P, P, atol=1e-10)
    
    def test_symmetry(self):
        """Проектор должен быть симметричным для вещественных векторов"""
        u1 = np.array([1., 2., 3.])
        u2 = np.array([4., 5., 6.])
        
        P = subspace_projector(u1, u2)
        
        np.testing.assert_allclose(P, P.T, atol=1e-10)
    
    def test_linearly_dependent_vectors(self):
        """Линейно зависимые векторы не увеличивают ранг"""
        u1 = np.array([1., 2., 3.])
        u2 = np.array([2., 4., 6.])  # u2 = 2 * u1
        
        P1 = subspace_projector(u1)
        P2 = subspace_projector(u1, u2)
        
        # Должны быть одинаковыми
        np.testing.assert_allclose(P1, P2, atol=1e-10)
    
    def test_orthogonal_vectors(self):
        """Ортогональные векторы образуют простой базис"""
        u1 = np.array([1., 0., 0.])
        u2 = np.array([0., 1., 0.])
        u3 = np.array([0., 0., 1.])
        
        P = subspace_projector(u1, u2, u3)
        
        # Должны покрывать всё пространство R³
        np.testing.assert_allclose(P, np.eye(3), atol=1e-10)
    
    def test_point_projection_on_plane(self):
        """Проекция точки на плоскость в 3D"""
        # Плоскость через точки: (1,0,0), (0,1,0), (0,0,0)
        # Направляющие векторы плоскости
        u1 = np.array([1., 0., 0.])
        u2 = np.array([0., 1., 0.])
        
        P = subspace_projector(u1, u2)
        
        # Точка вне плоскости
        point = np.array([2., 3., 7.])
        projected = P @ point
        
        # Проекция должна быть (2, 3, 0)
        expected = np.array([2., 3., 0.])
        np.testing.assert_allclose(projected, expected, atol=1e-10)
        
        # Повторная проекция не меняет точку (уже в плоскости)
        np.testing.assert_allclose(P @ projected, projected, atol=1e-10)
    
    def test_arbitrary_plane_in_3d(self):
        """Проекция на произвольную плоскость в 3D"""
        # Плоскость с нормалью [1, 1, 1] через начало координат
        # Два ортогональных вектора в этой плоскости:
        u1 = np.array([1., -1., 0.])
        u2 = np.array([1., 1., -2.])
        
        P = subspace_projector(u1, u2)
        
        # Проверяем, что нормаль проецируется в ноль
        normal = np.array([1., 1., 1.])
        projected = P @ normal
        
        # Проекция нормали на плоскость = 0
        np.testing.assert_allclose(np.linalg.norm(projected), 0.0, atol=1e-10)
    
    def test_rank_of_projector(self):
        """Ранг проектора = размерность подпространства"""
        u1 = np.array([1., 0., 0., 0.])
        u2 = np.array([0., 1., 0., 0.])
        
        P = subspace_projector(u1, u2)
        
        rank = np.linalg.matrix_rank(P)
        self.assertEqual(rank, 2)
    
    def test_trace_equals_rank(self):
        """След проектора = ранг подпространства"""
        u1 = np.array([1., 0., 0., 0.])
        u2 = np.array([0., 1., 0., 0.])
        u3 = np.array([0., 0., 1., 0.])
        
        P = subspace_projector(u1, u2, u3)
        
        trace = np.trace(P)
        self.assertAlmostEqual(trace, 3.0, places=10)
    
    def test_complex_vectors(self):
        """Проектор для комплексных векторов"""
        u1 = np.array([1. + 1j, 0., 0.])
        u2 = np.array([0., 1., 0.])
        
        P = subspace_projector(u1, u2)
        
        # Эрмитовость
        np.testing.assert_allclose(P, P.T.conj(), atol=1e-10)
        
        # Идемпотентность
        np.testing.assert_allclose(P @ P, P, atol=1e-10)
    
    def test_no_vectors_raises(self):
        """Отсутствие векторов должно вызывать ошибку"""
        with self.assertRaises(ValueError):
            subspace_projector()
    
    def test_normalized_vectors(self):
        """Проектор не зависит от нормы векторов"""
        u1 = np.array([1., 2., 3.])
        u2 = np.array([4., 5., 6.])
        
        P1 = subspace_projector(u1, u2)
        P2 = subspace_projector(5*u1, 10*u2)
        
        np.testing.assert_allclose(P1, P2, atol=1e-10)
    
    def test_distance_to_plane(self):
        """Расстояние от точки до плоскости через проектор"""
        # Плоскость XY
        u1 = np.array([1., 0., 0.])
        u2 = np.array([0., 1., 0.])
        P = subspace_projector(u1, u2)
        
        # Точка над плоскостью
        point = np.array([3., 4., 5.])
        projected = P @ point
        
        # Расстояние = длина компоненты вне плоскости
        distance = np.linalg.norm(point - projected)
        self.assertAlmostEqual(distance, 5.0, places=10)


class TestOrthogonalComplement(unittest.TestCase):
    """Тесты для функции orthogonal_complement"""
    
    def test_sum_is_identity(self):
        """P + P_perp = I"""
        P = subspace_projector([1., 0., 0.], [0., 1., 0.])
        P_perp = orthogonal_complement(P)
        
        I = np.eye(3)
        np.testing.assert_allclose(P + P_perp, I, atol=1e-10)
    
    def test_double_complement(self):
        """Дополнение дополнения = исходное подпространство"""
        P = vector_projector([1., 2., 3.])
        P_perp = orthogonal_complement(P)
        P_perp_perp = orthogonal_complement(P_perp)
        
        np.testing.assert_allclose(P, P_perp_perp, atol=1e-10)
    
    def test_orthogonality(self):
        """P @ P_perp = 0 (подпространства ортогональны)"""
        P = subspace_projector([1., 0., 0.], [0., 1., 0.])
        P_perp = orthogonal_complement(P)
        
        zero = np.zeros((3, 3))
        np.testing.assert_allclose(P @ P_perp, zero, atol=1e-10)
        np.testing.assert_allclose(P_perp @ P, zero, atol=1e-10)
    
    def test_dimension_sum(self):
        """dim(V) + dim(V_perp) = n"""
        P = subspace_projector([1., 0., 0.])  # 1D
        P_perp = orthogonal_complement(P)
        
        dim_v = subspace_dimension(P)
        dim_v_perp = subspace_dimension(P_perp)
        
        self.assertEqual(dim_v + dim_v_perp, 3)


class TestIsInSubspace(unittest.TestCase):
    """Тесты для функции is_in_subspace"""
    
    def test_vector_in_xy_plane(self):
        """Вектор в плоскости XY"""
        P_xy = subspace_projector([1., 0., 0.], [0., 1., 0.])
        
        v_in = np.array([3., 4., 0.])
        v_out = np.array([3., 4., 5.])
        
        self.assertTrue(is_in_subspace(v_in, P_xy))
        self.assertFalse(is_in_subspace(v_out, P_xy))
    
    def test_zero_vector(self):
        """Нулевой вектор всегда в подпространстве"""
        P = subspace_projector([1., 2., 3.])
        
        zero = np.array([0., 0., 0.])
        self.assertTrue(is_in_subspace(zero, P))
    
    def test_basis_vectors(self):
        """Базисные векторы должны быть в подпространстве"""
        u1 = np.array([1., 2., 3.])
        u2 = np.array([4., 5., 6.])
        
        P = subspace_projector(u1, u2)
        
        self.assertTrue(is_in_subspace(u1, P))
        self.assertTrue(is_in_subspace(u2, P))
        self.assertTrue(is_in_subspace(2*u1 + 3*u2, P))
    
    def test_orthogonal_vector(self):
        """Вектор, ортогональный подпространству, не в нём (кроме 0)"""
        P_xy = subspace_projector([1., 0., 0.], [0., 1., 0.])
        
        z_axis = np.array([0., 0., 1.])
        self.assertFalse(is_in_subspace(z_axis, P_xy))
    
    def test_custom_tolerance(self):
        """Проверка с кастомным порогом"""
        P = vector_projector([1., 0., 0.])
        
        # Почти в подпространстве
        v = np.array([1., 1e-8, 0.])
        
        self.assertTrue(is_in_subspace(v, P, tol=1e-6))
        self.assertFalse(is_in_subspace(v, P, tol=1e-10))


class TestSubspaceDimension(unittest.TestCase):
    """Тесты для функции subspace_dimension"""
    
    def test_line_dimension(self):
        """Размерность прямой = 1"""
        P = vector_projector([1., 2., 3.])
        self.assertEqual(subspace_dimension(P), 1)
    
    def test_plane_dimension(self):
        """Размерность плоскости = 2"""
        P = subspace_projector([1., 0., 0.], [0., 1., 0.])
        self.assertEqual(subspace_dimension(P), 2)
    
    def test_full_space_dimension(self):
        """Размерность всего пространства = n"""
        I = np.eye(4)
        self.assertEqual(subspace_dimension(I), 4)
    
    def test_zero_space_dimension(self):
        """Размерность нулевого подпространства = 0"""
        P = np.zeros((3, 3))
        self.assertEqual(subspace_dimension(P), 0)
    
    def test_dimension_equals_trace(self):
        """Для ортогонального проектора dim = trace"""
        P = subspace_projector([1., 0., 0.], [0., 1., 0.])
        
        dim = subspace_dimension(P)
        trace = int(np.round(np.trace(P)))
        
        self.assertEqual(dim, trace)
    
    def test_linearly_dependent_vectors(self):
        """Линейно зависимые векторы не увеличивают размерность"""
        u = np.array([1., 2., 3.])
        
        P1 = vector_projector(u)
        P2 = subspace_projector(u, 2*u, 3*u)
        
        self.assertEqual(subspace_dimension(P2), 1)


class TestGramSchmidt(unittest.TestCase):
    """Тесты для функции gram_schmidt"""
    
    def test_orthonormality(self):
        """Результат должен быть ортонормированным"""
        v1 = np.array([3., 4., 0.])
        v2 = np.array([1., 0., 1.])
        
        Q = gram_schmidt(v1, v2)
        
        # Q.T @ Q = I
        np.testing.assert_allclose(Q.T @ Q, np.eye(2), atol=1e-10)
    
    def test_single_vector(self):
        """Ортогонализация одного вектора = его нормализация"""
        v = np.array([3., 4., 0.])
        
        Q = gram_schmidt(v)
        
        # Один столбец
        self.assertEqual(Q.shape, (3, 1))
        
        # Норма = 1
        self.assertAlmostEqual(np.linalg.norm(Q), 1.0, places=10)
        
        # Направление сохраняется
        self.assertAlmostEqual(np.abs(np.dot(Q.flatten(), v) / np.linalg.norm(v)), 1.0, places=10)
    
    def test_linearly_dependent_vectors(self):
        """Линейно зависимые векторы дают меньше базисных векторов"""
        v1 = np.array([1., 0., 0.])
        v2 = np.array([2., 0., 0.])  # v2 = 2*v1
        v3 = np.array([3., 0., 0.])  # v3 = 3*v1
        
        Q = gram_schmidt(v1, v2, v3)
        
        # Только 1 независимый вектор
        self.assertEqual(Q.shape, (3, 1))
    
    def test_standard_basis(self):
        """Стандартный базис остаётся ортонормированным"""
        e1 = np.array([1., 0., 0.])
        e2 = np.array([0., 1., 0.])
        e3 = np.array([0., 0., 1.])
        
        Q = gram_schmidt(e1, e2, e3)
        
        self.assertEqual(Q.shape, (3, 3))
        
        # Ортонормированность
        np.testing.assert_allclose(Q.T @ Q, np.eye(3), atol=1e-10)
    
    def test_plane_vectors(self):
        """Два вектора в плоскости дают базис плоскости"""
        v1 = np.array([1., 0., 0.])
        v2 = np.array([1., 1., 0.])
        
        Q = gram_schmidt(v1, v2)
        
        # 2 независимых вектора
        self.assertEqual(Q.shape, (3, 2))
        
        # Оба вектора в плоскости XY (z = 0)
        np.testing.assert_allclose(Q[2, :], 0, atol=1e-10)
    
    def test_first_vector_preserved(self):
        """Первый вектор сохраняет направление (только нормализуется)"""
        v1 = np.array([3., 4., 0.])
        v2 = np.array([1., 0., 1.])
        
        Q = gram_schmidt(v1, v2)
        
        # Первый вектор базиса параллелен v1
        v1_normalized = v1 / np.linalg.norm(v1)
        np.testing.assert_allclose(np.abs(Q[:, 0]), np.abs(v1_normalized), atol=1e-10)


class TestOrthogonalizeSVD(unittest.TestCase):
    """Тесты для функции orthogonalize_svd"""
    
    def test_orthonormality(self):
        """Результат должен быть ортонормированным"""
        v1 = np.array([3., 4., 0.])
        v2 = np.array([1., 0., 1.])
        
        Q = orthogonalize_svd(v1, v2)
        
        # Q.T @ Q = I
        np.testing.assert_allclose(Q.T @ Q, np.eye(2), atol=1e-10)
    
    def test_single_vector(self):
        """Ортогонализация одного вектора"""
        v = np.array([3., 4., 0.])
        
        Q = orthogonalize_svd(v)
        
        # Один столбец
        self.assertEqual(Q.shape, (3, 1))
        
        # Норма = 1
        self.assertAlmostEqual(np.linalg.norm(Q), 1.0, places=10)
    
    def test_linearly_dependent_vectors(self):
        """Линейно зависимые векторы дают меньше базисных векторов"""
        v1 = np.array([1., 0., 0.])
        v2 = np.array([2., 0., 0.])  # v2 = 2*v1
        v3 = np.array([3., 0., 0.])  # v3 = 3*v1
        
        Q = orthogonalize_svd(v1, v2, v3)
        
        # Только 1 независимый вектор
        self.assertEqual(Q.shape, (3, 1))


class TestOrthogonalizeComparison(unittest.TestCase):
    """Сравнение методов ортогонализации"""
    
    def test_same_span(self):
        """Оба метода дают базис одного и того же подпространства"""
        v1 = np.array([1., 2., 3.])
        v2 = np.array([4., 5., 6.])
        
        Q_gs = gram_schmidt(v1, v2)
        Q_svd = orthogonalize_svd(v1, v2)
        
        # Проекторы должны быть одинаковыми
        P_gs = Q_gs @ Q_gs.T
        P_svd = Q_svd @ Q_svd.T
        
        np.testing.assert_allclose(P_gs, P_svd, atol=1e-10)
    
    def test_orthogonal_vectors(self):
        """Для уже ортогональных векторов оба метода дают похожий результат"""
        v1 = np.array([1., 0., 0.])
        v2 = np.array([0., 1., 0.])
        
        Q_gs = gram_schmidt(v1, v2)
        Q_svd = orthogonalize_svd(v1, v2)
        
        # Оба должны дать ортонормированный базис
        np.testing.assert_allclose(Q_gs.T @ Q_gs, np.eye(2), atol=1e-10)
        np.testing.assert_allclose(Q_svd.T @ Q_svd, np.eye(2), atol=1e-10)
        
        # Проекторы идентичны
        P_gs = Q_gs @ Q_gs.T
        P_svd = Q_svd @ Q_svd.T
        np.testing.assert_allclose(P_gs, P_svd, atol=1e-10)
    
    def test_three_vectors_in_plane(self):
        """Три вектора в плоскости -> базис размерности 2"""
        v1 = np.array([1., 0., 0.])
        v2 = np.array([0., 1., 0.])
        v3 = np.array([1., 1., 0.])  # Линейная комбинация v1 и v2
        
        Q_gs = gram_schmidt(v1, v2, v3)
        Q_svd = orthogonalize_svd(v1, v2, v3)
        
        # Оба должны дать 2D базис
        self.assertEqual(Q_gs.shape, (3, 2))
        self.assertEqual(Q_svd.shape, (3, 2))
        
        # Проекторы совпадают
        P_gs = Q_gs @ Q_gs.T
        P_svd = Q_svd @ Q_svd.T
        np.testing.assert_allclose(P_gs, P_svd, atol=1e-10)
    
    def test_wrapper_function(self):
        """Тест универсальной функции orthogonalize"""
        v1 = np.array([1., 2., 3.])
        v2 = np.array([4., 5., 6.])
        
        Q_gs = orthogonalize(v1, v2, method='gram_schmidt')
        Q_svd = orthogonalize(v1, v2, method='svd')
        Q_default = orthogonalize(v1, v2)  # По умолчанию SVD
        
        # Проверяем, что методы вызываются правильно
        np.testing.assert_allclose(Q_default, Q_svd, atol=1e-10)
        
        # Проекторы совпадают
        P_gs = Q_gs @ Q_gs.T
        P_svd = Q_svd @ Q_svd.T
        np.testing.assert_allclose(P_gs, P_svd, atol=1e-10)
    
    def test_nearly_collinear_vectors(self):
        """SVD более стабилен для почти коллинеарных векторов"""
        v1 = np.array([1., 0., 0.])
        v2 = np.array([1., 1e-10, 0.])  # Почти параллелен v1
        
        Q_gs = gram_schmidt(v1, v2)
        Q_svd = orthogonalize_svd(v1, v2)
        
        # Оба должны распознать независимость (но очень малую)
        # SVD обычно более стабилен в определении ранга
        
        # Проверяем ортонормированность обоих
        if Q_gs.shape[1] > 0:
            np.testing.assert_allclose(Q_gs.T @ Q_gs, np.eye(Q_gs.shape[1]), atol=1e-8)
        if Q_svd.shape[1] > 0:
            np.testing.assert_allclose(Q_svd.T @ Q_svd, np.eye(Q_svd.shape[1]), atol=1e-10)


class TestOrthogonalize(unittest.TestCase):
    """Тесты для старых тестов orthogonalize (теперь тестируем дефолтный SVD)"""
    
    def test_span_preservation(self):
        """Ортогонализация сохраняет линейную оболочку"""
        v1 = np.array([3., 4., 0.])
        v2 = np.array([1., 7., 0.])
        
        Q = orthogonalize(v1, v2)
        
        # Исходные векторы должны выражаться через Q
        c1 = Q.T @ v1.reshape(-1, 1)
        c2 = Q.T @ v2.reshape(-1, 1)
        
        reconstructed_v1 = Q @ c1
        reconstructed_v2 = Q @ c2
        
        np.testing.assert_allclose(reconstructed_v1.flatten(), v1, atol=1e-10)
        np.testing.assert_allclose(reconstructed_v2.flatten(), v2, atol=1e-10)
    
    def test_zero_vector(self):
        """Нулевые векторы игнорируются"""
        v1 = np.array([1., 0., 0.])
        v2 = np.array([0., 0., 0.])
        
        Q = orthogonalize(v1, v2)
        
        # Только 1 ненулевой вектор
        self.assertEqual(Q.shape, (3, 1))
    
    def test_all_zero_vectors(self):
        """Все нулевые векторы дают пустой базис"""
        v1 = np.array([0., 0., 0.])
        v2 = np.array([0., 0., 0.])
        
        Q = orthogonalize(v1, v2)
        
        # Пустой базис
        self.assertEqual(Q.shape, (3, 0))
    
    def test_no_vectors_raises(self):
        """Отсутствие векторов вызывает ошибку"""
        with self.assertRaises(ValueError):
            orthogonalize()
    
    def test_consistency_with_subspace_projector(self):
        """Результат согласован с subspace_projector"""
        v1 = np.array([1., 2., 3.])
        v2 = np.array([4., 5., 6.])
        
        Q = orthogonalize(v1, v2)
        P_from_Q = Q @ Q.T
        P_from_subspace = subspace_projector(v1, v2)
        
        np.testing.assert_allclose(P_from_Q, P_from_subspace, atol=1e-10)


class TestIsProjector(unittest.TestCase):
    """Тесты для функции is_projector - проверка свойств проектора."""
    
    def test_valid_projector_vector(self):
        """Проектор на вектор - валидный проектор"""
        P = vector_projector([1., 2., 3.])
        self.assertTrue(is_projector(P))
    
    def test_valid_projector_subspace(self):
        """Проектор на подпространство - валидный проектор"""
        P = subspace_projector([1., 0., 0.], [0., 1., 0.])
        self.assertTrue(is_projector(P))
    
    def test_identity_is_projector(self):
        """Единичная матрица - валидный проектор"""
        I = np.eye(3)
        self.assertTrue(is_projector(I))
    
    def test_zero_is_projector(self):
        """Нулевая матрица - валидный проектор (на {0})"""
        Z = np.zeros((3, 3))
        self.assertTrue(is_projector(Z))
    
    def test_non_square_not_projector(self):
        """Неквадратная матрица - не проектор"""
        A = np.array([[1, 0], [0, 1], [0, 0]])
        self.assertFalse(is_projector(A))
    
    def test_non_idempotent_not_projector(self):
        """Не идемпотентная матрица - не проектор"""
        # Матрица поворота не идемпотентна
        theta = np.pi / 4
        R = np.array([[np.cos(theta), -np.sin(theta)],
                      [np.sin(theta), np.cos(theta)]])
        self.assertFalse(is_projector(R))
    
    def test_non_hermitian_not_projector(self):
        """Не эрмитова матрица - не проектор"""
        # Идемпотентна, но не симметрична
        A = np.array([[1, 1], [0, 0]])
        # A @ A = A, но A.T != A
        self.assertFalse(is_projector(A))
    
    def test_arbitrary_matrix_not_projector(self):
        """Произвольная матрица - не проектор"""
        A = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        self.assertFalse(is_projector(A))
    
    def test_all_projector_functions_produce_valid_projectors(self):
        """Все функции создания проекторов возвращают валидные проекторы"""
        A = np.array([[1, 2, 3], [4, 5, 6]])
        
        P_null = nullspace_projector(A)
        P_row = rowspace_projector(A)
        P_col = colspace_projector(A)
        P_left = left_nullspace_projector(A)
        
        self.assertTrue(is_projector(P_null))
        self.assertTrue(is_projector(P_row))
        self.assertTrue(is_projector(P_col))
        self.assertTrue(is_projector(P_left))
    
    def test_complementary_projectors(self):
        """Проверка ортогонального дополнения"""
        P = subspace_projector([1., 0., 0.], [0., 1., 0.])
        P_perp = orthogonal_complement(P)
        
        self.assertTrue(is_projector(P))
        self.assertTrue(is_projector(P_perp))


class TestProjectorBasis(unittest.TestCase):
    """Тесты для функции projector_basis - извлечение базиса из проектора."""
    
    def test_recovers_projector(self):
        """Q @ Q.T = P (восстановление проектора из базиса)"""
        P = subspace_projector([1., 0., 0.], [0., 1., 0.])
        Q = projector_basis(P)
        
        P_reconstructed = Q @ Q.T
        np.testing.assert_allclose(P_reconstructed, P, atol=1e-10)
    
    def test_basis_orthonormal(self):
        """Q.T @ Q = I (базис ортонормирован)"""
        P = subspace_projector([1., 2., 3.], [4., 5., 7.])
        Q = projector_basis(P)
        
        identity = Q.T @ Q
        k = Q.shape[1]
        np.testing.assert_allclose(identity, np.eye(k), atol=1e-10)
    
    def test_dimension(self):
        """Количество векторов базиса = размерность подпространства"""
        P = subspace_projector([1., 0., 0., 0.], [0., 1., 0., 0.], [0., 0., 1., 0.])
        Q = projector_basis(P)
        
        self.assertEqual(Q.shape[1], 3)  # 3 независимых вектора
    
    def test_zero_projector(self):
        """Для нулевого проектора возвращает пустой базис"""
        P = np.zeros((4, 4))
        Q = projector_basis(P)
        
        self.assertEqual(Q.shape, (4, 0))
    
    def test_identity_projector(self):
        """Для единичного проектора возвращает полный базис"""
        n = 3
        P = np.eye(n)
        Q = projector_basis(P)
        
        self.assertEqual(Q.shape[1], n)
        np.testing.assert_allclose(Q @ Q.T, P, atol=1e-10)
    
    def test_vector_projector(self):
        """Для проектора на вектор возвращает нормированный вектор"""
        v = np.array([3., 4., 0.])
        P = vector_projector(v)
        Q = projector_basis(P)
        
        self.assertEqual(Q.shape, (3, 1))
        # Базис должен быть единичным вектором
        np.testing.assert_allclose(np.linalg.norm(Q), 1.0, atol=1e-10)
        # Восстановление проектора
        np.testing.assert_allclose(Q @ Q.T, P, atol=1e-10)


class TestSubspaceIntersection(unittest.TestCase):
    """Тесты для функции subspace_intersection"""
    
    def test_xy_and_xz_planes(self):
        """Пересечение плоскости XY и плоскости XZ = ось X"""
        P_xy = subspace_projector([1., 0., 0.], [0., 1., 0.])
        P_xz = subspace_projector([1., 0., 0.], [0., 0., 1.])
        
        P_x = subspace_intersection(P_xy, P_xz)
        P_x_expected = vector_projector([1., 0., 0.])
        
        np.testing.assert_allclose(P_x, P_x_expected, atol=1e-10)
    
    def test_intersection_dimension(self):
        """Размерность пересечения ≤ min(dim(V1), dim(V2))"""
        P1 = subspace_projector([1., 0., 0.], [0., 1., 0.])  # 2D
        P2 = subspace_projector([1., 0., 0.], [0., 0., 1.])  # 2D
        
        P_int = subspace_intersection(P1, P2)
        dim_int = subspace_dimension(P_int)
        
        self.assertLessEqual(dim_int, 2)
        self.assertEqual(dim_int, 1)  # Пересечение = ось X
    
    def test_orthogonal_subspaces(self):
        """Пересечение ортогональных подпространств = {0}"""
        P_x = vector_projector([1., 0., 0.])
        P_y = vector_projector([0., 1., 0.])
        
        P_int = subspace_intersection(P_x, P_y)
        
        # Должен быть нулевой проектор
        np.testing.assert_allclose(P_int, np.zeros((3, 3)), atol=1e-10)
    
    def test_idempotence(self):
        """Проектор пересечения идемпотентен"""
        P1 = subspace_projector([1., 1., 0.], [0., 1., 1.])
        P2 = subspace_projector([1., 0., 1.], [1., 1., 0.])
        
        P_int = subspace_intersection(P1, P2)
        
        np.testing.assert_allclose(P_int @ P_int, P_int, atol=1e-10)
    
    def test_self_intersection(self):
        """V ∩ V = V"""
        P = subspace_projector([1., 2., 3.], [4., 5., 6.])
        P_int = subspace_intersection(P, P)
        
        np.testing.assert_allclose(P_int, P, atol=1e-10)
    
    def test_symmetry(self):
        """V1 ∩ V2 = V2 ∩ V1 (коммутативность)"""
        P1 = subspace_projector([1., 1., 0.])
        P2 = subspace_projector([1., 0., 1.])
        
        P_int_12 = subspace_intersection(P1, P2)
        P_int_21 = subspace_intersection(P2, P1)
        
        np.testing.assert_allclose(P_int_12, P_int_21, atol=1e-10)
    
    def test_intersection_in_both_spaces(self):
        """Векторы из пересечения лежат в обоих подпространствах"""
        P1 = subspace_projector([1., 0., 0.], [0., 1., 0.])  # XY
        P2 = subspace_projector([1., 0., 0.], [0., 0., 1.])  # XZ
        
        P_int = subspace_intersection(P1, P2)
        
        # Любой вектор из пересечения должен остаться неизменным при проекции на V1 и V2
        v = np.array([5., 0., 0.])  # Вектор вдоль X (в пересечении)
        v_proj_int = P_int @ v
        
        # Проверяем, что проекция на пересечение даёт вектор в V1 и V2
        np.testing.assert_allclose(P1 @ v_proj_int, v_proj_int, atol=1e-10)
        np.testing.assert_allclose(P2 @ v_proj_int, v_proj_int, atol=1e-10)
    
    def test_three_planes_intersection(self):
        """Пересечение трёх координатных плоскостей = начало координат"""
        P_xy = subspace_projector([1., 0., 0.], [0., 1., 0.])
        P_xz = subspace_projector([1., 0., 0.], [0., 0., 1.])
        P_yz = subspace_projector([0., 1., 0.], [0., 0., 1.])
        
        # XY ∩ XZ = ось X
        P_x = subspace_intersection(P_xy, P_xz)
        
        # (XY ∩ XZ) ∩ YZ = X ∩ YZ = {0}
        P_zero = subspace_intersection(P_x, P_yz)
        
        np.testing.assert_allclose(P_zero, np.zeros((3, 3)), atol=1e-10)
    
    def test_contained_subspace(self):
        """Если V1 ⊂ V2, то V1 ∩ V2 = V1"""
        # Ось X ⊂ Плоскость XY
        P_x = vector_projector([1., 0., 0.])
        P_xy = subspace_projector([1., 0., 0.], [0., 1., 0.])
        
        P_int = subspace_intersection(P_x, P_xy)
        
        np.testing.assert_allclose(P_int, P_x, atol=1e-10)
    
    def test_diagonal_planes(self):
        """Пересечение диагональных плоскостей"""
        # Плоскость z = 0
        P1 = subspace_projector([1., 0., 0.], [0., 1., 0.])
        
        # Плоскость x + y + z = 0
        P2 = orthogonal_complement(vector_projector([1., 1., 1.]))
        
        P_int = subspace_intersection(P1, P2)
        
        # Пересечение - прямая x + y = 0, z = 0
        # Проверяем размерность
        dim_int = subspace_dimension(P_int)
        self.assertEqual(dim_int, 1)
        
        # Проверяем, что вектор [1, -1, 0] в пересечении
        v = np.array([1., -1., 0.])
        v_proj = P_int @ v
        np.testing.assert_allclose(v_proj / np.linalg.norm(v_proj), 
                                   v / np.linalg.norm(v), atol=1e-10)


    def test_affine_projector(self):
        C = np.array([[0., 0., 1.]])  # Нормаль к плоскости XY
        b = np.array([1.])     # Смещение вдоль Z

        A, B = affine_projector(C, b)

        x = np.array([2., 3., 5.])
        x_proj = x - (A @ x - B)  # Проекция на плоскость XY + смещение вдоль Z
        np.testing.assert_allclose(x_proj, np.array([2., 3., 1.]), atol=1e-10)
        
    def test_affine_projector_2(self):
        C = np.array([[0., 0., 1.],
                      [0., 1., 0.]])  
        b = np.array([1., 1.])     # Смещение вдоль Z

        A, B = affine_projector(C, b)

        x = np.array([2., 3., 5.])
        x_proj = x - (A @ x - B)  # Проекция на плоскость XY + смещение вдоль Z
        np.testing.assert_allclose(x_proj, np.array([2., 1., 1.]), atol=1e-10)



if __name__ == '__main__':
    unittest.main()
