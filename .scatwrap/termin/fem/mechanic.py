<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/mechanic.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#!/usr/bin/env python3<br>
&quot;&quot;&quot;<br>
Простейшие конечные элементы для механики.<br>
<br>
Реализованы классические элементы, которые изучаются в институте:<br>
- Стержневой элемент (bar/truss) - работает на растяжение/сжатие<br>
- Балочный элемент (beam) - работает на изгиб<br>
- Плоский треугольный элемент - для плоско-напряженного состояния<br>
&quot;&quot;&quot;<br>
<br>
import numpy as np<br>
from typing import List, Dict<br>
from .assembler import Contribution, Variable<br>
<br>
# Optional:<br>
from typing import Optional<br>
<br>
<br>
class BarElement(Contribution):<br>
    &quot;&quot;&quot;<br>
    Стержневой (ферменный) конечный элемент.<br>
    <br>
    Работает только на растяжение/сжатие (нет изгиба).<br>
    Имеет 2 узла, каждый узел имеет перемещения в 1D, 2D или 3D.<br>
    <br>
    Матрица жесткости в локальных координатах (вдоль стержня):<br>
    K_local = (E*A/L) * [[1, -1],<br>
                          [-1, 1]]<br>
    <br>
    где:<br>
    E - модуль Юнга<br>
    A - площадь поперечного сечения<br>
    L - длина элемента<br>
    &quot;&quot;&quot;<br>
    <br>
    def __init__(self, <br>
                 node1: Variable, <br>
                 node2: Variable,<br>
                 E: float,<br>
                 A: float,<br>
                 coord1: np.ndarray,<br>
                 coord2: np.ndarray):<br>
        &quot;&quot;&quot;<br>
        Args:<br>
            node1: Переменная перемещений первого узла (размер 1, 2 или 3)<br>
            node2: Переменная перемещений второго узла (размер 1, 2 или 3)<br>
            E: Модуль Юнга (модуль упругости) [Па]<br>
            A: Площадь поперечного сечения [м²]<br>
            coord1: Координаты первого узла [м]<br>
            coord2: Координаты второго узла [м]<br>
        &quot;&quot;&quot;<br>
        self.node1 = node1<br>
        self.node2 = node2<br>
        self.E = E<br>
        self.A = A<br>
        self.coord1 = np.array(coord1, dtype=float)<br>
        self.coord2 = np.array(coord2, dtype=float)<br>
        <br>
        # Проверка размерностей<br>
        if node1.size != node2.size:<br>
            raise ValueError(&quot;Узлы должны иметь одинаковую размерность&quot;)<br>
        <br>
        if len(self.coord1) != len(self.coord2):<br>
            raise ValueError(&quot;Координаты узлов должны иметь одинаковую размерность&quot;)<br>
        <br>
        if node1.size != len(self.coord1):<br>
            raise ValueError(f&quot;Размерность узла {node1.size} не соответствует &quot;<br>
                           f&quot;размерности координат {len(self.coord1)}&quot;)<br>
<br>
        super().__init__(variables=[node1, node2])<br>
        <br>
        # Вычислить геометрические параметры<br>
        self._compute_geometry()<br>
    <br>
    def _compute_geometry(self):<br>
        &quot;&quot;&quot;Вычислить длину и направляющие косинусы&quot;&quot;&quot;<br>
        # Вектор вдоль стержня<br>
        dx = self.coord2 - self.coord1<br>
        <br>
        # Длина<br>
        self.L = np.linalg.norm(dx)<br>
        if self.L &lt; 1e-10:<br>
            raise ValueError(&quot;Длина элемента слишком мала или равна нулю&quot;)<br>
        <br>
        # Направляющие косинусы (единичный вектор)<br>
        self.direction = dx / self.L<br>
        <br>
        # Коэффициент жесткости<br>
        self.k = self.E * self.A / self.L<br>
    <br>
    def _get_local_stiffness(self) -&gt; np.ndarray:<br>
        &quot;&quot;&quot;<br>
        Локальная матрица жесткости (вдоль оси стержня)<br>
        Размер 2x2 для одномерной задачи<br>
        &quot;&quot;&quot;<br>
        k = self.k<br>
        K_local_1d = np.array([<br>
            [ k, -k],<br>
            [-k,  k]<br>
        ])<br>
        return K_local_1d<br>
    <br>
    def _get_transformation_matrix(self) -&gt; np.ndarray:<br>
        &quot;&quot;&quot;<br>
        Матрица преобразования из глобальных координат в локальные<br>
        <br>
        Для 1D: T = [1, 1] (тривиальное преобразование)<br>
        Для 2D: T = [cos, sin, cos, sin]<br>
        Для 3D: T = [cx, cy, cz, cx, cy, cz]<br>
        <br>
        где c - направляющие косинусы<br>
        &quot;&quot;&quot;<br>
        dim = self.node1.size<br>
        <br>
        if dim == 1:<br>
            # 1D - нет преобразования<br>
            return np.array([1, 1])<br>
        <br>
        elif dim == 2:<br>
            # 2D - cos и sin угла<br>
            c = self.direction[0]  # cos<br>
            s = self.direction[1]  # sin<br>
            return np.array([c, s, c, s])<br>
        <br>
        elif dim == 3:<br>
            # 3D - направляющие косинусы<br>
            cx, cy, cz = self.direction<br>
            return np.array([cx, cy, cz, cx, cy, cz])<br>
        <br>
        else:<br>
            raise ValueError(f&quot;Неподдерживаемая размерность: {dim}&quot;)<br>
    <br>
    def _get_global_stiffness(self) -&gt; np.ndarray:<br>
        &quot;&quot;&quot;<br>
        Глобальная матрица жесткости<br>
        <br>
        K_global строится из направляющих косинусов<br>
        &quot;&quot;&quot;<br>
        dim = self.node1.size<br>
        k = self.k<br>
        <br>
        if dim == 1:<br>
            # 1D случай - просто локальная матрица<br>
            K_global = k * np.array([<br>
                [ 1, -1],<br>
                [-1,  1]<br>
            ])<br>
        else:<br>
            # 2D и 3D: K = k * c * c^T, где c = [l1, l2, ..., -l1, -l2, ...]<br>
            # l - направляющие косинусы<br>
            c = np.zeros(2 * dim)<br>
            c[:dim] = self.direction<br>
            c[dim:] = -self.direction<br>
            <br>
            # K = k * c * c^T<br>
            K_global = k * np.outer(c, c)<br>
        <br>
        return K_global<br>
    <br>
    def contribute_to_stiffness(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
        K_global = self._get_global_stiffness()<br>
        <br>
        # Получить глобальные индексы<br>
        indices1 = index_map[self.node1]<br>
        indices2 = index_map[self.node2]<br>
        global_indices = indices1 + indices2<br>
        <br>
        # Добавить в глобальную матрицу<br>
        for i, gi in enumerate(global_indices):<br>
            for j, gj in enumerate(global_indices):<br>
                A[gi, gj] += K_global[i, j]<br>
    <br>
    def contribute_to_load(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
        # Стержневой элемент без распределенной нагрузки не вносит вклад в b<br>
        pass<br>
    <br>
    def get_stress(self, u1: np.ndarray, u2: np.ndarray) -&gt; float:<br>
        &quot;&quot;&quot;<br>
        Вычислить напряжение в стержне по перемещениям узлов<br>
        <br>
        Args:<br>
            u1: Вектор перемещений узла 1<br>
            u2: Вектор перемещений узла 2<br>
        <br>
        Returns:<br>
            Напряжение sigma [Па] (положительное - растяжение, отрицательное - сжатие)<br>
        &quot;&quot;&quot;<br>
        # Удлинение в направлении стержня<br>
        delta_u = u2 - u1<br>
        elongation = np.dot(delta_u, self.direction)<br>
        <br>
        # Деформация<br>
        strain = elongation / self.L<br>
        <br>
        # Напряжение<br>
        stress = self.E * strain<br>
        <br>
        return stress<br>
    <br>
    def get_force(self, u1: np.ndarray, u2: np.ndarray) -&gt; float:<br>
        &quot;&quot;&quot;<br>
        Вычислить силу в стержне<br>
        <br>
        Returns:<br>
            Сила N [Н] (положительная - растяжение)<br>
        &quot;&quot;&quot;<br>
        stress = self.get_stress(u1, u2)<br>
        force = stress * self.A<br>
        return force<br>
<br>
<br>
class BeamElement2D(Contribution):<br>
    &quot;&quot;&quot;<br>
    Балочный элемент Эйлера-Бернулли для плоской задачи.<br>
    <br>
    Работает на изгиб в плоскости. Каждый узел имеет 2 степени свободы:<br>
    - v: прогиб (перемещение перпендикулярно оси)<br>
    - theta: угол поворота сечения<br>
    <br>
    Матрица жесткости 4x4 (2 узла × 2 DOF на узел).<br>
    <br>
    Предположения:<br>
    - Малые деформации<br>
    - Гипотеза плоских сечений<br>
    - Пренебрегаем деформациями сдвига (теория Эйлера-Бернулли)<br>
    &quot;&quot;&quot;<br>
    <br>
    def __init__(self,<br>
                 node1_v: Variable,     # прогиб узла 1<br>
                 node1_theta: Variable, # угол поворота узла 1<br>
                 node2_v: Variable,     # прогиб узла 2<br>
                 node2_theta: Variable, # угол поворота узла 2<br>
                 E: float,              # модуль Юнга<br>
                 I: float,              # момент инерции сечения<br>
                 L: float,              # длина балки<br>
            assembler = None):<br>
        &quot;&quot;&quot;<br>
        Args:<br>
            node1_v: Переменная прогиба первого узла (скаляр)<br>
            node1_theta: Переменная угла поворота первого узла (скаляр)<br>
            node2_v: Переменная прогиба второго узла (скаляр)<br>
            node2_theta: Переменная угла поворота второго узла (скаляр)<br>
            E: Модуль Юнга [Па]<br>
            I: Момент инерции сечения относительно нейтральной оси [м⁴]<br>
            L: Длина балки [м]<br>
        &quot;&quot;&quot;<br>
        self.node1_v = node1_v<br>
        self.node1_theta = node1_theta<br>
        self.node2_v = node2_v<br>
        self.node2_theta = node2_theta<br>
<br>
        super().__init__(variables=[node1_v, node1_theta, node2_v, node2_theta], assembler=assembler)<br>
        <br>
        self.E = E<br>
        self.I = I<br>
        self.L = L<br>
        <br>
        # Проверка: все переменные должны быть скалярами<br>
        for var in [node1_v, node1_theta, node2_v, node2_theta]:<br>
            if var.size != 1:<br>
                raise ValueError(f&quot;Переменная {var.name} должна быть скаляром&quot;)<br>
        <br>
        if L &lt;= 0:<br>
            raise ValueError(&quot;Длина балки должна быть положительной&quot;)<br>
        <br>
        if I &lt;= 0:<br>
            raise ValueError(&quot;Момент инерции должен быть положительным&quot;)<br>
    <br>
    def _get_local_stiffness(self) -&gt; np.ndarray:<br>
        &quot;&quot;&quot;<br>
        Матрица жесткости балочного элемента Эйлера-Бернулли<br>
        <br>
        K = (E*I/L³) * [[  12,   6L,  -12,   6L ],<br>
                        [  6L,  4L²,  -6L,  2L² ],<br>
                        [ -12,  -6L,   12,  -6L ],<br>
                        [  6L,  2L²,  -6L,  4L² ]]<br>
        <br>
        Порядок DOF: [v1, theta1, v2, theta2]<br>
        &quot;&quot;&quot;<br>
        E, I, L = self.E, self.I, self.L<br>
        c = E * I / (L ** 3)<br>
        <br>
        K = c * np.array([<br>
            [ 12,      6*L,    -12,      6*L   ],<br>
            [ 6*L,     4*L**2, -6*L,     2*L**2],<br>
            [-12,     -6*L,     12,     -6*L   ],<br>
            [ 6*L,     2*L**2, -6*L,     4*L**2]<br>
        ])<br>
        <br>
        return K<br>
    <br>
    def contribute_to_stiffness(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
        K_local = self._get_local_stiffness()<br>
        <br>
        # Получить глобальные индексы в правильном порядке<br>
        global_indices = [<br>
            index_map[self.node1_v][0],<br>
            index_map[self.node1_theta][0],<br>
            index_map[self.node2_v][0],<br>
            index_map[self.node2_theta][0]<br>
        ]<br>
        <br>
        # Добавить в глобальную матрицу<br>
        for i, gi in enumerate(global_indices):<br>
            for j, gj in enumerate(global_indices):<br>
                A[gi, gj] += K_local[i, j]<br>
    <br>
    def contribute_to_load(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
        # Балка без распределенной нагрузки не вносит вклад в b<br>
        pass<br>
    <br>
    def get_bending_moment(self, v1: float, theta1: float, <br>
                          v2: float, theta2: float, x: float) -&gt; float:<br>
        &quot;&quot;&quot;<br>
        Вычислить изгибающий момент в точке x вдоль балки<br>
        <br>
        Args:<br>
            v1, theta1: Прогиб и угол поворота в узле 1<br>
            v2, theta2: Прогиб и угол поворота в узле 2<br>
            x: Координата вдоль балки (0 &lt;= x &lt;= L)<br>
        <br>
        Returns:<br>
            Изгибающий момент M(x) [Н·м]<br>
        &quot;&quot;&quot;<br>
        if x &lt; 0 or x &gt; self.L:<br>
            raise ValueError(f&quot;x должен быть в диапазоне [0, {self.L}]&quot;)<br>
        <br>
        # Функции формы для изгиба балки<br>
        L = self.L<br>
        xi = x / L  # безразмерная координата<br>
        <br>
        # Вторые производные функций формы (кривизна)<br>
        N1_dd = (6 - 12*xi) / L**2<br>
        N2_dd = (4 - 6*xi) / L<br>
        N3_dd = (-6 + 12*xi) / L**2<br>
        N4_dd = (-2 + 6*xi) / L<br>
        <br>
        # Кривизна<br>
        curvature = v1*N1_dd + theta1*N2_dd + v2*N3_dd + theta2*N4_dd<br>
        <br>
        # Изгибающий момент M = -E*I*d²v/dx²<br>
        M = -self.E * self.I * curvature<br>
        <br>
        return M<br>
    <br>
    def get_shear_force(self, v1: float, theta1: float,<br>
                       v2: float, theta2: float, x: float) -&gt; float:<br>
        &quot;&quot;&quot;<br>
        Вычислить поперечную силу в точке x<br>
        <br>
        Q(x) = -dM/dx<br>
        <br>
        Returns:<br>
            Поперечная сила Q(x) [Н]<br>
        &quot;&quot;&quot;<br>
        if x &lt; 0 or x &gt; self.L:<br>
            raise ValueError(f&quot;x должен быть в диапазоне [0, {self.L}]&quot;)<br>
        <br>
        # Третьи производные функций формы<br>
        L = self.L<br>
        xi = x / L<br>
        <br>
        N1_ddd = -12 / L**3<br>
        N2_ddd = -6 / L**2<br>
        N3_ddd = 12 / L**3<br>
        N4_ddd = 6 / L**2<br>
        <br>
        # Поперечная сила Q = E*I*d³v/dx³<br>
        Q = self.E * self.I * (v1*N1_ddd + theta1*N2_ddd + <br>
                                v2*N3_ddd + theta2*N4_ddd)<br>
        <br>
        return Q<br>
<br>
<br>
class DistributedLoad(Contribution):<br>
    &quot;&quot;&quot;<br>
    Распределенная нагрузка на балочный элемент.<br>
    <br>
    Для равномерно распределенной нагрузки q [Н/м],<br>
    эквивалентные узловые силы:<br>
    F = (q*L/2) * [1, L/6, 1, -L/6]<br>
    &quot;&quot;&quot;<br>
    <br>
    def __init__(self,<br>
                 node1_v: Variable,<br>
                 node1_theta: Variable,<br>
                 node2_v: Variable,<br>
                 node2_theta: Variable,<br>
                 q: float,  # интенсивность нагрузки [Н/м]<br>
                 L: float): # длина балки<br>
        &quot;&quot;&quot;<br>
        Args:<br>
            node1_v, node1_theta: Прогиб и угол поворота узла 1<br>
            node2_v, node2_theta: Прогиб и угол поворота узла 2<br>
            q: Интенсивность распределенной нагрузки [Н/м] (положительная вниз)<br>
            L: Длина балки [м]<br>
        &quot;&quot;&quot;<br>
        self.node1_v = node1_v<br>
        self.node1_theta = node1_theta<br>
        self.node2_v = node2_v<br>
        self.node2_theta = node2_theta<br>
        self.q = q<br>
        self.L = L<br>
<br>
        super().__init__(variables=[node1_v, node1_theta, node2_v, node2_theta])<br>
    <br>
    def contribute_to_stiffness(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
        # Не влияет на матрицу жесткости<br>
        pass<br>
    <br>
    def contribute_to_load(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
        # Эквивалентные узловые силы для равномерной нагрузки<br>
        q, L = self.q, self.L<br>
        <br>
        F = np.array([<br>
            q * L / 2,      # сила в узле 1<br>
            q * L**2 / 12,  # момент в узле 1<br>
            q * L / 2,      # сила в узле 2<br>
            -q * L**2 / 12  # момент в узле 2<br>
        ])<br>
        <br>
        global_indices = [<br>
            index_map[self.node1_v][0],<br>
            index_map[self.node1_theta][0],<br>
            index_map[self.node2_v][0],<br>
            index_map[self.node2_theta][0]<br>
        ]<br>
        <br>
        for i, idx in enumerate(global_indices):<br>
            b[idx] += F[i]<br>
<br>
<br>
class Triangle3Node(Contribution):<br>
    &quot;&quot;&quot;<br>
    Трехузловой треугольный элемент для плоско-напряженного состояния (plane stress).<br>
    <br>
    Каждый узел имеет 2 степени свободы: ux, uy (перемещения в плоскости).<br>
    Используется линейная интерполяция перемещений.<br>
    <br>
    Это простейший элемент для 2D задач механики сплошной среды.<br>
    Также известен как CST (Constant Strain Triangle).<br>
    &quot;&quot;&quot;<br>
    <br>
    def __init__(self,<br>
                 node1: Variable,  # перемещения (ux1, uy1)<br>
                 node2: Variable,  # перемещения (ux2, uy2)<br>
                 node3: Variable,  # перемещения (ux3, uy3)<br>
                 coords1: np.ndarray,  # координаты узла 1 (x1, y1)<br>
                 coords2: np.ndarray,  # координаты узла 2 (x2, y2)<br>
                 coords3: np.ndarray,  # координаты узла 3 (x3, y3)<br>
                 E: float,         # модуль Юнга<br>
                 nu: float,        # коэффициент Пуассона<br>
                 thickness: float, # толщина пластины<br>
                 plane_stress: bool = True):  # True: plane stress, False: plane strain<br>
        &quot;&quot;&quot;<br>
        Args:<br>
            node1, node2, node3: Переменные перемещений узлов (каждая размера 2)<br>
            coords1, coords2, coords3: Координаты узлов [м]<br>
            E: Модуль Юнга [Па]<br>
            nu: Коэффициент Пуассона (0 &lt;= nu &lt; 0.5)<br>
            thickness: Толщина пластины [м]<br>
            plane_stress: True для плоско-напряженного состояния,<br>
                         False для плоской деформации<br>
        &quot;&quot;&quot;<br>
        self.node1 = node1<br>
        self.node2 = node2<br>
        self.node3 = node3<br>
<br>
        super().__init__(variables=[node1, node2, node3])<br>
        <br>
        self.coords1 = np.array(coords1, dtype=float)<br>
        self.coords2 = np.array(coords2, dtype=float)<br>
        self.coords3 = np.array(coords3, dtype=float)<br>
        <br>
        self.E = E<br>
        self.nu = nu<br>
        self.thickness = thickness<br>
        self.plane_stress = plane_stress<br>
        <br>
        # Проверки<br>
        for node in [node1, node2, node3]:<br>
            if node.size != 2:<br>
                raise ValueError(f&quot;Узел {node.name} должен иметь размер 2 (ux, uy)&quot;)<br>
        <br>
        for coords in [self.coords1, self.coords2, self.coords3]:<br>
            if len(coords) != 2:<br>
                raise ValueError(&quot;Координаты должны быть 2D (x, y)&quot;)<br>
        <br>
        if not (0 &lt;= nu &lt; 0.5):<br>
            raise ValueError(&quot;Коэффициент Пуассона должен быть в диапазоне [0, 0.5)&quot;)<br>
        <br>
        # Вычислить геометрические характеристики<br>
        self._compute_geometry()<br>
        <br>
        # Вычислить матрицу жесткости<br>
        self._compute_stiffness()<br>
    <br>
    def _compute_geometry(self):<br>
        &quot;&quot;&quot;Вычислить площадь и производные функций формы&quot;&quot;&quot;<br>
        x1, y1 = self.coords1<br>
        x2, y2 = self.coords2<br>
        x3, y3 = self.coords3<br>
        <br>
        # Площадь треугольника (удвоенная)<br>
        self.area_2 = (x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)<br>
        <br>
        if abs(self.area_2) &lt; 1e-10:<br>
            raise ValueError(&quot;Узлы треугольника лежат на одной прямой (нулевая площадь)&quot;)<br>
        <br>
        self.area = abs(self.area_2) / 2<br>
        <br>
        # Производные функций формы (константы для линейного треугольника)<br>
        # dN/dx и dN/dy для каждой из трех функций формы<br>
        self.dN_dx = np.array([<br>
            (y2 - y3) / self.area_2,<br>
            (y3 - y1) / self.area_2,<br>
            (y1 - y2) / self.area_2<br>
        ])<br>
        <br>
        self.dN_dy = np.array([<br>
            (x3 - x2) / self.area_2,<br>
            (x1 - x3) / self.area_2,<br>
            (x2 - x1) / self.area_2<br>
        ])<br>
    <br>
    def _get_constitutive_matrix(self) -&gt; np.ndarray:<br>
        &quot;&quot;&quot;<br>
        Матрица упругости D (связь напряжений и деформаций)<br>
        <br>
        Для плоско-напряженного состояния:<br>
        D = (E/(1-nu²)) * [[1,  nu,    0      ],<br>
                           [nu, 1,     0      ],<br>
                           [0,  0,  (1-nu)/2 ]]<br>
        <br>
        Для плоской деформации:<br>
        D = (E/((1+nu)(1-2nu))) * [[1-nu,  nu,        0      ],<br>
                                    [nu,    1-nu,      0      ],<br>
                                    [0,     0,    (1-2nu)/2 ]]<br>
        &quot;&quot;&quot;<br>
        E = self.E<br>
        nu = self.nu<br>
        <br>
        if self.plane_stress:<br>
            c = E / (1 - nu**2)<br>
            D = c * np.array([<br>
                [1,  nu,         0        ],<br>
                [nu, 1,          0        ],<br>
                [0,  0,  (1 - nu) / 2     ]<br>
            ])<br>
        else:  # plane strain<br>
            c = E / ((1 + nu) * (1 - 2*nu))<br>
            D = c * np.array([<br>
                [1 - nu,  nu,            0           ],<br>
                [nu,      1 - nu,        0           ],<br>
                [0,       0,       (1 - 2*nu) / 2    ]<br>
            ])<br>
        <br>
        return D<br>
    <br>
    def _get_B_matrix(self) -&gt; np.ndarray:<br>
        &quot;&quot;&quot;<br>
        Матрица деформаций B (связь деформаций и перемещений)<br>
        <br>
        Деформации: epsilon = [epsilon_xx, epsilon_yy, gamma_xy]^T<br>
        Перемещения: u = [ux1, uy1, ux2, uy2, ux3, uy3]^T<br>
        <br>
        epsilon = B * u<br>
        <br>
        B = [[dN1/dx,    0,    dN2/dx,    0,    dN3/dx,    0   ],<br>
             [   0,    dN1/dy,    0,    dN2/dy,    0,    dN3/dy],<br>
             [dN1/dy, dN1/dx, dN2/dy, dN2/dx, dN3/dy, dN3/dx]]<br>
        <br>
        Размер: 3x6<br>
        &quot;&quot;&quot;<br>
        dN_dx = self.dN_dx<br>
        dN_dy = self.dN_dy<br>
        <br>
        B = np.array([<br>
            [dN_dx[0], 0,        dN_dx[1], 0,        dN_dx[2], 0       ],<br>
            [0,        dN_dy[0], 0,        dN_dy[1], 0,        dN_dy[2]],<br>
            [dN_dy[0], dN_dx[0], dN_dy[1], dN_dx[1], dN_dy[2], dN_dx[2]]<br>
        ])<br>
        <br>
        return B<br>
    <br>
    def _compute_stiffness(self):<br>
        &quot;&quot;&quot;<br>
        Вычислить матрицу жесткости элемента<br>
        <br>
        K = t * A * B^T * D * B<br>
        <br>
        где:<br>
        t - толщина<br>
        A - площадь треугольника<br>
        B - матрица деформаций (3x6)<br>
        D - матрица упругости (3x3)<br>
        &quot;&quot;&quot;<br>
        D = self._get_constitutive_matrix()<br>
        B = self._get_B_matrix()<br>
        <br>
        # K = t * A * B^T * D * B<br>
        self.K = self.thickness * self.area * (B.T @ D @ B)<br>
    <br>
    def contribute_to_stiffness(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
        # Получить глобальные индексы всех DOF<br>
        # Порядок: [ux1, uy1, ux2, uy2, ux3, uy3]<br>
        global_indices = []<br>
        for node in [self.node1, self.node2, self.node3]:<br>
            global_indices.extend(index_map[node])<br>
        <br>
        # Добавить локальную матрицу в глобальную<br>
        for i, gi in enumerate(global_indices):<br>
            for j, gj in enumerate(global_indices):<br>
                A[gi, gj] += self.K[i, j]<br>
    <br>
    def contribute_to_load(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
        # Треугольник без объемных сил не вносит вклад в b<br>
        pass<br>
    <br>
    def get_stress(self, u: np.ndarray) -&gt; np.ndarray:<br>
        &quot;&quot;&quot;<br>
        Вычислить напряжения в элементе по вектору перемещений узлов<br>
        <br>
        Args:<br>
            u: Вектор перемещений [ux1, uy1, ux2, uy2, ux3, uy3]<br>
        <br>
        Returns:<br>
            Напряжения [sigma_xx, sigma_yy, tau_xy] [Па]<br>
        &quot;&quot;&quot;<br>
        if len(u) != 6:<br>
            raise ValueError(&quot;Вектор перемещений должен иметь размер 6&quot;)<br>
        <br>
        D = self._get_constitutive_matrix()<br>
        B = self._get_B_matrix()<br>
        <br>
        # Деформации: epsilon = B * u<br>
        strain = B @ u<br>
        <br>
        # Напряжения: sigma = D * epsilon<br>
        stress = D @ strain<br>
        <br>
        return stress<br>
    <br>
    def get_strain(self, u: np.ndarray) -&gt; np.ndarray:<br>
        &quot;&quot;&quot;<br>
        Вычислить деформации в элементе<br>
        <br>
        Returns:<br>
            Деформации [epsilon_xx, epsilon_yy, gamma_xy]<br>
        &quot;&quot;&quot;<br>
        if len(u) != 6:<br>
            raise ValueError(&quot;Вектор перемещений должен иметь размер 6&quot;)<br>
        <br>
        B = self._get_B_matrix()<br>
        strain = B @ u<br>
        <br>
        return strain<br>
<br>
<br>
class BodyForce(Contribution):<br>
    &quot;&quot;&quot;<br>
    Объемная сила для треугольного элемента<br>
    (например, сила тяжести, центробежная сила)<br>
    &quot;&quot;&quot;<br>
    <br>
    def __init__(self,<br>
                 node1: Variable,<br>
                 node2: Variable,<br>
                 node3: Variable,<br>
                 area: float,<br>
                 thickness: float,<br>
                 force_density: np.ndarray):  # [fx, fy] - сила на единицу объема [Н/м³]<br>
        &quot;&quot;&quot;<br>
        Args:<br>
            node1, node2, node3: Узлы элемента<br>
            area: Площадь треугольника [м²]<br>
            thickness: Толщина [м]<br>
            force_density: Плотность объемной силы [fx, fy] [Н/м³]<br>
        &quot;&quot;&quot;<br>
        self.node1 = node1<br>
        self.node2 = node2<br>
        self.node3 = node3<br>
        self.area = area<br>
        self.thickness = thickness<br>
        self.force_density = np.array(force_density, dtype=float)<br>
<br>
        super().__init__(variables=[node1, node2, node3])<br>
        <br>
        if len(self.force_density) != 2:<br>
            raise ValueError(&quot;Плотность силы должна быть 2D вектором&quot;)<br>
    <br>
    def contribute_to_stiffness(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
        pass<br>
    <br>
    def contribute_to_load(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
        # Для линейного треугольника с равномерной объемной силой,<br>
        # эквивалентные узловые силы: F_node = (volume / 3) * force_density<br>
        volume = self.area * self.thickness<br>
        F_node = (volume / 3) * self.force_density<br>
        <br>
        # Каждый узел получает 1/3 от общей силы<br>
        for node in [self.node1, self.node2, self.node3]:<br>
            indices = index_map[node]<br>
            for i, idx in enumerate(indices):<br>
                b[idx] += F_node[i]<br>
<!-- END SCAT CODE -->
</body>
</html>
