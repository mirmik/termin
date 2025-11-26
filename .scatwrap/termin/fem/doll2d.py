<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/doll2d.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
<br>
#!/usr/bin/env python3<br>
&quot;&quot;&quot;<br>
Редуцированная многотельная динамика 2D на основе дерева звеньев.<br>
<br>
Doll2D - система из звеньев (links), соединенных шарнирами (joints).<br>
Каждый шарнир имеет обобщенную координату (угол для RotatorJoint).<br>
<br>
Динамика формируется через уравнения Лагранжа:<br>
&#9;M(q)·q̈ + C(q,q̇)·q̇ + g(q) = τ<br>
<br>
где:<br>
- M(q) - матрица масс (зависит от конфигурации)<br>
- C(q,q̇) - кориолисовы и центробежные силы<br>
- g(q) - гравитационные силы<br>
- τ - приложенные моменты/силы<br>
&quot;&quot;&quot;<br>
<br>
import numpy as np<br>
from typing import List, Dict, Optional<br>
from termin.fem.assembler import MatrixAssembler, Variable, Contribution, Constraint<br>
from termin.fem.inertia2d import SpatialInertia2D<br>
from termin.geombase.pose2 import Pose2<br>
from termin.geombase.screw import Screw2, cross2d_scalar<br>
<br>
<br>
class Doll2D(Contribution):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Редуцированная многотельная система 2D.<br>
&#9;<br>
&#9;Представляет собой дерево звеньев, соединенных шарнирами.<br>
&#9;Формирует матрицу масс M(q) и вектор обобщенных сил для решателя.<br>
&#9;<br>
&#9;Атрибуты:<br>
&#9;&#9;base: Базовое звено (корень дерева)<br>
&#9;&#9;links: Список всех звеньев<br>
&#9;&#9;joints: Список всех шарниров<br>
&#9;&#9;variables: Список переменных (скорости шарниров)<br>
&#9;&quot;&quot;&quot;<br>
&#9;<br>
&#9;def __init__(self, base_link=None, assembler=None):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;base_link: Корневое звено (None = земля)<br>
&#9;&#9;&#9;assembler: MatrixAssembler для автоматической регистрации<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self.base = base_link<br>
&#9;&#9;self.links: List[DollLink2D] = []<br>
&#9;&#9;self.joints: List[DollJoint2D] = []<br>
&#9;&#9;self.gravity = np.array([0.0, -9.81])  # [м/с²]<br>
&#9;&#9;<br>
&#9;&#9;# Соберем переменные из шарниров<br>
&#9;&#9;variables = []<br>
&#9;&#9;if base_link:<br>
&#9;&#9;&#9;self._collect_joints(base_link)<br>
&#9;&#9;&#9;variables = [var for joint in self.joints for var in joint.get_variables()]<br>
<br>
&#9;&#9;print(&quot;HERE!!!!&quot;)<br>
&#9;&#9;print(variables)<br>
<br>
&#9;&#9;super().__init__(variables, assembler=assembler)<br>
&#9;<br>
&#9;def _collect_joints(self, link: 'DollLink2D'):<br>
&#9;&#9;&quot;&quot;&quot;Рекурсивно собрать все звенья и шарниры из дерева.&quot;&quot;&quot;<br>
&#9;&#9;if link not in self.links:<br>
&#9;&#9;&#9;self.links.append(link)<br>
<br>
&#9;&#9;if link.joint and link.joint not in self.joints:<br>
&#9;&#9;&#9;self.joints.append(link.joint)<br>
<br>
&#9;&#9;for child in link.children:<br>
&#9;&#9;&#9;self._collect_joints(child)<br>
&#9;<br>
&#9;def add_link(self, link: 'DollLink2D'):<br>
&#9;&#9;&quot;&quot;&quot;Добавить звено в систему.&quot;&quot;&quot;<br>
&#9;&#9;if link not in self.links:<br>
&#9;&#9;&#9;self.links.append(link)<br>
&#9;<br>
&#9;def update_kinematics(self):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Обновить прямую кинематику всех звеньев.<br>
&#9;&#9;Вычисляет положения и скорости на основе текущих значений переменных.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;if self.base:<br>
&#9;&#9;&#9;base_pose = Pose2.identity()<br>
&#9;&#9;&#9;base_twist = Screw2(ang=np.array([0.0]), lin=np.zeros(2))<br>
&#9;&#9;&#9;self._update_link_kinematics(self.base, base_pose, base_twist)<br>
&#9;<br>
&#9;def _update_link_kinematics(self, link: 'DollLink2D',<br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;&#9;pose: Pose2,<br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;&#9;twist: Screw2):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Рекурсивно обновить кинематику звена и его потомков.<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;link: Текущее звено<br>
&#9;&#9;&#9;pose: Поза точки привязки<br>
&#9;&#9;&#9;twist: Твист точки привязки (винт скоростей)<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;# Обновляем текущее звено<br>
&#9;&#9;link.pose = pose<br>
&#9;&#9;link.twist = twist<br>
&#9;&#9;<br>
&#9;&#9;# Обновляем детей через их шарниры<br>
&#9;&#9;for child in link.children:<br>
&#9;&#9;&#9;if child.joint:<br>
&#9;&#9;&#9;&#9;child_pose = child.joint.pose_after_joint(link.pose)<br>
&#9;&#9;&#9;&#9;child_twist = child.joint.twist_after_joint(link.twist)<br>
&#9;&#9;&#9;&#9;self._update_link_kinematics(child, child_pose, child_twist)<br>
&#9;<br>
&#9;def contribute_to_mass(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Добавить матрицу масс M(q) в глобальную матрицу.<br>
&#9;&#9;<br>
&#9;&#9;Для редуцированной системы: M(q) связывает ускорения с силами.<br>
&#9;&#9;M строится через якобианы: M = Σ (J_i^T · M_body_i · J_i)<br>
&#9;&#9;<br>
&#9;&#9;где J_i - якобиан i-го тела относительно обобщенных координат.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;# Собираем вклады от всех звеньев<br>
&#9;&#9;if self.base:<br>
&#9;&#9;&#9;self.base.contribute_subtree_inertia(A, index_map)<br>
&#9;<br>
&#9;def contribute_to_b(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Добавить обобщенные силы в правую часть.<br>
&#9;&#9;<br>
&#9;&#9;Включает:<br>
&#9;&#9;- Гравитационные силы: Q_g = -∂V/∂q<br>
&#9;&#9;- Кориолисовы силы: Q_c = -C(q,q̇)·q̇<br>
&#9;&#9;- Приложенные моменты<br>
&#9;&#9;&quot;&quot;&quot;        <br>
&#9;&#9;# Рекурсивно вычисляем силы, спускаясь по дереву<br>
&#9;&#9;if self.base:<br>
&#9;&#9;&#9;self.base.contribute_subtree_forces(self.gravity, b, index_map)<br>
&#9;<br>
&#9;def get_kinetic_energy(self) -&gt; float:<br>
&#9;&#9;&quot;&quot;&quot;Вычислить полную кинетическую энергию системы.&quot;&quot;&quot;<br>
&#9;&#9;energy = 0.0<br>
&#9;&#9;for link in self.links:<br>
&#9;&#9;&#9;if link.inertia:<br>
&#9;&#9;&#9;&#9;v = link.twist.vector()<br>
&#9;&#9;&#9;&#9;omega = link.twist.moment()<br>
&#9;&#9;&#9;&#9;energy += link.inertia.get_kinetic_energy(v, omega)<br>
&#9;&#9;return energy<br>
<br>
<br>
<br>
class DollJoint2D:<br>
&#9;&quot;&quot;&quot;<br>
&#9;Базовый класс для шарнира в Doll2D.<br>
&#9;<br>
&#9;Шарнир связывает родительское и дочернее звено,<br>
&#9;определяет обобщенную координату и кинематику.<br>
&#9;&quot;&quot;&quot;<br>
&#9;<br>
&#9;def __init__(self, name: str = &quot;joint&quot;):<br>
&#9;&#9;self.name = name<br>
&#9;&#9;self.parent_link: Optional['DollLink2D'] = None<br>
&#9;&#9;self.child_link: Optional['DollLink2D'] = None<br>
&#9;<br>
&#9;def get_variables(self) -&gt; List[Variable]:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Вернуть список переменных, связанных с этим шарниром.<br>
&#9;&#9;<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;Список переменных (может быть пустым для фиксированных шарниров)<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;return []<br>
&#9;<br>
&#9;def project_wrench(self, wrench: Screw2, index_map: Dict[Variable, List[int]], b: np.ndarray):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Спроецировать вренч на ось шарнира и добавить в вектор обобщенных сил.<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;wrench: Вренч сил (Screw2) в точке привязки дочернего звена<br>
&#9;&#9;&#9;index_map: Отображение переменных на индексы<br>
&#9;&#9;&#9;b: Вектор обобщенных сил<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;pass  # Фиксированный шарнир не имеет степеней свободы<br>
&#9;<br>
&#9;def inverse_transform_wrench(self, wrench: Screw2) -&gt; Screw2:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Обратная трансформация вренча через шарнир (от child к parent).<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;wrench: Вренч в точке привязки дочернего звена<br>
&#9;&#9;&#9;<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;Вренч в точке привязки родительского звена<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;raise NotImplementedError(&quot;Метод должен быть реализован в подклассе&quot;)<br>
&#9;<br>
&#9;def pose_after_joint(self, parent_pose: Pose2) -&gt; Pose2:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Вычислить позу дочернего звена на основе позы родителя.<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;parent_pose: Поза точки привязки родителя<br>
&#9;&#9;&#9;<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;Поза точки привязки ребенка<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;raise NotImplementedError(&quot;Метод должен быть реализован в подклассе&quot;)<br>
&#9;<br>
&#9;def twist_after_joint(self, parent_twist: Screw2) -&gt; Screw2:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Вычислить твист дочернего звена на основе твиста родителя.<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;parent_twist: Твист точки привязки родителя<br>
&#9;&#9;&#9;<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;Твист точки привязки ребенка<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;raise NotImplementedError(&quot;Метод должен быть реализован в подклассе&quot;)<br>
&#9;<br>
<br>
class DollLink2D:<br>
&#9;&quot;&quot;&quot;<br>
&#9;Звено в Doll2D - твердое тело в цепи.<br>
&#9;<br>
&#9;Атрибуты:<br>
&#9;&#9;name: Имя звена<br>
&#9;&#9;parent: Родительское звено<br>
&#9;&#9;children: Дочерние звенья<br>
&#9;&#9;joint: Шарнир, связывающий это звено с родителем<br>
&#9;&#9;inertia: Инерционные характеристики (масса, момент инерции, ЦМ)<br>
&#9;&#9;<br>
&#9;&#9;# Состояние (вычисляется кинематикой):<br>
&#9;&#9;pose: Поза точки привязки (Pose2)<br>
&#9;&#9;twist: Твист точки привязки (Screw2 - винт скоростей)<br>
&#9;&quot;&quot;&quot;<br>
&#9;<br>
&#9;def __init__(self, name: str = &quot;link&quot;, inertia: 'SpatialInertia2D' = SpatialInertia2D()):<br>
&#9;&#9;self.name = name<br>
&#9;&#9;self.children: List['DollLink2D'] = []<br>
&#9;&#9;self.parent: Optional['DollLink2D'] = None<br>
&#9;&#9;self.joint: Optional[DollJoint2D] = None<br>
&#9;&#9;self.inertia = inertia<br>
&#9;&#9;<br>
&#9;&#9;# Кинематическое состояние<br>
&#9;&#9;self.pose = Pose2.identity()<br>
&#9;&#9;self.twist = Screw2(ang=np.array([0.0]), lin=np.zeros(2))<br>
&#9;<br>
&#9;def add_child(self, child: 'DollLink2D', joint: DollJoint2D):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Добавить дочернее звено через шарнир.<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;child: Дочернее звено<br>
&#9;&#9;&#9;joint: Шарнир, соединяющий parent и child<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;child.parent = self<br>
&#9;&#9;child.joint = joint<br>
&#9;&#9;joint.parent_link = self<br>
&#9;&#9;joint.child_link = child<br>
&#9;&#9;self.children.append(child)<br>
&#9;<br>
&#9;def gravity_wrench(self, gravity: np.ndarray) -&gt; Screw2:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Вычислить вренч гравитационной силы, действующей на звено.<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;gravity: Вектор гравитации [м/с²]<br>
&#9;&#9;&#9;<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;Вренч гравитации (момент + сила) в точке привязки звена<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;if not self.inertia:<br>
&#9;&#9;&#9;return Screw2(ang=np.array([0.0]), lin=np.zeros(2))<br>
&#9;&#9;<br>
&#9;&#9;return self.inertia.gravity_wrench(self.pose, gravity)<br>
&#9;<br>
&#9;def local_wrench(self, gravity: np.ndarray) -&gt; Screw2:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Вычислить суммарный вренч всех сил, действующих на звено.<br>
&#9;&#9;Включает:<br>
&#9;&#9;- гравитацию<br>
&#9;&#9;- кориолисовы и центробежные силы<br>
&#9;&#9;- (в будущем) внешние силы<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;wrench = self.gravity_wrench(gravity)<br>
<br>
&#9;&#9;coriolis_wrench = self.coriolis_wrench()<br>
&#9;&#9;if coriolis_wrench is not None:<br>
&#9;&#9;&#9;wrench += coriolis_wrench<br>
<br>
&#9;&#9;# TODO: добавить внешние силы<br>
&#9;&#9;return wrench<br>
<br>
<br>
&#9;def coriolis_wrench(self) -&gt; Optional[Screw2]:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Вычислить вренч кориолисовых и центробежных сил для звена.<br>
<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;Screw2: (момент, сила) в мировой СК, либо None, если звено неподвижно<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;if not self.inertia or self.twist is None:<br>
&#9;&#9;&#9;return None<br>
<br>
&#9;&#9;ω = float(self.twist.ang.flatten()[0])<br>
&#9;&#9;v = self.twist.lin<br>
<br>
&#9;&#9;# если скорости нулевые — можно не считать<br>
&#9;&#9;if abs(ω) &lt; 1e-12 and np.linalg.norm(v) &lt; 1e-12:<br>
&#9;&#9;&#9;return None<br>
<br>
&#9;&#9;# Центр масс в мировой СК<br>
&#9;&#9;r_c = self.pose.rotation_matrix() @ self.inertia.com  # com — в локальной СК<br>
<br>
&#9;&#9;# Скорость центра масс<br>
&#9;&#9;v_c = v + ω * np.array([-r_c[1], r_c[0]])<br>
<br>
&#9;&#9;# Кориолисовая сила<br>
&#9;&#9;F_c = self.inertia.mass * ω * np.array([-v_c[1], v_c[0]])<br>
<br>
&#9;&#9;# Момент относительно точки привязки<br>
&#9;&#9;M_c = r_c[0] * F_c[1] - r_c[1] * F_c[0]<br>
<br>
&#9;&#9;return Screw2(ang=np.array([M_c]), lin=F_c)<br>
&#9;<br>
&#9;def contribute_subtree_forces(self, gravity: np.ndarray, <br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;&#9;b: np.ndarray, <br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;&#9;index_map: Dict[Variable, List[int]]) -&gt; Screw2:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Рекурсивно вычислить суммарный вренч сил для поддерева.<br>
&#9;&#9;<br>
&#9;&#9;Алгоритм:<br>
&#9;&#9;1. Вычисляем вренч сил на текущем звене (гравитация, внешние силы)<br>
&#9;&#9;2. Рекурсивно получаем вренчи от детей<br>
&#9;&#9;3. Трансформируем вренчи детей в точку привязки текущего звена<br>
&#9;&#9;4. Суммируем все вренчи<br>
&#9;&#9;5. Проецируем на шарнир текущего звена (если есть)<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;gravity: Вектор гравитации [м/с²]<br>
&#9;&#9;&#9;b: Вектор обобщенных сил<br>
&#9;&#9;&#9;index_map: Отображение переменных на индексы<br>
&#9;&#9;&#9;<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;Суммарный вренч сил, действующих на поддерево (в точке привязки)<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;# 1. Вренч сил на текущем звене<br>
&#9;&#9;wrench_link = self.local_wrench(gravity)<br>
&#9;&#9;<br>
&#9;&#9;# 2. Собираем вренчи от детей<br>
&#9;&#9;total_wrench = wrench_link<br>
&#9;&#9;for child in self.children:<br>
&#9;&#9;&#9;# Рекурсивно получаем вренч поддерева ребенка<br>
&#9;&#9;&#9;child_wrench = child.contribute_subtree_forces(gravity, b, index_map)<br>
&#9;&#9;&#9;<br>
&#9;&#9;&#9;# Трансформируем вренч ребенка в точку привязки текущего звена<br>
&#9;&#9;&#9;# Используем обратную трансформацию через шарнир ребенка<br>
&#9;&#9;&#9;child_wrench = child.joint.inverse_transform_wrench(child_wrench)<br>
&#9;&#9;&#9;<br>
&#9;&#9;&#9;total_wrench = total_wrench + child_wrench<br>
&#9;&#9;<br>
&#9;&#9;# 3. Проецируем на шарнир текущего звена<br>
&#9;&#9;# Обобщенная сила = проекция вренча на оси шарнира<br>
&#9;&#9;# Для фиксированного шарнира (без переменных) project_wrench ничего не делает<br>
&#9;&#9;if self.joint:<br>
&#9;&#9;&#9;self.joint.project_wrench(total_wrench, index_map, b)<br>
&#9;&#9;<br>
&#9;&#9;return total_wrench<br>
&#9;<br>
&#9;def contribute_subtree_inertia(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Рекурсивно собрать spatial inertia от поддерева, проецировать на переменные.<br>
&#9;&#9;Алгоритм:<br>
&#9;&#9;1. Собрать spatial inertia от детей, трансформировать к текущему звену<br>
&#9;&#9;2. Суммировать с собственной инерцией<br>
&#9;&#9;3. Проецировать итоговую spatial inertia на переменные звена (через якобиан)<br>
&#9;&#9;4. Рекурсивно пройти по дереву<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;# 1. Собираем spatial inertia от детей<br>
&#9;&#9;subtree_inertia = SpatialInertia2D(0.0, 0.0, np.zeros(2))<br>
&#9;&#9;for child in self.children:<br>
&#9;&#9;&#9;child_inertia = child.contribute_subtree_inertia(A, index_map)<br>
&#9;&#9;&#9;child_inertia = child_inertia.transform_by(child.joint.child_pose_in_joint)<br>
&#9;&#9;&#9;subtree_inertia = subtree_inertia + child_inertia<br>
<br>
&#9;&#9;# 2. Суммируем с собственной инерцией<br>
&#9;&#9;total_inertia = subtree_inertia + self.inertia<br>
<br>
&#9;&#9;# 3. Проецируем через шарнир (если есть)<br>
&#9;&#9;if self.joint:<br>
&#9;&#9;&#9;self.joint.project_inertia(total_inertia, A, index_map)<br>
<br>
&#9;&#9;# 4. Возвращаем spatial inertia поддерева для родителя<br>
&#9;&#9;return total_inertia<br>
&#9;<br>
&#9;def __repr__(self):<br>
&#9;&#9;return f&quot;DollLink2D({self.name})&quot;<br>
&#9;&#9;<br>
<br>
class DollRotatorJoint2D(DollJoint2D):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Вращательный шарнир для Doll2D.<br>
&#9;<br>
&#9;Связывает родительское и дочернее звено через угловую координату.<br>
&#9;<br>
&#9;Атрибуты:<br>
&#9;&#9;omega: Переменная угловой скорости [рад/с]<br>
&#9;&#9;angle: Текущий угол [рад] (интегрируется из omega)<br>
&#9;&#9;joint_pose_in_parent: Поза шарнира в системе координат родителя<br>
&#9;&#9;child_pose_in_joint: Поза точки привязки ребенка в системе шарнира<br>
&#9;&quot;&quot;&quot;<br>
&#9;<br>
&#9;def __init__(self, <br>
&#9;&#9;&#9;&#9;name: str = &quot;rotator_joint&quot;,<br>
&#9;&#9;&#9;&#9;joint_pose_in_parent: Pose2 = None,<br>
&#9;&#9;&#9;&#9;child_pose_in_joint: Pose2 = None,<br>
&#9;&#9;&#9;&#9;assembler=None):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;name: Имя шарнира<br>
&#9;&#9;&#9;joint_pose_in_parent: Поза шарнира в СК родителя<br>
&#9;&#9;&#9;child_pose_in_joint: Поза точки привязки ребенка в СК шарнира<br>
&#9;&#9;&#9;assembler: MatrixAssembler для регистрации переменной<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;super().__init__(name)<br>
&#9;&#9;self.omega = Variable(name=f&quot;{name}_omega&quot;, size=1)<br>
&#9;&#9;self.angle = 0.0  # текущий угол (интегрируется)<br>
&#9;&#9;<br>
&#9;&#9;self.joint_pose_in_parent = joint_pose_in_parent if joint_pose_in_parent is not None else Pose2.identity()<br>
&#9;&#9;self.child_pose_in_joint = child_pose_in_joint if child_pose_in_joint is not None else Pose2.identity()<br>
&#9;&#9;<br>
&#9;&#9;if assembler:<br>
&#9;&#9;&#9;assembler.add_variable(self.omega)<br>
&#9;<br>
&#9;def get_variables(self) -&gt; List[Variable]:<br>
&#9;&#9;&quot;&quot;&quot;Вернуть список переменных шарнира.&quot;&quot;&quot;<br>
&#9;&#9;return [self.omega]<br>
&#9;<br>
&#9;def project_wrench(self, wrench: Screw2, index_map: Dict[Variable, List[int]], b: np.ndarray):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Спроецировать вренч на ось вращательного шарнира.<br>
&#9;&#9;<br>
&#9;&#9;Для вращательного шарнира обобщенная сила = момент (угловая компонента вренча).<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;wrench: Вренч сил в точке привязки дочернего звена<br>
&#9;&#9;&#9;index_map: Отображение переменных на индексы<br>
&#9;&#9;&#9;b: Вектор обобщенных сил<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;idx = index_map[self.omega][0]<br>
&#9;&#9;# Обобщенная сила для вращательного шарнира = момент<br>
&#9;&#9;b[idx] += wrench.moment()<br>
<br>
&#9;def project_inertia(self, inertia: 'SpatialInertia2D',<br>
&#9;&#9;&#9;&#9;&#9;A: np.ndarray,<br>
&#9;&#9;&#9;&#9;&#9;index_map: Dict[Variable, List[int]]):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Проецировать spatial inertia на матрицу масс через вращательный DOF.<br>
&#9;&#9;Эквивалентно вычислению M_ii = Sᵀ I S, где S — ось вращения.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;vars = self.get_variables()<br>
&#9;&#9;if not vars:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;<br>
&#9;&#9;idx = index_map[vars[0]][0]<br>
<br>
&#9;&#9;# Вращения в локальной СК шарнира в плоскости xy<br>
&#9;&#9;S = np.array([1.0, 0.0, 0.0])  # [ω, vx, vy]<br>
<br>
&#9;&#9;# Преобразуем ось в систему родителя<br>
&#9;&#9;R = self.joint_pose_in_parent.rotation_matrix()<br>
&#9;&#9;S_world = np.array([S[0], *(R @ S[1:])])  # [ω, vx, vy]<br>
<br>
&#9;&#9;# Spatial inertia в матричном виде<br>
&#9;&#9;I = inertia.to_matrix()  # 3x3<br>
<br>
&#9;&#9;# M_ii = Sᵀ I S<br>
&#9;&#9;Mjj = float(S_world @ (I @ S_world))<br>
<br>
&#9;&#9;# Записываем в глобальную матрицу масс<br>
&#9;&#9;A[idx, idx] += Mjj<br>
&#9;<br>
&#9;def inverse_transform_wrench(self, wrench: Screw2) -&gt; Screw2:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Обратная трансформация вренча через вращательный шарнир (от child к parent).<br>
&#9;&#9;<br>
&#9;&#9;Вренч трансформируется обратно по цепочке:<br>
&#9;&#9;child -&gt; child_pose_in_joint^-1 -&gt; rotation^-1 -&gt; joint_pose_in_parent^-1 -&gt; parent<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;wrench: Вренч в точке привязки дочернего звена<br>
&#9;&#9;&#9;<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;Вренч в точке привязки родительского звена<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;# Обратная трансформация по цепочке<br>
&#9;&#9;result = wrench.inverse_transform_as_wrench_by(self.child_pose_in_joint)<br>
&#9;&#9;joint_rotation = Pose2.rotation(self.angle)<br>
&#9;&#9;result = result.inverse_transform_as_wrench_by(joint_rotation)<br>
&#9;&#9;result = result.inverse_transform_as_wrench_by(self.joint_pose_in_parent)<br>
&#9;&#9;return result<br>
&#9;<br>
&#9;def pose_after_joint(self, parent_pose: Pose2) -&gt; Pose2:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Вычислить позу дочернего звена на основе позы родителя.<br>
&#9;&#9;<br>
&#9;&#9;Композиция поз:<br>
&#9;&#9;child_pose = parent_pose * joint_pose_in_parent * rotation(angle) * child_pose_in_joint<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;parent_pose: Поза точки привязки родителя<br>
&#9;&#9;&#9;<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;Поза точки привязки ребенка<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;joint_rotation = Pose2.rotation(self.angle)<br>
&#9;&#9;joint_pose = parent_pose * self.joint_pose_in_parent * joint_rotation<br>
&#9;&#9;child_pose = joint_pose * self.child_pose_in_joint<br>
&#9;&#9;return child_pose<br>
&#9;<br>
&#9;def joint_twist_in_joint(self) -&gt; Screw2:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Вычислить твист шарнира в его собственной системе координат.<br>
&#9;&#9;<br>
&#9;&#9;Возвращает твист, соответствующий собственной угловой скорости шарнира.<br>
&#9;&#9;<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;Твист шарнира в его системе координат<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;return Screw2(<br>
&#9;&#9;&#9;ang=self.omega.value,<br>
&#9;&#9;&#9;lin=np.zeros(2)<br>
&#9;&#9;)<br>
<br>
&#9;def twist_after_joint(self, parent_twist: Screw2) -&gt; Screw2:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Вычислить твист дочернего звена на основе твиста родителя.<br>
&#9;&#9;<br>
&#9;&#9;Трансформация твиста с добавлением собственной скорости шарнира.<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;parent_twist: Твист точки привязки родителя<br>
&#9;&#9;&#9;<br>
&#9;&#9;Returns:<br>
&#9;&#9;&#9;Твист точки привязки ребенка<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;# 1. Трансформируем твист родителя в систему шарнира<br>
&#9;&#9;parent_twist_in_joint = parent_twist.transform_as_twist_by(self.joint_pose_in_parent)<br>
<br>
&#9;&#9;# 2. Добавляем собственную угловую скорость шарнира<br>
&#9;&#9;joint_twist = parent_twist_in_joint + self.joint_twist_in_joint()<br>
&#9;&#9;<br>
&#9;&#9;# 3. Трансформируем в точку привязки ребенка<br>
&#9;&#9;child_twist = joint_twist.transform_as_twist_by(self.child_pose_in_joint)<br>
&#9;&#9;<br>
&#9;&#9;return child_twist<br>
&#9;<br>
&#9;def integrate(self, dt: float):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Интегрировать угол из угловой скорости.<br>
&#9;&#9;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;dt: Шаг по времени [с]<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self.angle += self.omega.value * dt<br>
&#9;<br>
&#9;def __repr__(self):<br>
&#9;&#9;return f&quot;DollRotatorJoint2D({self.name}, angle={self.angle:.3f}, omega={self.omega.value:.3f})&quot;<br>
<!-- END SCAT CODE -->
</body>
</html>
