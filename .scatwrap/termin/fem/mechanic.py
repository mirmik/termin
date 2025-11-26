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
&#9;&quot;&quot;&quot;<br>
&#9;Стержневой (ферменный) конечный элемент.<br>
&#9;<br>
&#9;Работает только на растяжение/сжатие (нет изгиба).<br>
&#9;Имеет 2 узла, каждый узел имеет перемещения в 1D, 2D или 3D.<br>
&#9;<br>
&#9;Матрица жесткости в локальных координатах (вдоль стержня):<br>
&#9;K_local = (E*A/L) * [[1, -1],<br>
&#9;&#9;&#9;&#9;&#9;&#9;[-1, 1]]<br>
&#9;<br>
&#9;где:<br>
&#9;E - модуль Юнга<br>
&#9;A - площадь поперечного сечения<br>
&#9;L - длина элемента<br>
&#9;&quot;&quot;&quot;<br>
&#9;<br>
&#9;def __init__(self, <br>
&#9;&#9;&#9;&#9;node1: Variable, <br>
&#9;&#9;&#9;&#9;node2: Variable,<br>
&#9;&#9;&#9;&#9;E: float,<br>
&#9;&#9;&#9;&#9;A: float,<br>
&#9;&#9;&#9;&#9;coord1: np.ndarray,<br>
&#9;&#9;&#9;&#9;coord2: np.ndarray):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;node1: Переменная перемещений первого узла (размер 1, 2 или 3)<br>
&#9;&#9;&#9;node2: Переменная перемещений второго узла (размер 1, 2 или 3)<br>
&#9;&#9;&#9;E: Модуль Юнга (модуль упругости) [Па]<br>
&#9;&#9;&#9;A: Площадь поперечного сечения [м²]<br>
&#9;&#9;&#9;coord1: Координаты первого узла [м]<br>
&#9;&#9;&#9;coord2: Координаты второго узла [м]<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self.node1 = node1<br>
&#9;&#9;self.node2 = node2<br>
&#9;&#9;self.E = E<br>
&#9;&#9;self.A = A<br>
&#9;&#9;self.coord1 = np.array(coord1, dtype=float)<br>
&#9;&#9;self.coord2 = np.array(coord2, dtype=float)<br>
&#9;&#9;<br>
&#9;&#9;# Проверка размерностей<br>
&#9;&#9;if node1.size != node2.size:<br>
&#9;&#9;&#9;raise ValueError(&quot;Узлы должны иметь одинаковую размерность&quot;)<br>
&#9;&#9;<br>
&#9;&#9;if len(self.coord1) != len(self.coord2):<br>
&#9;&#9;&#9;raise ValueError(&quot;Координаты узлов должны иметь одинаковую размерность&quot;)<br>
&#9;&#9;<br>
&#9;&#9;if node1.size != len(self.coord1):<br>
&#9;&#9;&#9;raise ValueError(f&quot;Размерность узла {node1.size} не соответствует &quot;<br>
&#9;&#9;&#9;&#9;&#9;&#9;f&quot;размерности координат {len(self.coord1)}&quot;)<br>
<br>
&#9;&#9;super().__init__(variables=[node1, node2])<br>
&#9;&#9;<br>
&#9;&#9;# Вычислить геометрические параметры<br>
&#9;&#9;self._compute_geometry()<br>
&#9;<br>
&#9;def _compute_geometry(self):<br>
&#9;&#9;&quot;&quot;&quot;Вычислить длину и направляющие косинусы&quot;&quot;&quot;<br>
&#9;&#9;# Вектор вдоль стержня<br>
&#9;&#9;dx = self.coord2 - self.coord1<br>
&#9;&#9;<br>
&#9;&#9;# Длина<br>
&#9;&#9;self.L = np.linalg.norm(dx)<br>
&#9;&#9;if self.L &lt; 1e-10:<br>
&#9;&#9;&#9;raise ValueError(&quot;Длина элемента слишком мала или равна нулю&quot;)<br>
&#9;&#9;<br>
&#9;&#9;# Направляющие косинусы (единичный вектор)<br>
&#9;&#9;self.direction = dx / self.L<br>
&#9;&#9;<br>
&#9;&#9;# Коэффициент жесткости<br>
&#9;&#9;self.k = self.E * self.A / self.L<br>
&#9;<br>
&#9;def _get_local_stiffness(self) -&gt; np.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Локальная матрица жесткости (вдоль оси стержня)<br>
&#9;&#9;Размер 2x2 для одномерной задачи<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;k = self.k<br>
&#9;&#9;K_local_1d = np.array([<br>
&#9;&#9;&#9;[ k, -k],<br>
&#9;&#9;&#9;[-k,  k]<br>
&#9;&#9;])<br>
&#9;&#9;return K_local_1d<br>
&#9;<br>
&#9;def _get_transformation_matrix(self) -&gt; np.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Матрица преобразования из глобальных координат в локальные<br>
&#9;&#9;<br>
&#9;&#9;Для 1D: T = [1, 1] (тривиальное преобразование)<br>
&#9;&#9;Для 2D: T = [cos, sin, cos, sin]<br>
&#9;&#9;Для 3D: T = [cx, cy, cz, cx, cy, cz]<br>
&#9;&#9;<br>
&#9;&#9;где c - направляющие косинусы<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;dim = self.node1.size<br>
&#9;&#9;<br>
&#9;&#9;if dim == 1:<br>
&#9;&#9;&#9;# 1D - нет преобразования<br>
&#9;&#9;&#9;return np.array([1, 1])<br>
&#9;&#9;<br>
&#9;&#9;elif dim == 2:<br>
&#9;&#9;&#9;# 2D - cos и sin угла<br>
&#9;&#9;&#9;c = self.direction[0]  # cos<br>
&#9;&#9;&#9;s = self.direction[1]  # sin<br>
&#9;&#9;&#9;return np.array([c, s, c, s])<br>
&#9;&#9;<br>
&#9;&#9;elif dim == 3:<br>
&#9;&#9;&#9;# 3D - направляющие косинусы<br>
&#9;&#9;&#9;cx, cy, cz = self.direction<br>
&#9;&#9;&#9;return np.array([cx, cy, cz, cx, cy, cz])<br>
&#9;&#9;<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;raise ValueError(f&quot;Неподдерживаемая размерность: {dim}&quot;)<br>
&#9;<br>
&#9;def _get_global_stiffness(self) -&gt; np.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Глобальная матрица жесткости<br>
&#9;&#9;<br>
&#9;&#9;K_global строится из направляющих косинусов<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;dim = self.node1.size<br>
&#9;&#9;k = self.k<br>
&#9;&#9;<br>
&#9;&#9;if dim == 1:<br>
&#9;&#9;&#9;# 1D случай - просто локальная матрица<br>
&#9;&#9;&#9;K_global = k * np.array([<br>
&#9;&#9;&#9;&#9;[ 1, -1],<br>
&#9;&#9;&#9;&#9;[-1,  1]<br>
&#9;&#9;&#9;])<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;# 2D и 3D: K = k * c * c^T, где c = [l1, l2, ..., -l1, -l2, ...]<br>
&#9;&#9;&#9;# l - направляющие косинусы<br>
&#9;&#9;&#9;c = np.zeros(2 * dim)<br>
&#9;&#9;&#9;c[:dim] = self.direction<br>
&#9;&#9;&#9;c[dim:] = -self.direction<br>
&#9;&#9;&#9;<br>
&#9;&#9;&#9;# K = k * c * c^T<br>
&#9;&#9;&#9;K_global = k * np.outer(c, c)<br>
&#9;&#9;<br>
&#9;&#9;return K_global<br>
&#9;<br>
&#9;def contribute_to_stiffness(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;K_global = self._get_global_stiffness()<br>
&#9;&#9;<br>
&#9;&#9;# Получить глобальные индексы<br>
&#9;&#9;indices1 = index_map[self.node1]<br>
&#9;&#9;indices2 = index_map[self.node2]<br>
&#9;&#9;global_indices = indices1 + indices2<br>
&#9;&#9;<br>
&#9;&#9;# Добавить в глобальную матрицу<br>
&#9;&#9;for i, gi in enumerate(global_indices):<br>
&#9;&#9;&#9;for j, gj in enumerate(global_indices):<br>
&#9;&#9;&#9;&#9;A[gi, gj] += K_global[i, j]<br>
&#9;<br>
&#9;def contribute_to_load(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;# Стержневой элемент без распределенной нагрузки не вносит вклад в b<br>
&#9;&#9;pass<br>
&#9;<br>
&#9;def get_stress(self, u1: np.ndarray, u2: np.ndarray) -&gt; float:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Вычислить напряжение в стержне по перемещениям узлов<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;u1: Вектор перемещений узла 1<br>
&#9;&#9;&#9;u2: Вектор перемещений узла 2<br>
&#9;&#9;<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;Напряжение sigma [Па] (положительное - растяжение, отрицательное - сжатие)<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;# Удлинение в направлении стержня<br>
&#9;&#9;delta_u = u2 - u1<br>
&#9;&#9;elongation = np.dot(delta_u, self.direction)<br>
&#9;&#9;<br>
&#9;&#9;# Деформация<br>
&#9;&#9;strain = elongation / self.L<br>
&#9;&#9;<br>
&#9;&#9;# Напряжение<br>
&#9;&#9;stress = self.E * strain<br>
&#9;&#9;<br>
&#9;&#9;return stress<br>
&#9;<br>
&#9;def get_force(self, u1: np.ndarray, u2: np.ndarray) -&gt; float:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Вычислить силу в стержне<br>
&#9;&#9;<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;Сила N [Н] (положительная - растяжение)<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;stress = self.get_stress(u1, u2)<br>
&#9;&#9;force = stress * self.A<br>
&#9;&#9;return force<br>
<br>
<br>
class BeamElement2D(Contribution):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Балочный элемент Эйлера-Бернулли для плоской задачи.<br>
&#9;<br>
&#9;Работает на изгиб в плоскости. Каждый узел имеет 2 степени свободы:<br>
&#9;- v: прогиб (перемещение перпендикулярно оси)<br>
&#9;- theta: угол поворота сечения<br>
&#9;<br>
&#9;Матрица жесткости 4x4 (2 узла × 2 DOF на узел).<br>
&#9;<br>
&#9;Предположения:<br>
&#9;- Малые деформации<br>
&#9;- Гипотеза плоских сечений<br>
&#9;- Пренебрегаем деформациями сдвига (теория Эйлера-Бернулли)<br>
&#9;&quot;&quot;&quot;<br>
&#9;<br>
&#9;def __init__(self,<br>
&#9;&#9;&#9;&#9;node1_v: Variable,     # прогиб узла 1<br>
&#9;&#9;&#9;&#9;node1_theta: Variable, # угол поворота узла 1<br>
&#9;&#9;&#9;&#9;node2_v: Variable,     # прогиб узла 2<br>
&#9;&#9;&#9;&#9;node2_theta: Variable, # угол поворота узла 2<br>
&#9;&#9;&#9;&#9;E: float,              # модуль Юнга<br>
&#9;&#9;&#9;&#9;I: float,              # момент инерции сечения<br>
&#9;&#9;&#9;&#9;L: float,              # длина балки<br>
&#9;&#9;&#9;assembler = None):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;node1_v: Переменная прогиба первого узла (скаляр)<br>
&#9;&#9;&#9;node1_theta: Переменная угла поворота первого узла (скаляр)<br>
&#9;&#9;&#9;node2_v: Переменная прогиба второго узла (скаляр)<br>
&#9;&#9;&#9;node2_theta: Переменная угла поворота второго узла (скаляр)<br>
&#9;&#9;&#9;E: Модуль Юнга [Па]<br>
&#9;&#9;&#9;I: Момент инерции сечения относительно нейтральной оси [м⁴]<br>
&#9;&#9;&#9;L: Длина балки [м]<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self.node1_v = node1_v<br>
&#9;&#9;self.node1_theta = node1_theta<br>
&#9;&#9;self.node2_v = node2_v<br>
&#9;&#9;self.node2_theta = node2_theta<br>
<br>
&#9;&#9;super().__init__(variables=[node1_v, node1_theta, node2_v, node2_theta], assembler=assembler)<br>
&#9;&#9;<br>
&#9;&#9;self.E = E<br>
&#9;&#9;self.I = I<br>
&#9;&#9;self.L = L<br>
&#9;&#9;<br>
&#9;&#9;# Проверка: все переменные должны быть скалярами<br>
&#9;&#9;for var in [node1_v, node1_theta, node2_v, node2_theta]:<br>
&#9;&#9;&#9;if var.size != 1:<br>
&#9;&#9;&#9;&#9;raise ValueError(f&quot;Переменная {var.name} должна быть скаляром&quot;)<br>
&#9;&#9;<br>
&#9;&#9;if L &lt;= 0:<br>
&#9;&#9;&#9;raise ValueError(&quot;Длина балки должна быть положительной&quot;)<br>
&#9;&#9;<br>
&#9;&#9;if I &lt;= 0:<br>
&#9;&#9;&#9;raise ValueError(&quot;Момент инерции должен быть положительным&quot;)<br>
&#9;<br>
&#9;def _get_local_stiffness(self) -&gt; np.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Матрица жесткости балочного элемента Эйлера-Бернулли<br>
&#9;&#9;<br>
&#9;&#9;K = (E*I/L³) * [[  12,   6L,  -12,   6L ],<br>
&#9;&#9;&#9;&#9;&#9;&#9;[  6L,  4L²,  -6L,  2L² ],<br>
&#9;&#9;&#9;&#9;&#9;&#9;[ -12,  -6L,   12,  -6L ],<br>
&#9;&#9;&#9;&#9;&#9;&#9;[  6L,  2L²,  -6L,  4L² ]]<br>
&#9;&#9;<br>
&#9;&#9;Порядок DOF: [v1, theta1, v2, theta2]<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;E, I, L = self.E, self.I, self.L<br>
&#9;&#9;c = E * I / (L ** 3)<br>
&#9;&#9;<br>
&#9;&#9;K = c * np.array([<br>
&#9;&#9;&#9;[ 12,      6*L,    -12,      6*L   ],<br>
&#9;&#9;&#9;[ 6*L,     4*L**2, -6*L,     2*L**2],<br>
&#9;&#9;&#9;[-12,     -6*L,     12,     -6*L   ],<br>
&#9;&#9;&#9;[ 6*L,     2*L**2, -6*L,     4*L**2]<br>
&#9;&#9;])<br>
&#9;&#9;<br>
&#9;&#9;return K<br>
&#9;<br>
&#9;def contribute_to_stiffness(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;K_local = self._get_local_stiffness()<br>
&#9;&#9;<br>
&#9;&#9;# Получить глобальные индексы в правильном порядке<br>
&#9;&#9;global_indices = [<br>
&#9;&#9;&#9;index_map[self.node1_v][0],<br>
&#9;&#9;&#9;index_map[self.node1_theta][0],<br>
&#9;&#9;&#9;index_map[self.node2_v][0],<br>
&#9;&#9;&#9;index_map[self.node2_theta][0]<br>
&#9;&#9;]<br>
&#9;&#9;<br>
&#9;&#9;# Добавить в глобальную матрицу<br>
&#9;&#9;for i, gi in enumerate(global_indices):<br>
&#9;&#9;&#9;for j, gj in enumerate(global_indices):<br>
&#9;&#9;&#9;&#9;A[gi, gj] += K_local[i, j]<br>
&#9;<br>
&#9;def contribute_to_load(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;# Балка без распределенной нагрузки не вносит вклад в b<br>
&#9;&#9;pass<br>
&#9;<br>
&#9;def get_bending_moment(self, v1: float, theta1: float, <br>
&#9;&#9;&#9;&#9;&#9;&#9;v2: float, theta2: float, x: float) -&gt; float:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Вычислить изгибающий момент в точке x вдоль балки<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;v1, theta1: Прогиб и угол поворота в узле 1<br>
&#9;&#9;&#9;v2, theta2: Прогиб и угол поворота в узле 2<br>
&#9;&#9;&#9;x: Координата вдоль балки (0 &lt;= x &lt;= L)<br>
&#9;&#9;<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;Изгибающий момент M(x) [Н·м]<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;if x &lt; 0 or x &gt; self.L:<br>
&#9;&#9;&#9;raise ValueError(f&quot;x должен быть в диапазоне [0, {self.L}]&quot;)<br>
&#9;&#9;<br>
&#9;&#9;# Функции формы для изгиба балки<br>
&#9;&#9;L = self.L<br>
&#9;&#9;xi = x / L  # безразмерная координата<br>
&#9;&#9;<br>
&#9;&#9;# Вторые производные функций формы (кривизна)<br>
&#9;&#9;N1_dd = (6 - 12*xi) / L**2<br>
&#9;&#9;N2_dd = (4 - 6*xi) / L<br>
&#9;&#9;N3_dd = (-6 + 12*xi) / L**2<br>
&#9;&#9;N4_dd = (-2 + 6*xi) / L<br>
&#9;&#9;<br>
&#9;&#9;# Кривизна<br>
&#9;&#9;curvature = v1*N1_dd + theta1*N2_dd + v2*N3_dd + theta2*N4_dd<br>
&#9;&#9;<br>
&#9;&#9;# Изгибающий момент M = -E*I*d²v/dx²<br>
&#9;&#9;M = -self.E * self.I * curvature<br>
&#9;&#9;<br>
&#9;&#9;return M<br>
&#9;<br>
&#9;def get_shear_force(self, v1: float, theta1: float,<br>
&#9;&#9;&#9;&#9;&#9;v2: float, theta2: float, x: float) -&gt; float:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Вычислить поперечную силу в точке x<br>
&#9;&#9;<br>
&#9;&#9;Q(x) = -dM/dx<br>
&#9;&#9;<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;Поперечная сила Q(x) [Н]<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;if x &lt; 0 or x &gt; self.L:<br>
&#9;&#9;&#9;raise ValueError(f&quot;x должен быть в диапазоне [0, {self.L}]&quot;)<br>
&#9;&#9;<br>
&#9;&#9;# Третьи производные функций формы<br>
&#9;&#9;L = self.L<br>
&#9;&#9;xi = x / L<br>
&#9;&#9;<br>
&#9;&#9;N1_ddd = -12 / L**3<br>
&#9;&#9;N2_ddd = -6 / L**2<br>
&#9;&#9;N3_ddd = 12 / L**3<br>
&#9;&#9;N4_ddd = 6 / L**2<br>
&#9;&#9;<br>
&#9;&#9;# Поперечная сила Q = E*I*d³v/dx³<br>
&#9;&#9;Q = self.E * self.I * (v1*N1_ddd + theta1*N2_ddd + <br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;&#9;v2*N3_ddd + theta2*N4_ddd)<br>
&#9;&#9;<br>
&#9;&#9;return Q<br>
<br>
<br>
class DistributedLoad(Contribution):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Распределенная нагрузка на балочный элемент.<br>
&#9;<br>
&#9;Для равномерно распределенной нагрузки q [Н/м],<br>
&#9;эквивалентные узловые силы:<br>
&#9;F = (q*L/2) * [1, L/6, 1, -L/6]<br>
&#9;&quot;&quot;&quot;<br>
&#9;<br>
&#9;def __init__(self,<br>
&#9;&#9;&#9;&#9;node1_v: Variable,<br>
&#9;&#9;&#9;&#9;node1_theta: Variable,<br>
&#9;&#9;&#9;&#9;node2_v: Variable,<br>
&#9;&#9;&#9;&#9;node2_theta: Variable,<br>
&#9;&#9;&#9;&#9;q: float,  # интенсивность нагрузки [Н/м]<br>
&#9;&#9;&#9;&#9;L: float): # длина балки<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;node1_v, node1_theta: Прогиб и угол поворота узла 1<br>
&#9;&#9;&#9;node2_v, node2_theta: Прогиб и угол поворота узла 2<br>
&#9;&#9;&#9;q: Интенсивность распределенной нагрузки [Н/м] (положительная вниз)<br>
&#9;&#9;&#9;L: Длина балки [м]<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self.node1_v = node1_v<br>
&#9;&#9;self.node1_theta = node1_theta<br>
&#9;&#9;self.node2_v = node2_v<br>
&#9;&#9;self.node2_theta = node2_theta<br>
&#9;&#9;self.q = q<br>
&#9;&#9;self.L = L<br>
<br>
&#9;&#9;super().__init__(variables=[node1_v, node1_theta, node2_v, node2_theta])<br>
&#9;<br>
&#9;def contribute_to_stiffness(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;# Не влияет на матрицу жесткости<br>
&#9;&#9;pass<br>
&#9;<br>
&#9;def contribute_to_load(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;# Эквивалентные узловые силы для равномерной нагрузки<br>
&#9;&#9;q, L = self.q, self.L<br>
&#9;&#9;<br>
&#9;&#9;F = np.array([<br>
&#9;&#9;&#9;q * L / 2,      # сила в узле 1<br>
&#9;&#9;&#9;q * L**2 / 12,  # момент в узле 1<br>
&#9;&#9;&#9;q * L / 2,      # сила в узле 2<br>
&#9;&#9;&#9;-q * L**2 / 12  # момент в узле 2<br>
&#9;&#9;])<br>
&#9;&#9;<br>
&#9;&#9;global_indices = [<br>
&#9;&#9;&#9;index_map[self.node1_v][0],<br>
&#9;&#9;&#9;index_map[self.node1_theta][0],<br>
&#9;&#9;&#9;index_map[self.node2_v][0],<br>
&#9;&#9;&#9;index_map[self.node2_theta][0]<br>
&#9;&#9;]<br>
&#9;&#9;<br>
&#9;&#9;for i, idx in enumerate(global_indices):<br>
&#9;&#9;&#9;b[idx] += F[i]<br>
<br>
<br>
class Triangle3Node(Contribution):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Трехузловой треугольный элемент для плоско-напряженного состояния (plane stress).<br>
&#9;<br>
&#9;Каждый узел имеет 2 степени свободы: ux, uy (перемещения в плоскости).<br>
&#9;Используется линейная интерполяция перемещений.<br>
&#9;<br>
&#9;Это простейший элемент для 2D задач механики сплошной среды.<br>
&#9;Также известен как CST (Constant Strain Triangle).<br>
&#9;&quot;&quot;&quot;<br>
&#9;<br>
&#9;def __init__(self,<br>
&#9;&#9;&#9;&#9;node1: Variable,  # перемещения (ux1, uy1)<br>
&#9;&#9;&#9;&#9;node2: Variable,  # перемещения (ux2, uy2)<br>
&#9;&#9;&#9;&#9;node3: Variable,  # перемещения (ux3, uy3)<br>
&#9;&#9;&#9;&#9;coords1: np.ndarray,  # координаты узла 1 (x1, y1)<br>
&#9;&#9;&#9;&#9;coords2: np.ndarray,  # координаты узла 2 (x2, y2)<br>
&#9;&#9;&#9;&#9;coords3: np.ndarray,  # координаты узла 3 (x3, y3)<br>
&#9;&#9;&#9;&#9;E: float,         # модуль Юнга<br>
&#9;&#9;&#9;&#9;nu: float,        # коэффициент Пуассона<br>
&#9;&#9;&#9;&#9;thickness: float, # толщина пластины<br>
&#9;&#9;&#9;&#9;plane_stress: bool = True):  # True: plane stress, False: plane strain<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;node1, node2, node3: Переменные перемещений узлов (каждая размера 2)<br>
&#9;&#9;&#9;coords1, coords2, coords3: Координаты узлов [м]<br>
&#9;&#9;&#9;E: Модуль Юнга [Па]<br>
&#9;&#9;&#9;nu: Коэффициент Пуассона (0 &lt;= nu &lt; 0.5)<br>
&#9;&#9;&#9;thickness: Толщина пластины [м]<br>
&#9;&#9;&#9;plane_stress: True для плоско-напряженного состояния,<br>
&#9;&#9;&#9;&#9;&#9;&#9;False для плоской деформации<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self.node1 = node1<br>
&#9;&#9;self.node2 = node2<br>
&#9;&#9;self.node3 = node3<br>
<br>
&#9;&#9;super().__init__(variables=[node1, node2, node3])<br>
&#9;&#9;<br>
&#9;&#9;self.coords1 = np.array(coords1, dtype=float)<br>
&#9;&#9;self.coords2 = np.array(coords2, dtype=float)<br>
&#9;&#9;self.coords3 = np.array(coords3, dtype=float)<br>
&#9;&#9;<br>
&#9;&#9;self.E = E<br>
&#9;&#9;self.nu = nu<br>
&#9;&#9;self.thickness = thickness<br>
&#9;&#9;self.plane_stress = plane_stress<br>
&#9;&#9;<br>
&#9;&#9;# Проверки<br>
&#9;&#9;for node in [node1, node2, node3]:<br>
&#9;&#9;&#9;if node.size != 2:<br>
&#9;&#9;&#9;&#9;raise ValueError(f&quot;Узел {node.name} должен иметь размер 2 (ux, uy)&quot;)<br>
&#9;&#9;<br>
&#9;&#9;for coords in [self.coords1, self.coords2, self.coords3]:<br>
&#9;&#9;&#9;if len(coords) != 2:<br>
&#9;&#9;&#9;&#9;raise ValueError(&quot;Координаты должны быть 2D (x, y)&quot;)<br>
&#9;&#9;<br>
&#9;&#9;if not (0 &lt;= nu &lt; 0.5):<br>
&#9;&#9;&#9;raise ValueError(&quot;Коэффициент Пуассона должен быть в диапазоне [0, 0.5)&quot;)<br>
&#9;&#9;<br>
&#9;&#9;# Вычислить геометрические характеристики<br>
&#9;&#9;self._compute_geometry()<br>
&#9;&#9;<br>
&#9;&#9;# Вычислить матрицу жесткости<br>
&#9;&#9;self._compute_stiffness()<br>
&#9;<br>
&#9;def _compute_geometry(self):<br>
&#9;&#9;&quot;&quot;&quot;Вычислить площадь и производные функций формы&quot;&quot;&quot;<br>
&#9;&#9;x1, y1 = self.coords1<br>
&#9;&#9;x2, y2 = self.coords2<br>
&#9;&#9;x3, y3 = self.coords3<br>
&#9;&#9;<br>
&#9;&#9;# Площадь треугольника (удвоенная)<br>
&#9;&#9;self.area_2 = (x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)<br>
&#9;&#9;<br>
&#9;&#9;if abs(self.area_2) &lt; 1e-10:<br>
&#9;&#9;&#9;raise ValueError(&quot;Узлы треугольника лежат на одной прямой (нулевая площадь)&quot;)<br>
&#9;&#9;<br>
&#9;&#9;self.area = abs(self.area_2) / 2<br>
&#9;&#9;<br>
&#9;&#9;# Производные функций формы (константы для линейного треугольника)<br>
&#9;&#9;# dN/dx и dN/dy для каждой из трех функций формы<br>
&#9;&#9;self.dN_dx = np.array([<br>
&#9;&#9;&#9;(y2 - y3) / self.area_2,<br>
&#9;&#9;&#9;(y3 - y1) / self.area_2,<br>
&#9;&#9;&#9;(y1 - y2) / self.area_2<br>
&#9;&#9;])<br>
&#9;&#9;<br>
&#9;&#9;self.dN_dy = np.array([<br>
&#9;&#9;&#9;(x3 - x2) / self.area_2,<br>
&#9;&#9;&#9;(x1 - x3) / self.area_2,<br>
&#9;&#9;&#9;(x2 - x1) / self.area_2<br>
&#9;&#9;])<br>
&#9;<br>
&#9;def _get_constitutive_matrix(self) -&gt; np.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Матрица упругости D (связь напряжений и деформаций)<br>
&#9;&#9;<br>
&#9;&#9;Для плоско-напряженного состояния:<br>
&#9;&#9;D = (E/(1-nu²)) * [[1,  nu,    0      ],<br>
&#9;&#9;&#9;&#9;&#9;&#9;[nu, 1,     0      ],<br>
&#9;&#9;&#9;&#9;&#9;&#9;[0,  0,  (1-nu)/2 ]]<br>
&#9;&#9;<br>
&#9;&#9;Для плоской деформации:<br>
&#9;&#9;D = (E/((1+nu)(1-2nu))) * [[1-nu,  nu,        0      ],<br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;&#9;&#9;[nu,    1-nu,      0      ],<br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;&#9;&#9;[0,     0,    (1-2nu)/2 ]]<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;E = self.E<br>
&#9;&#9;nu = self.nu<br>
&#9;&#9;<br>
&#9;&#9;if self.plane_stress:<br>
&#9;&#9;&#9;c = E / (1 - nu**2)<br>
&#9;&#9;&#9;D = c * np.array([<br>
&#9;&#9;&#9;&#9;[1,  nu,         0        ],<br>
&#9;&#9;&#9;&#9;[nu, 1,          0        ],<br>
&#9;&#9;&#9;&#9;[0,  0,  (1 - nu) / 2     ]<br>
&#9;&#9;&#9;])<br>
&#9;&#9;else:  # plane strain<br>
&#9;&#9;&#9;c = E / ((1 + nu) * (1 - 2*nu))<br>
&#9;&#9;&#9;D = c * np.array([<br>
&#9;&#9;&#9;&#9;[1 - nu,  nu,            0           ],<br>
&#9;&#9;&#9;&#9;[nu,      1 - nu,        0           ],<br>
&#9;&#9;&#9;&#9;[0,       0,       (1 - 2*nu) / 2    ]<br>
&#9;&#9;&#9;])<br>
&#9;&#9;<br>
&#9;&#9;return D<br>
&#9;<br>
&#9;def _get_B_matrix(self) -&gt; np.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Матрица деформаций B (связь деформаций и перемещений)<br>
&#9;&#9;<br>
&#9;&#9;Деформации: epsilon = [epsilon_xx, epsilon_yy, gamma_xy]^T<br>
&#9;&#9;Перемещения: u = [ux1, uy1, ux2, uy2, ux3, uy3]^T<br>
&#9;&#9;<br>
&#9;&#9;epsilon = B * u<br>
&#9;&#9;<br>
&#9;&#9;B = [[dN1/dx,    0,    dN2/dx,    0,    dN3/dx,    0   ],<br>
&#9;&#9;&#9;[   0,    dN1/dy,    0,    dN2/dy,    0,    dN3/dy],<br>
&#9;&#9;&#9;[dN1/dy, dN1/dx, dN2/dy, dN2/dx, dN3/dy, dN3/dx]]<br>
&#9;&#9;<br>
&#9;&#9;Размер: 3x6<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;dN_dx = self.dN_dx<br>
&#9;&#9;dN_dy = self.dN_dy<br>
&#9;&#9;<br>
&#9;&#9;B = np.array([<br>
&#9;&#9;&#9;[dN_dx[0], 0,        dN_dx[1], 0,        dN_dx[2], 0       ],<br>
&#9;&#9;&#9;[0,        dN_dy[0], 0,        dN_dy[1], 0,        dN_dy[2]],<br>
&#9;&#9;&#9;[dN_dy[0], dN_dx[0], dN_dy[1], dN_dx[1], dN_dy[2], dN_dx[2]]<br>
&#9;&#9;])<br>
&#9;&#9;<br>
&#9;&#9;return B<br>
&#9;<br>
&#9;def _compute_stiffness(self):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Вычислить матрицу жесткости элемента<br>
&#9;&#9;<br>
&#9;&#9;K = t * A * B^T * D * B<br>
&#9;&#9;<br>
&#9;&#9;где:<br>
&#9;&#9;t - толщина<br>
&#9;&#9;A - площадь треугольника<br>
&#9;&#9;B - матрица деформаций (3x6)<br>
&#9;&#9;D - матрица упругости (3x3)<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;D = self._get_constitutive_matrix()<br>
&#9;&#9;B = self._get_B_matrix()<br>
&#9;&#9;<br>
&#9;&#9;# K = t * A * B^T * D * B<br>
&#9;&#9;self.K = self.thickness * self.area * (B.T @ D @ B)<br>
&#9;<br>
&#9;def contribute_to_stiffness(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;# Получить глобальные индексы всех DOF<br>
&#9;&#9;# Порядок: [ux1, uy1, ux2, uy2, ux3, uy3]<br>
&#9;&#9;global_indices = []<br>
&#9;&#9;for node in [self.node1, self.node2, self.node3]:<br>
&#9;&#9;&#9;global_indices.extend(index_map[node])<br>
&#9;&#9;<br>
&#9;&#9;# Добавить локальную матрицу в глобальную<br>
&#9;&#9;for i, gi in enumerate(global_indices):<br>
&#9;&#9;&#9;for j, gj in enumerate(global_indices):<br>
&#9;&#9;&#9;&#9;A[gi, gj] += self.K[i, j]<br>
&#9;<br>
&#9;def contribute_to_load(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;# Треугольник без объемных сил не вносит вклад в b<br>
&#9;&#9;pass<br>
&#9;<br>
&#9;def get_stress(self, u: np.ndarray) -&gt; np.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Вычислить напряжения в элементе по вектору перемещений узлов<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;u: Вектор перемещений [ux1, uy1, ux2, uy2, ux3, uy3]<br>
&#9;&#9;<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;Напряжения [sigma_xx, sigma_yy, tau_xy] [Па]<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;if len(u) != 6:<br>
&#9;&#9;&#9;raise ValueError(&quot;Вектор перемещений должен иметь размер 6&quot;)<br>
&#9;&#9;<br>
&#9;&#9;D = self._get_constitutive_matrix()<br>
&#9;&#9;B = self._get_B_matrix()<br>
&#9;&#9;<br>
&#9;&#9;# Деформации: epsilon = B * u<br>
&#9;&#9;strain = B @ u<br>
&#9;&#9;<br>
&#9;&#9;# Напряжения: sigma = D * epsilon<br>
&#9;&#9;stress = D @ strain<br>
&#9;&#9;<br>
&#9;&#9;return stress<br>
&#9;<br>
&#9;def get_strain(self, u: np.ndarray) -&gt; np.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Вычислить деформации в элементе<br>
&#9;&#9;<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;Деформации [epsilon_xx, epsilon_yy, gamma_xy]<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;if len(u) != 6:<br>
&#9;&#9;&#9;raise ValueError(&quot;Вектор перемещений должен иметь размер 6&quot;)<br>
&#9;&#9;<br>
&#9;&#9;B = self._get_B_matrix()<br>
&#9;&#9;strain = B @ u<br>
&#9;&#9;<br>
&#9;&#9;return strain<br>
<br>
<br>
class BodyForce(Contribution):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Объемная сила для треугольного элемента<br>
&#9;(например, сила тяжести, центробежная сила)<br>
&#9;&quot;&quot;&quot;<br>
&#9;<br>
&#9;def __init__(self,<br>
&#9;&#9;&#9;&#9;node1: Variable,<br>
&#9;&#9;&#9;&#9;node2: Variable,<br>
&#9;&#9;&#9;&#9;node3: Variable,<br>
&#9;&#9;&#9;&#9;area: float,<br>
&#9;&#9;&#9;&#9;thickness: float,<br>
&#9;&#9;&#9;&#9;force_density: np.ndarray):  # [fx, fy] - сила на единицу объема [Н/м³]<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;node1, node2, node3: Узлы элемента<br>
&#9;&#9;&#9;area: Площадь треугольника [м²]<br>
&#9;&#9;&#9;thickness: Толщина [м]<br>
&#9;&#9;&#9;force_density: Плотность объемной силы [fx, fy] [Н/м³]<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self.node1 = node1<br>
&#9;&#9;self.node2 = node2<br>
&#9;&#9;self.node3 = node3<br>
&#9;&#9;self.area = area<br>
&#9;&#9;self.thickness = thickness<br>
&#9;&#9;self.force_density = np.array(force_density, dtype=float)<br>
<br>
&#9;&#9;super().__init__(variables=[node1, node2, node3])<br>
&#9;&#9;<br>
&#9;&#9;if len(self.force_density) != 2:<br>
&#9;&#9;&#9;raise ValueError(&quot;Плотность силы должна быть 2D вектором&quot;)<br>
&#9;<br>
&#9;def contribute_to_stiffness(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;pass<br>
&#9;<br>
&#9;def contribute_to_load(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;# Для линейного треугольника с равномерной объемной силой,<br>
&#9;&#9;# эквивалентные узловые силы: F_node = (volume / 3) * force_density<br>
&#9;&#9;volume = self.area * self.thickness<br>
&#9;&#9;F_node = (volume / 3) * self.force_density<br>
&#9;&#9;<br>
&#9;&#9;# Каждый узел получает 1/3 от общей силы<br>
&#9;&#9;for node in [self.node1, self.node2, self.node3]:<br>
&#9;&#9;&#9;indices = index_map[node]<br>
&#9;&#9;&#9;for i, idx in enumerate(indices):<br>
&#9;&#9;&#9;&#9;b[idx] += F_node[i]<br>
<!-- END SCAT CODE -->
</body>
</html>
