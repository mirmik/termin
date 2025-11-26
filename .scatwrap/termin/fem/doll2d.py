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
    M(q)·q̈ + C(q,q̇)·q̇ + g(q) = τ<br>
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
    &quot;&quot;&quot;<br>
    Редуцированная многотельная система 2D.<br>
    <br>
    Представляет собой дерево звеньев, соединенных шарнирами.<br>
    Формирует матрицу масс M(q) и вектор обобщенных сил для решателя.<br>
    <br>
    Атрибуты:<br>
        base: Базовое звено (корень дерева)<br>
        links: Список всех звеньев<br>
        joints: Список всех шарниров<br>
        variables: Список переменных (скорости шарниров)<br>
    &quot;&quot;&quot;<br>
    <br>
    def __init__(self, base_link=None, assembler=None):<br>
        &quot;&quot;&quot;<br>
        Args:<br>
            base_link: Корневое звено (None = земля)<br>
            assembler: MatrixAssembler для автоматической регистрации<br>
        &quot;&quot;&quot;<br>
        self.base = base_link<br>
        self.links: List[DollLink2D] = []<br>
        self.joints: List[DollJoint2D] = []<br>
        self.gravity = np.array([0.0, -9.81])  # [м/с²]<br>
        <br>
        # Соберем переменные из шарниров<br>
        variables = []<br>
        if base_link:<br>
            self._collect_joints(base_link)<br>
            variables = [var for joint in self.joints for var in joint.get_variables()]<br>
<br>
        print(&quot;HERE!!!!&quot;)<br>
        print(variables)<br>
<br>
        super().__init__(variables, assembler=assembler)<br>
    <br>
    def _collect_joints(self, link: 'DollLink2D'):<br>
        &quot;&quot;&quot;Рекурсивно собрать все звенья и шарниры из дерева.&quot;&quot;&quot;<br>
        if link not in self.links:<br>
            self.links.append(link)<br>
<br>
        if link.joint and link.joint not in self.joints:<br>
            self.joints.append(link.joint)<br>
<br>
        for child in link.children:<br>
            self._collect_joints(child)<br>
    <br>
    def add_link(self, link: 'DollLink2D'):<br>
        &quot;&quot;&quot;Добавить звено в систему.&quot;&quot;&quot;<br>
        if link not in self.links:<br>
            self.links.append(link)<br>
    <br>
    def update_kinematics(self):<br>
        &quot;&quot;&quot;<br>
        Обновить прямую кинематику всех звеньев.<br>
        Вычисляет положения и скорости на основе текущих значений переменных.<br>
        &quot;&quot;&quot;<br>
        if self.base:<br>
            base_pose = Pose2.identity()<br>
            base_twist = Screw2(ang=np.array([0.0]), lin=np.zeros(2))<br>
            self._update_link_kinematics(self.base, base_pose, base_twist)<br>
    <br>
    def _update_link_kinematics(self, link: 'DollLink2D',<br>
                                pose: Pose2,<br>
                                twist: Screw2):<br>
        &quot;&quot;&quot;<br>
        Рекурсивно обновить кинематику звена и его потомков.<br>
        <br>
        Args:<br>
            link: Текущее звено<br>
            pose: Поза точки привязки<br>
            twist: Твист точки привязки (винт скоростей)<br>
        &quot;&quot;&quot;<br>
        # Обновляем текущее звено<br>
        link.pose = pose<br>
        link.twist = twist<br>
        <br>
        # Обновляем детей через их шарниры<br>
        for child in link.children:<br>
            if child.joint:<br>
                child_pose = child.joint.pose_after_joint(link.pose)<br>
                child_twist = child.joint.twist_after_joint(link.twist)<br>
                self._update_link_kinematics(child, child_pose, child_twist)<br>
    <br>
    def contribute_to_mass(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
        &quot;&quot;&quot;<br>
        Добавить матрицу масс M(q) в глобальную матрицу.<br>
        <br>
        Для редуцированной системы: M(q) связывает ускорения с силами.<br>
        M строится через якобианы: M = Σ (J_i^T · M_body_i · J_i)<br>
        <br>
        где J_i - якобиан i-го тела относительно обобщенных координат.<br>
        &quot;&quot;&quot;<br>
        # Собираем вклады от всех звеньев<br>
        if self.base:<br>
            self.base.contribute_subtree_inertia(A, index_map)<br>
    <br>
    def contribute_to_b(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
        &quot;&quot;&quot;<br>
        Добавить обобщенные силы в правую часть.<br>
        <br>
        Включает:<br>
        - Гравитационные силы: Q_g = -∂V/∂q<br>
        - Кориолисовы силы: Q_c = -C(q,q̇)·q̇<br>
        - Приложенные моменты<br>
        &quot;&quot;&quot;        <br>
        # Рекурсивно вычисляем силы, спускаясь по дереву<br>
        if self.base:<br>
            self.base.contribute_subtree_forces(self.gravity, b, index_map)<br>
    <br>
    def get_kinetic_energy(self) -&gt; float:<br>
        &quot;&quot;&quot;Вычислить полную кинетическую энергию системы.&quot;&quot;&quot;<br>
        energy = 0.0<br>
        for link in self.links:<br>
            if link.inertia:<br>
                v = link.twist.vector()<br>
                omega = link.twist.moment()<br>
                energy += link.inertia.get_kinetic_energy(v, omega)<br>
        return energy<br>
<br>
<br>
<br>
class DollJoint2D:<br>
    &quot;&quot;&quot;<br>
    Базовый класс для шарнира в Doll2D.<br>
    <br>
    Шарнир связывает родительское и дочернее звено,<br>
    определяет обобщенную координату и кинематику.<br>
    &quot;&quot;&quot;<br>
    <br>
    def __init__(self, name: str = &quot;joint&quot;):<br>
        self.name = name<br>
        self.parent_link: Optional['DollLink2D'] = None<br>
        self.child_link: Optional['DollLink2D'] = None<br>
    <br>
    def get_variables(self) -&gt; List[Variable]:<br>
        &quot;&quot;&quot;<br>
        Вернуть список переменных, связанных с этим шарниром.<br>
        <br>
        Returns:<br>
            Список переменных (может быть пустым для фиксированных шарниров)<br>
        &quot;&quot;&quot;<br>
        return []<br>
    <br>
    def project_wrench(self, wrench: Screw2, index_map: Dict[Variable, List[int]], b: np.ndarray):<br>
        &quot;&quot;&quot;<br>
        Спроецировать вренч на ось шарнира и добавить в вектор обобщенных сил.<br>
        <br>
        Args:<br>
            wrench: Вренч сил (Screw2) в точке привязки дочернего звена<br>
            index_map: Отображение переменных на индексы<br>
            b: Вектор обобщенных сил<br>
        &quot;&quot;&quot;<br>
        pass  # Фиксированный шарнир не имеет степеней свободы<br>
    <br>
    def inverse_transform_wrench(self, wrench: Screw2) -&gt; Screw2:<br>
        &quot;&quot;&quot;<br>
        Обратная трансформация вренча через шарнир (от child к parent).<br>
        <br>
        Args:<br>
            wrench: Вренч в точке привязки дочернего звена<br>
            <br>
        Returns:<br>
            Вренч в точке привязки родительского звена<br>
        &quot;&quot;&quot;<br>
        raise NotImplementedError(&quot;Метод должен быть реализован в подклассе&quot;)<br>
    <br>
    def pose_after_joint(self, parent_pose: Pose2) -&gt; Pose2:<br>
        &quot;&quot;&quot;<br>
        Вычислить позу дочернего звена на основе позы родителя.<br>
        <br>
        Args:<br>
            parent_pose: Поза точки привязки родителя<br>
            <br>
        Returns:<br>
            Поза точки привязки ребенка<br>
        &quot;&quot;&quot;<br>
        raise NotImplementedError(&quot;Метод должен быть реализован в подклассе&quot;)<br>
    <br>
    def twist_after_joint(self, parent_twist: Screw2) -&gt; Screw2:<br>
        &quot;&quot;&quot;<br>
        Вычислить твист дочернего звена на основе твиста родителя.<br>
        <br>
        Args:<br>
            parent_twist: Твист точки привязки родителя<br>
            <br>
        Returns:<br>
            Твист точки привязки ребенка<br>
        &quot;&quot;&quot;<br>
        raise NotImplementedError(&quot;Метод должен быть реализован в подклассе&quot;)<br>
    <br>
<br>
class DollLink2D:<br>
    &quot;&quot;&quot;<br>
    Звено в Doll2D - твердое тело в цепи.<br>
    <br>
    Атрибуты:<br>
        name: Имя звена<br>
        parent: Родительское звено<br>
        children: Дочерние звенья<br>
        joint: Шарнир, связывающий это звено с родителем<br>
        inertia: Инерционные характеристики (масса, момент инерции, ЦМ)<br>
        <br>
        # Состояние (вычисляется кинематикой):<br>
        pose: Поза точки привязки (Pose2)<br>
        twist: Твист точки привязки (Screw2 - винт скоростей)<br>
    &quot;&quot;&quot;<br>
    <br>
    def __init__(self, name: str = &quot;link&quot;, inertia: 'SpatialInertia2D' = SpatialInertia2D()):<br>
        self.name = name<br>
        self.children: List['DollLink2D'] = []<br>
        self.parent: Optional['DollLink2D'] = None<br>
        self.joint: Optional[DollJoint2D] = None<br>
        self.inertia = inertia<br>
        <br>
        # Кинематическое состояние<br>
        self.pose = Pose2.identity()<br>
        self.twist = Screw2(ang=np.array([0.0]), lin=np.zeros(2))<br>
    <br>
    def add_child(self, child: 'DollLink2D', joint: DollJoint2D):<br>
        &quot;&quot;&quot;<br>
        Добавить дочернее звено через шарнир.<br>
        <br>
        Args:<br>
            child: Дочернее звено<br>
            joint: Шарнир, соединяющий parent и child<br>
        &quot;&quot;&quot;<br>
        child.parent = self<br>
        child.joint = joint<br>
        joint.parent_link = self<br>
        joint.child_link = child<br>
        self.children.append(child)<br>
    <br>
    def gravity_wrench(self, gravity: np.ndarray) -&gt; Screw2:<br>
        &quot;&quot;&quot;<br>
        Вычислить вренч гравитационной силы, действующей на звено.<br>
        <br>
        Args:<br>
            gravity: Вектор гравитации [м/с²]<br>
            <br>
        Returns:<br>
            Вренч гравитации (момент + сила) в точке привязки звена<br>
        &quot;&quot;&quot;<br>
        if not self.inertia:<br>
            return Screw2(ang=np.array([0.0]), lin=np.zeros(2))<br>
        <br>
        return self.inertia.gravity_wrench(self.pose, gravity)<br>
    <br>
    def local_wrench(self, gravity: np.ndarray) -&gt; Screw2:<br>
        &quot;&quot;&quot;<br>
        Вычислить суммарный вренч всех сил, действующих на звено.<br>
        Включает:<br>
        - гравитацию<br>
        - кориолисовы и центробежные силы<br>
        - (в будущем) внешние силы<br>
        &quot;&quot;&quot;<br>
        wrench = self.gravity_wrench(gravity)<br>
<br>
        coriolis_wrench = self.coriolis_wrench()<br>
        if coriolis_wrench is not None:<br>
            wrench += coriolis_wrench<br>
<br>
        # TODO: добавить внешние силы<br>
        return wrench<br>
<br>
<br>
    def coriolis_wrench(self) -&gt; Optional[Screw2]:<br>
        &quot;&quot;&quot;<br>
        Вычислить вренч кориолисовых и центробежных сил для звена.<br>
<br>
        Returns:<br>
            Screw2: (момент, сила) в мировой СК, либо None, если звено неподвижно<br>
        &quot;&quot;&quot;<br>
        if not self.inertia or self.twist is None:<br>
            return None<br>
<br>
        ω = float(self.twist.ang.flatten()[0])<br>
        v = self.twist.lin<br>
<br>
        # если скорости нулевые — можно не считать<br>
        if abs(ω) &lt; 1e-12 and np.linalg.norm(v) &lt; 1e-12:<br>
            return None<br>
<br>
        # Центр масс в мировой СК<br>
        r_c = self.pose.rotation_matrix() @ self.inertia.com  # com — в локальной СК<br>
<br>
        # Скорость центра масс<br>
        v_c = v + ω * np.array([-r_c[1], r_c[0]])<br>
<br>
        # Кориолисовая сила<br>
        F_c = self.inertia.mass * ω * np.array([-v_c[1], v_c[0]])<br>
<br>
        # Момент относительно точки привязки<br>
        M_c = r_c[0] * F_c[1] - r_c[1] * F_c[0]<br>
<br>
        return Screw2(ang=np.array([M_c]), lin=F_c)<br>
    <br>
    def contribute_subtree_forces(self, gravity: np.ndarray, <br>
                                  b: np.ndarray, <br>
                                  index_map: Dict[Variable, List[int]]) -&gt; Screw2:<br>
        &quot;&quot;&quot;<br>
        Рекурсивно вычислить суммарный вренч сил для поддерева.<br>
        <br>
        Алгоритм:<br>
        1. Вычисляем вренч сил на текущем звене (гравитация, внешние силы)<br>
        2. Рекурсивно получаем вренчи от детей<br>
        3. Трансформируем вренчи детей в точку привязки текущего звена<br>
        4. Суммируем все вренчи<br>
        5. Проецируем на шарнир текущего звена (если есть)<br>
        <br>
        Args:<br>
            gravity: Вектор гравитации [м/с²]<br>
            b: Вектор обобщенных сил<br>
            index_map: Отображение переменных на индексы<br>
            <br>
        Returns:<br>
            Суммарный вренч сил, действующих на поддерево (в точке привязки)<br>
        &quot;&quot;&quot;<br>
        # 1. Вренч сил на текущем звене<br>
        wrench_link = self.local_wrench(gravity)<br>
        <br>
        # 2. Собираем вренчи от детей<br>
        total_wrench = wrench_link<br>
        for child in self.children:<br>
            # Рекурсивно получаем вренч поддерева ребенка<br>
            child_wrench = child.contribute_subtree_forces(gravity, b, index_map)<br>
            <br>
            # Трансформируем вренч ребенка в точку привязки текущего звена<br>
            # Используем обратную трансформацию через шарнир ребенка<br>
            child_wrench = child.joint.inverse_transform_wrench(child_wrench)<br>
            <br>
            total_wrench = total_wrench + child_wrench<br>
        <br>
        # 3. Проецируем на шарнир текущего звена<br>
        # Обобщенная сила = проекция вренча на оси шарнира<br>
        # Для фиксированного шарнира (без переменных) project_wrench ничего не делает<br>
        if self.joint:<br>
            self.joint.project_wrench(total_wrench, index_map, b)<br>
        <br>
        return total_wrench<br>
    <br>
    def contribute_subtree_inertia(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):<br>
        &quot;&quot;&quot;<br>
        Рекурсивно собрать spatial inertia от поддерева, проецировать на переменные.<br>
        Алгоритм:<br>
        1. Собрать spatial inertia от детей, трансформировать к текущему звену<br>
        2. Суммировать с собственной инерцией<br>
        3. Проецировать итоговую spatial inertia на переменные звена (через якобиан)<br>
        4. Рекурсивно пройти по дереву<br>
        &quot;&quot;&quot;<br>
        # 1. Собираем spatial inertia от детей<br>
        subtree_inertia = SpatialInertia2D(0.0, 0.0, np.zeros(2))<br>
        for child in self.children:<br>
            child_inertia = child.contribute_subtree_inertia(A, index_map)<br>
            child_inertia = child_inertia.transform_by(child.joint.child_pose_in_joint)<br>
            subtree_inertia = subtree_inertia + child_inertia<br>
<br>
        # 2. Суммируем с собственной инерцией<br>
        total_inertia = subtree_inertia + self.inertia<br>
<br>
        # 3. Проецируем через шарнир (если есть)<br>
        if self.joint:<br>
            self.joint.project_inertia(total_inertia, A, index_map)<br>
<br>
        # 4. Возвращаем spatial inertia поддерева для родителя<br>
        return total_inertia<br>
    <br>
    def __repr__(self):<br>
        return f&quot;DollLink2D({self.name})&quot;<br>
        <br>
<br>
class DollRotatorJoint2D(DollJoint2D):<br>
    &quot;&quot;&quot;<br>
    Вращательный шарнир для Doll2D.<br>
    <br>
    Связывает родительское и дочернее звено через угловую координату.<br>
    <br>
    Атрибуты:<br>
        omega: Переменная угловой скорости [рад/с]<br>
        angle: Текущий угол [рад] (интегрируется из omega)<br>
        joint_pose_in_parent: Поза шарнира в системе координат родителя<br>
        child_pose_in_joint: Поза точки привязки ребенка в системе шарнира<br>
    &quot;&quot;&quot;<br>
    <br>
    def __init__(self, <br>
                 name: str = &quot;rotator_joint&quot;,<br>
                 joint_pose_in_parent: Pose2 = None,<br>
                 child_pose_in_joint: Pose2 = None,<br>
                 assembler=None):<br>
        &quot;&quot;&quot;<br>
        Args:<br>
            name: Имя шарнира<br>
            joint_pose_in_parent: Поза шарнира в СК родителя<br>
            child_pose_in_joint: Поза точки привязки ребенка в СК шарнира<br>
            assembler: MatrixAssembler для регистрации переменной<br>
        &quot;&quot;&quot;<br>
        super().__init__(name)<br>
        self.omega = Variable(name=f&quot;{name}_omega&quot;, size=1)<br>
        self.angle = 0.0  # текущий угол (интегрируется)<br>
        <br>
        self.joint_pose_in_parent = joint_pose_in_parent if joint_pose_in_parent is not None else Pose2.identity()<br>
        self.child_pose_in_joint = child_pose_in_joint if child_pose_in_joint is not None else Pose2.identity()<br>
        <br>
        if assembler:<br>
            assembler.add_variable(self.omega)<br>
    <br>
    def get_variables(self) -&gt; List[Variable]:<br>
        &quot;&quot;&quot;Вернуть список переменных шарнира.&quot;&quot;&quot;<br>
        return [self.omega]<br>
    <br>
    def project_wrench(self, wrench: Screw2, index_map: Dict[Variable, List[int]], b: np.ndarray):<br>
        &quot;&quot;&quot;<br>
        Спроецировать вренч на ось вращательного шарнира.<br>
        <br>
        Для вращательного шарнира обобщенная сила = момент (угловая компонента вренча).<br>
        <br>
        Args:<br>
            wrench: Вренч сил в точке привязки дочернего звена<br>
            index_map: Отображение переменных на индексы<br>
            b: Вектор обобщенных сил<br>
        &quot;&quot;&quot;<br>
        idx = index_map[self.omega][0]<br>
        # Обобщенная сила для вращательного шарнира = момент<br>
        b[idx] += wrench.moment()<br>
<br>
    def project_inertia(self, inertia: 'SpatialInertia2D',<br>
                    A: np.ndarray,<br>
                    index_map: Dict[Variable, List[int]]):<br>
        &quot;&quot;&quot;<br>
        Проецировать spatial inertia на матрицу масс через вращательный DOF.<br>
        Эквивалентно вычислению M_ii = Sᵀ I S, где S — ось вращения.<br>
        &quot;&quot;&quot;<br>
        vars = self.get_variables()<br>
        if not vars:<br>
            return<br>
        <br>
        idx = index_map[vars[0]][0]<br>
<br>
        # Вращения в локальной СК шарнира в плоскости xy<br>
        S = np.array([1.0, 0.0, 0.0])  # [ω, vx, vy]<br>
<br>
        # Преобразуем ось в систему родителя<br>
        R = self.joint_pose_in_parent.rotation_matrix()<br>
        S_world = np.array([S[0], *(R @ S[1:])])  # [ω, vx, vy]<br>
<br>
        # Spatial inertia в матричном виде<br>
        I = inertia.to_matrix()  # 3x3<br>
<br>
        # M_ii = Sᵀ I S<br>
        Mjj = float(S_world @ (I @ S_world))<br>
<br>
        # Записываем в глобальную матрицу масс<br>
        A[idx, idx] += Mjj<br>
    <br>
    def inverse_transform_wrench(self, wrench: Screw2) -&gt; Screw2:<br>
        &quot;&quot;&quot;<br>
        Обратная трансформация вренча через вращательный шарнир (от child к parent).<br>
        <br>
        Вренч трансформируется обратно по цепочке:<br>
        child -&gt; child_pose_in_joint^-1 -&gt; rotation^-1 -&gt; joint_pose_in_parent^-1 -&gt; parent<br>
        <br>
        Args:<br>
            wrench: Вренч в точке привязки дочернего звена<br>
            <br>
        Returns:<br>
            Вренч в точке привязки родительского звена<br>
        &quot;&quot;&quot;<br>
        # Обратная трансформация по цепочке<br>
        result = wrench.inverse_transform_as_wrench_by(self.child_pose_in_joint)<br>
        joint_rotation = Pose2.rotation(self.angle)<br>
        result = result.inverse_transform_as_wrench_by(joint_rotation)<br>
        result = result.inverse_transform_as_wrench_by(self.joint_pose_in_parent)<br>
        return result<br>
    <br>
    def pose_after_joint(self, parent_pose: Pose2) -&gt; Pose2:<br>
        &quot;&quot;&quot;<br>
        Вычислить позу дочернего звена на основе позы родителя.<br>
        <br>
        Композиция поз:<br>
        child_pose = parent_pose * joint_pose_in_parent * rotation(angle) * child_pose_in_joint<br>
        <br>
        Args:<br>
            parent_pose: Поза точки привязки родителя<br>
            <br>
        Returns:<br>
            Поза точки привязки ребенка<br>
        &quot;&quot;&quot;<br>
        joint_rotation = Pose2.rotation(self.angle)<br>
        joint_pose = parent_pose * self.joint_pose_in_parent * joint_rotation<br>
        child_pose = joint_pose * self.child_pose_in_joint<br>
        return child_pose<br>
    <br>
    def joint_twist_in_joint(self) -&gt; Screw2:<br>
        &quot;&quot;&quot;<br>
        Вычислить твист шарнира в его собственной системе координат.<br>
        <br>
        Возвращает твист, соответствующий собственной угловой скорости шарнира.<br>
        <br>
        Returns:<br>
            Твист шарнира в его системе координат<br>
        &quot;&quot;&quot;<br>
        return Screw2(<br>
            ang=self.omega.value,<br>
            lin=np.zeros(2)<br>
        )<br>
<br>
    def twist_after_joint(self, parent_twist: Screw2) -&gt; Screw2:<br>
        &quot;&quot;&quot;<br>
        Вычислить твист дочернего звена на основе твиста родителя.<br>
        <br>
        Трансформация твиста с добавлением собственной скорости шарнира.<br>
        <br>
        Args:<br>
            parent_twist: Твист точки привязки родителя<br>
            <br>
        Returns:<br>
            Твист точки привязки ребенка<br>
        &quot;&quot;&quot;<br>
        # 1. Трансформируем твист родителя в систему шарнира<br>
        parent_twist_in_joint = parent_twist.transform_as_twist_by(self.joint_pose_in_parent)<br>
<br>
        # 2. Добавляем собственную угловую скорость шарнира<br>
        joint_twist = parent_twist_in_joint + self.joint_twist_in_joint()<br>
        <br>
        # 3. Трансформируем в точку привязки ребенка<br>
        child_twist = joint_twist.transform_as_twist_by(self.child_pose_in_joint)<br>
        <br>
        return child_twist<br>
    <br>
    def integrate(self, dt: float):<br>
        &quot;&quot;&quot;<br>
        Интегрировать угол из угловой скорости.<br>
        <br>
        Args:<br>
            dt: Шаг по времени [с]<br>
        &quot;&quot;&quot;<br>
        self.angle += self.omega.value * dt<br>
    <br>
    def __repr__(self):<br>
        return f&quot;DollRotatorJoint2D({self.name}, angle={self.angle:.3f}, omega={self.omega.value:.3f})&quot;<br>
<!-- END SCAT CODE -->
</body>
</html>
