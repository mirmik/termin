<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/mechanic.py</title>
</head>
<body>
<pre><code>
#!/usr/bin/env python3
&quot;&quot;&quot;
Простейшие конечные элементы для механики.

Реализованы классические элементы, которые изучаются в институте:
- Стержневой элемент (bar/truss) - работает на растяжение/сжатие
- Балочный элемент (beam) - работает на изгиб
- Плоский треугольный элемент - для плоско-напряженного состояния
&quot;&quot;&quot;

import numpy as np
from typing import List, Dict
from .assembler import Contribution, Variable

# Optional:
from typing import Optional


class BarElement(Contribution):
    &quot;&quot;&quot;
    Стержневой (ферменный) конечный элемент.
    
    Работает только на растяжение/сжатие (нет изгиба).
    Имеет 2 узла, каждый узел имеет перемещения в 1D, 2D или 3D.
    
    Матрица жесткости в локальных координатах (вдоль стержня):
    K_local = (E*A/L) * [[1, -1],
                          [-1, 1]]
    
    где:
    E - модуль Юнга
    A - площадь поперечного сечения
    L - длина элемента
    &quot;&quot;&quot;
    
    def __init__(self, 
                 node1: Variable, 
                 node2: Variable,
                 E: float,
                 A: float,
                 coord1: np.ndarray,
                 coord2: np.ndarray):
        &quot;&quot;&quot;
        Args:
            node1: Переменная перемещений первого узла (размер 1, 2 или 3)
            node2: Переменная перемещений второго узла (размер 1, 2 или 3)
            E: Модуль Юнга (модуль упругости) [Па]
            A: Площадь поперечного сечения [м²]
            coord1: Координаты первого узла [м]
            coord2: Координаты второго узла [м]
        &quot;&quot;&quot;
        self.node1 = node1
        self.node2 = node2
        self.E = E
        self.A = A
        self.coord1 = np.array(coord1, dtype=float)
        self.coord2 = np.array(coord2, dtype=float)
        
        # Проверка размерностей
        if node1.size != node2.size:
            raise ValueError(&quot;Узлы должны иметь одинаковую размерность&quot;)
        
        if len(self.coord1) != len(self.coord2):
            raise ValueError(&quot;Координаты узлов должны иметь одинаковую размерность&quot;)
        
        if node1.size != len(self.coord1):
            raise ValueError(f&quot;Размерность узла {node1.size} не соответствует &quot;
                           f&quot;размерности координат {len(self.coord1)}&quot;)

        super().__init__(variables=[node1, node2])
        
        # Вычислить геометрические параметры
        self._compute_geometry()
    
    def _compute_geometry(self):
        &quot;&quot;&quot;Вычислить длину и направляющие косинусы&quot;&quot;&quot;
        # Вектор вдоль стержня
        dx = self.coord2 - self.coord1
        
        # Длина
        self.L = np.linalg.norm(dx)
        if self.L &lt; 1e-10:
            raise ValueError(&quot;Длина элемента слишком мала или равна нулю&quot;)
        
        # Направляющие косинусы (единичный вектор)
        self.direction = dx / self.L
        
        # Коэффициент жесткости
        self.k = self.E * self.A / self.L
    
    def _get_local_stiffness(self) -&gt; np.ndarray:
        &quot;&quot;&quot;
        Локальная матрица жесткости (вдоль оси стержня)
        Размер 2x2 для одномерной задачи
        &quot;&quot;&quot;
        k = self.k
        K_local_1d = np.array([
            [ k, -k],
            [-k,  k]
        ])
        return K_local_1d
    
    def _get_transformation_matrix(self) -&gt; np.ndarray:
        &quot;&quot;&quot;
        Матрица преобразования из глобальных координат в локальные
        
        Для 1D: T = [1, 1] (тривиальное преобразование)
        Для 2D: T = [cos, sin, cos, sin]
        Для 3D: T = [cx, cy, cz, cx, cy, cz]
        
        где c - направляющие косинусы
        &quot;&quot;&quot;
        dim = self.node1.size
        
        if dim == 1:
            # 1D - нет преобразования
            return np.array([1, 1])
        
        elif dim == 2:
            # 2D - cos и sin угла
            c = self.direction[0]  # cos
            s = self.direction[1]  # sin
            return np.array([c, s, c, s])
        
        elif dim == 3:
            # 3D - направляющие косинусы
            cx, cy, cz = self.direction
            return np.array([cx, cy, cz, cx, cy, cz])
        
        else:
            raise ValueError(f&quot;Неподдерживаемая размерность: {dim}&quot;)
    
    def _get_global_stiffness(self) -&gt; np.ndarray:
        &quot;&quot;&quot;
        Глобальная матрица жесткости
        
        K_global строится из направляющих косинусов
        &quot;&quot;&quot;
        dim = self.node1.size
        k = self.k
        
        if dim == 1:
            # 1D случай - просто локальная матрица
            K_global = k * np.array([
                [ 1, -1],
                [-1,  1]
            ])
        else:
            # 2D и 3D: K = k * c * c^T, где c = [l1, l2, ..., -l1, -l2, ...]
            # l - направляющие косинусы
            c = np.zeros(2 * dim)
            c[:dim] = self.direction
            c[dim:] = -self.direction
            
            # K = k * c * c^T
            K_global = k * np.outer(c, c)
        
        return K_global
    
    def contribute_to_stiffness(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):
        K_global = self._get_global_stiffness()
        
        # Получить глобальные индексы
        indices1 = index_map[self.node1]
        indices2 = index_map[self.node2]
        global_indices = indices1 + indices2
        
        # Добавить в глобальную матрицу
        for i, gi in enumerate(global_indices):
            for j, gj in enumerate(global_indices):
                A[gi, gj] += K_global[i, j]
    
    def contribute_to_load(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):
        # Стержневой элемент без распределенной нагрузки не вносит вклад в b
        pass
    
    def get_stress(self, u1: np.ndarray, u2: np.ndarray) -&gt; float:
        &quot;&quot;&quot;
        Вычислить напряжение в стержне по перемещениям узлов
        
        Args:
            u1: Вектор перемещений узла 1
            u2: Вектор перемещений узла 2
        
        Returns:
            Напряжение sigma [Па] (положительное - растяжение, отрицательное - сжатие)
        &quot;&quot;&quot;
        # Удлинение в направлении стержня
        delta_u = u2 - u1
        elongation = np.dot(delta_u, self.direction)
        
        # Деформация
        strain = elongation / self.L
        
        # Напряжение
        stress = self.E * strain
        
        return stress
    
    def get_force(self, u1: np.ndarray, u2: np.ndarray) -&gt; float:
        &quot;&quot;&quot;
        Вычислить силу в стержне
        
        Returns:
            Сила N [Н] (положительная - растяжение)
        &quot;&quot;&quot;
        stress = self.get_stress(u1, u2)
        force = stress * self.A
        return force


class BeamElement2D(Contribution):
    &quot;&quot;&quot;
    Балочный элемент Эйлера-Бернулли для плоской задачи.
    
    Работает на изгиб в плоскости. Каждый узел имеет 2 степени свободы:
    - v: прогиб (перемещение перпендикулярно оси)
    - theta: угол поворота сечения
    
    Матрица жесткости 4x4 (2 узла × 2 DOF на узел).
    
    Предположения:
    - Малые деформации
    - Гипотеза плоских сечений
    - Пренебрегаем деформациями сдвига (теория Эйлера-Бернулли)
    &quot;&quot;&quot;
    
    def __init__(self,
                 node1_v: Variable,     # прогиб узла 1
                 node1_theta: Variable, # угол поворота узла 1
                 node2_v: Variable,     # прогиб узла 2
                 node2_theta: Variable, # угол поворота узла 2
                 E: float,              # модуль Юнга
                 I: float,              # момент инерции сечения
                 L: float,              # длина балки
            assembler = None):
        &quot;&quot;&quot;
        Args:
            node1_v: Переменная прогиба первого узла (скаляр)
            node1_theta: Переменная угла поворота первого узла (скаляр)
            node2_v: Переменная прогиба второго узла (скаляр)
            node2_theta: Переменная угла поворота второго узла (скаляр)
            E: Модуль Юнга [Па]
            I: Момент инерции сечения относительно нейтральной оси [м⁴]
            L: Длина балки [м]
        &quot;&quot;&quot;
        self.node1_v = node1_v
        self.node1_theta = node1_theta
        self.node2_v = node2_v
        self.node2_theta = node2_theta

        super().__init__(variables=[node1_v, node1_theta, node2_v, node2_theta], assembler=assembler)
        
        self.E = E
        self.I = I
        self.L = L
        
        # Проверка: все переменные должны быть скалярами
        for var in [node1_v, node1_theta, node2_v, node2_theta]:
            if var.size != 1:
                raise ValueError(f&quot;Переменная {var.name} должна быть скаляром&quot;)
        
        if L &lt;= 0:
            raise ValueError(&quot;Длина балки должна быть положительной&quot;)
        
        if I &lt;= 0:
            raise ValueError(&quot;Момент инерции должен быть положительным&quot;)
    
    def _get_local_stiffness(self) -&gt; np.ndarray:
        &quot;&quot;&quot;
        Матрица жесткости балочного элемента Эйлера-Бернулли
        
        K = (E*I/L³) * [[  12,   6L,  -12,   6L ],
                        [  6L,  4L²,  -6L,  2L² ],
                        [ -12,  -6L,   12,  -6L ],
                        [  6L,  2L²,  -6L,  4L² ]]
        
        Порядок DOF: [v1, theta1, v2, theta2]
        &quot;&quot;&quot;
        E, I, L = self.E, self.I, self.L
        c = E * I / (L ** 3)
        
        K = c * np.array([
            [ 12,      6*L,    -12,      6*L   ],
            [ 6*L,     4*L**2, -6*L,     2*L**2],
            [-12,     -6*L,     12,     -6*L   ],
            [ 6*L,     2*L**2, -6*L,     4*L**2]
        ])
        
        return K
    
    def contribute_to_stiffness(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):
        K_local = self._get_local_stiffness()
        
        # Получить глобальные индексы в правильном порядке
        global_indices = [
            index_map[self.node1_v][0],
            index_map[self.node1_theta][0],
            index_map[self.node2_v][0],
            index_map[self.node2_theta][0]
        ]
        
        # Добавить в глобальную матрицу
        for i, gi in enumerate(global_indices):
            for j, gj in enumerate(global_indices):
                A[gi, gj] += K_local[i, j]
    
    def contribute_to_load(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):
        # Балка без распределенной нагрузки не вносит вклад в b
        pass
    
    def get_bending_moment(self, v1: float, theta1: float, 
                          v2: float, theta2: float, x: float) -&gt; float:
        &quot;&quot;&quot;
        Вычислить изгибающий момент в точке x вдоль балки
        
        Args:
            v1, theta1: Прогиб и угол поворота в узле 1
            v2, theta2: Прогиб и угол поворота в узле 2
            x: Координата вдоль балки (0 &lt;= x &lt;= L)
        
        Returns:
            Изгибающий момент M(x) [Н·м]
        &quot;&quot;&quot;
        if x &lt; 0 or x &gt; self.L:
            raise ValueError(f&quot;x должен быть в диапазоне [0, {self.L}]&quot;)
        
        # Функции формы для изгиба балки
        L = self.L
        xi = x / L  # безразмерная координата
        
        # Вторые производные функций формы (кривизна)
        N1_dd = (6 - 12*xi) / L**2
        N2_dd = (4 - 6*xi) / L
        N3_dd = (-6 + 12*xi) / L**2
        N4_dd = (-2 + 6*xi) / L
        
        # Кривизна
        curvature = v1*N1_dd + theta1*N2_dd + v2*N3_dd + theta2*N4_dd
        
        # Изгибающий момент M = -E*I*d²v/dx²
        M = -self.E * self.I * curvature
        
        return M
    
    def get_shear_force(self, v1: float, theta1: float,
                       v2: float, theta2: float, x: float) -&gt; float:
        &quot;&quot;&quot;
        Вычислить поперечную силу в точке x
        
        Q(x) = -dM/dx
        
        Returns:
            Поперечная сила Q(x) [Н]
        &quot;&quot;&quot;
        if x &lt; 0 or x &gt; self.L:
            raise ValueError(f&quot;x должен быть в диапазоне [0, {self.L}]&quot;)
        
        # Третьи производные функций формы
        L = self.L
        xi = x / L
        
        N1_ddd = -12 / L**3
        N2_ddd = -6 / L**2
        N3_ddd = 12 / L**3
        N4_ddd = 6 / L**2
        
        # Поперечная сила Q = E*I*d³v/dx³
        Q = self.E * self.I * (v1*N1_ddd + theta1*N2_ddd + 
                                v2*N3_ddd + theta2*N4_ddd)
        
        return Q


class DistributedLoad(Contribution):
    &quot;&quot;&quot;
    Распределенная нагрузка на балочный элемент.
    
    Для равномерно распределенной нагрузки q [Н/м],
    эквивалентные узловые силы:
    F = (q*L/2) * [1, L/6, 1, -L/6]
    &quot;&quot;&quot;
    
    def __init__(self,
                 node1_v: Variable,
                 node1_theta: Variable,
                 node2_v: Variable,
                 node2_theta: Variable,
                 q: float,  # интенсивность нагрузки [Н/м]
                 L: float): # длина балки
        &quot;&quot;&quot;
        Args:
            node1_v, node1_theta: Прогиб и угол поворота узла 1
            node2_v, node2_theta: Прогиб и угол поворота узла 2
            q: Интенсивность распределенной нагрузки [Н/м] (положительная вниз)
            L: Длина балки [м]
        &quot;&quot;&quot;
        self.node1_v = node1_v
        self.node1_theta = node1_theta
        self.node2_v = node2_v
        self.node2_theta = node2_theta
        self.q = q
        self.L = L

        super().__init__(variables=[node1_v, node1_theta, node2_v, node2_theta])
    
    def contribute_to_stiffness(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):
        # Не влияет на матрицу жесткости
        pass
    
    def contribute_to_load(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):
        # Эквивалентные узловые силы для равномерной нагрузки
        q, L = self.q, self.L
        
        F = np.array([
            q * L / 2,      # сила в узле 1
            q * L**2 / 12,  # момент в узле 1
            q * L / 2,      # сила в узле 2
            -q * L**2 / 12  # момент в узле 2
        ])
        
        global_indices = [
            index_map[self.node1_v][0],
            index_map[self.node1_theta][0],
            index_map[self.node2_v][0],
            index_map[self.node2_theta][0]
        ]
        
        for i, idx in enumerate(global_indices):
            b[idx] += F[i]


class Triangle3Node(Contribution):
    &quot;&quot;&quot;
    Трехузловой треугольный элемент для плоско-напряженного состояния (plane stress).
    
    Каждый узел имеет 2 степени свободы: ux, uy (перемещения в плоскости).
    Используется линейная интерполяция перемещений.
    
    Это простейший элемент для 2D задач механики сплошной среды.
    Также известен как CST (Constant Strain Triangle).
    &quot;&quot;&quot;
    
    def __init__(self,
                 node1: Variable,  # перемещения (ux1, uy1)
                 node2: Variable,  # перемещения (ux2, uy2)
                 node3: Variable,  # перемещения (ux3, uy3)
                 coords1: np.ndarray,  # координаты узла 1 (x1, y1)
                 coords2: np.ndarray,  # координаты узла 2 (x2, y2)
                 coords3: np.ndarray,  # координаты узла 3 (x3, y3)
                 E: float,         # модуль Юнга
                 nu: float,        # коэффициент Пуассона
                 thickness: float, # толщина пластины
                 plane_stress: bool = True):  # True: plane stress, False: plane strain
        &quot;&quot;&quot;
        Args:
            node1, node2, node3: Переменные перемещений узлов (каждая размера 2)
            coords1, coords2, coords3: Координаты узлов [м]
            E: Модуль Юнга [Па]
            nu: Коэффициент Пуассона (0 &lt;= nu &lt; 0.5)
            thickness: Толщина пластины [м]
            plane_stress: True для плоско-напряженного состояния,
                         False для плоской деформации
        &quot;&quot;&quot;
        self.node1 = node1
        self.node2 = node2
        self.node3 = node3

        super().__init__(variables=[node1, node2, node3])
        
        self.coords1 = np.array(coords1, dtype=float)
        self.coords2 = np.array(coords2, dtype=float)
        self.coords3 = np.array(coords3, dtype=float)
        
        self.E = E
        self.nu = nu
        self.thickness = thickness
        self.plane_stress = plane_stress
        
        # Проверки
        for node in [node1, node2, node3]:
            if node.size != 2:
                raise ValueError(f&quot;Узел {node.name} должен иметь размер 2 (ux, uy)&quot;)
        
        for coords in [self.coords1, self.coords2, self.coords3]:
            if len(coords) != 2:
                raise ValueError(&quot;Координаты должны быть 2D (x, y)&quot;)
        
        if not (0 &lt;= nu &lt; 0.5):
            raise ValueError(&quot;Коэффициент Пуассона должен быть в диапазоне [0, 0.5)&quot;)
        
        # Вычислить геометрические характеристики
        self._compute_geometry()
        
        # Вычислить матрицу жесткости
        self._compute_stiffness()
    
    def _compute_geometry(self):
        &quot;&quot;&quot;Вычислить площадь и производные функций формы&quot;&quot;&quot;
        x1, y1 = self.coords1
        x2, y2 = self.coords2
        x3, y3 = self.coords3
        
        # Площадь треугольника (удвоенная)
        self.area_2 = (x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)
        
        if abs(self.area_2) &lt; 1e-10:
            raise ValueError(&quot;Узлы треугольника лежат на одной прямой (нулевая площадь)&quot;)
        
        self.area = abs(self.area_2) / 2
        
        # Производные функций формы (константы для линейного треугольника)
        # dN/dx и dN/dy для каждой из трех функций формы
        self.dN_dx = np.array([
            (y2 - y3) / self.area_2,
            (y3 - y1) / self.area_2,
            (y1 - y2) / self.area_2
        ])
        
        self.dN_dy = np.array([
            (x3 - x2) / self.area_2,
            (x1 - x3) / self.area_2,
            (x2 - x1) / self.area_2
        ])
    
    def _get_constitutive_matrix(self) -&gt; np.ndarray:
        &quot;&quot;&quot;
        Матрица упругости D (связь напряжений и деформаций)
        
        Для плоско-напряженного состояния:
        D = (E/(1-nu²)) * [[1,  nu,    0      ],
                           [nu, 1,     0      ],
                           [0,  0,  (1-nu)/2 ]]
        
        Для плоской деформации:
        D = (E/((1+nu)(1-2nu))) * [[1-nu,  nu,        0      ],
                                    [nu,    1-nu,      0      ],
                                    [0,     0,    (1-2nu)/2 ]]
        &quot;&quot;&quot;
        E = self.E
        nu = self.nu
        
        if self.plane_stress:
            c = E / (1 - nu**2)
            D = c * np.array([
                [1,  nu,         0        ],
                [nu, 1,          0        ],
                [0,  0,  (1 - nu) / 2     ]
            ])
        else:  # plane strain
            c = E / ((1 + nu) * (1 - 2*nu))
            D = c * np.array([
                [1 - nu,  nu,            0           ],
                [nu,      1 - nu,        0           ],
                [0,       0,       (1 - 2*nu) / 2    ]
            ])
        
        return D
    
    def _get_B_matrix(self) -&gt; np.ndarray:
        &quot;&quot;&quot;
        Матрица деформаций B (связь деформаций и перемещений)
        
        Деформации: epsilon = [epsilon_xx, epsilon_yy, gamma_xy]^T
        Перемещения: u = [ux1, uy1, ux2, uy2, ux3, uy3]^T
        
        epsilon = B * u
        
        B = [[dN1/dx,    0,    dN2/dx,    0,    dN3/dx,    0   ],
             [   0,    dN1/dy,    0,    dN2/dy,    0,    dN3/dy],
             [dN1/dy, dN1/dx, dN2/dy, dN2/dx, dN3/dy, dN3/dx]]
        
        Размер: 3x6
        &quot;&quot;&quot;
        dN_dx = self.dN_dx
        dN_dy = self.dN_dy
        
        B = np.array([
            [dN_dx[0], 0,        dN_dx[1], 0,        dN_dx[2], 0       ],
            [0,        dN_dy[0], 0,        dN_dy[1], 0,        dN_dy[2]],
            [dN_dy[0], dN_dx[0], dN_dy[1], dN_dx[1], dN_dy[2], dN_dx[2]]
        ])
        
        return B
    
    def _compute_stiffness(self):
        &quot;&quot;&quot;
        Вычислить матрицу жесткости элемента
        
        K = t * A * B^T * D * B
        
        где:
        t - толщина
        A - площадь треугольника
        B - матрица деформаций (3x6)
        D - матрица упругости (3x3)
        &quot;&quot;&quot;
        D = self._get_constitutive_matrix()
        B = self._get_B_matrix()
        
        # K = t * A * B^T * D * B
        self.K = self.thickness * self.area * (B.T @ D @ B)
    
    def contribute_to_stiffness(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):
        # Получить глобальные индексы всех DOF
        # Порядок: [ux1, uy1, ux2, uy2, ux3, uy3]
        global_indices = []
        for node in [self.node1, self.node2, self.node3]:
            global_indices.extend(index_map[node])
        
        # Добавить локальную матрицу в глобальную
        for i, gi in enumerate(global_indices):
            for j, gj in enumerate(global_indices):
                A[gi, gj] += self.K[i, j]
    
    def contribute_to_load(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):
        # Треугольник без объемных сил не вносит вклад в b
        pass
    
    def get_stress(self, u: np.ndarray) -&gt; np.ndarray:
        &quot;&quot;&quot;
        Вычислить напряжения в элементе по вектору перемещений узлов
        
        Args:
            u: Вектор перемещений [ux1, uy1, ux2, uy2, ux3, uy3]
        
        Returns:
            Напряжения [sigma_xx, sigma_yy, tau_xy] [Па]
        &quot;&quot;&quot;
        if len(u) != 6:
            raise ValueError(&quot;Вектор перемещений должен иметь размер 6&quot;)
        
        D = self._get_constitutive_matrix()
        B = self._get_B_matrix()
        
        # Деформации: epsilon = B * u
        strain = B @ u
        
        # Напряжения: sigma = D * epsilon
        stress = D @ strain
        
        return stress
    
    def get_strain(self, u: np.ndarray) -&gt; np.ndarray:
        &quot;&quot;&quot;
        Вычислить деформации в элементе
        
        Returns:
            Деформации [epsilon_xx, epsilon_yy, gamma_xy]
        &quot;&quot;&quot;
        if len(u) != 6:
            raise ValueError(&quot;Вектор перемещений должен иметь размер 6&quot;)
        
        B = self._get_B_matrix()
        strain = B @ u
        
        return strain


class BodyForce(Contribution):
    &quot;&quot;&quot;
    Объемная сила для треугольного элемента
    (например, сила тяжести, центробежная сила)
    &quot;&quot;&quot;
    
    def __init__(self,
                 node1: Variable,
                 node2: Variable,
                 node3: Variable,
                 area: float,
                 thickness: float,
                 force_density: np.ndarray):  # [fx, fy] - сила на единицу объема [Н/м³]
        &quot;&quot;&quot;
        Args:
            node1, node2, node3: Узлы элемента
            area: Площадь треугольника [м²]
            thickness: Толщина [м]
            force_density: Плотность объемной силы [fx, fy] [Н/м³]
        &quot;&quot;&quot;
        self.node1 = node1
        self.node2 = node2
        self.node3 = node3
        self.area = area
        self.thickness = thickness
        self.force_density = np.array(force_density, dtype=float)

        super().__init__(variables=[node1, node2, node3])
        
        if len(self.force_density) != 2:
            raise ValueError(&quot;Плотность силы должна быть 2D вектором&quot;)
    
    def contribute_to_stiffness(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):
        pass
    
    def contribute_to_load(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):
        # Для линейного треугольника с равномерной объемной силой,
        # эквивалентные узловые силы: F_node = (volume / 3) * force_density
        volume = self.area * self.thickness
        F_node = (volume / 3) * self.force_density
        
        # Каждый узел получает 1/3 от общей силы
        for node in [self.node1, self.node2, self.node3]:
            indices = index_map[node]
            for i, idx in enumerate(indices):
                b[idx] += F_node[i]

</code></pre>
</body>
</html>
