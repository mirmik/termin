<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/doll2d.py</title>
</head>
<body>
<pre><code>

#!/usr/bin/env python3
&quot;&quot;&quot;
Редуцированная многотельная динамика 2D на основе дерева звеньев.

Doll2D - система из звеньев (links), соединенных шарнирами (joints).
Каждый шарнир имеет обобщенную координату (угол для RotatorJoint).

Динамика формируется через уравнения Лагранжа:
    M(q)·q̈ + C(q,q̇)·q̇ + g(q) = τ

где:
- M(q) - матрица масс (зависит от конфигурации)
- C(q,q̇) - кориолисовы и центробежные силы
- g(q) - гравитационные силы
- τ - приложенные моменты/силы
&quot;&quot;&quot;

import numpy as np
from typing import List, Dict, Optional
from termin.fem.assembler import MatrixAssembler, Variable, Contribution, Constraint
from termin.fem.inertia2d import SpatialInertia2D
from termin.geombase.pose2 import Pose2
from termin.geombase.screw import Screw2, cross2d_scalar


class Doll2D(Contribution):
    &quot;&quot;&quot;
    Редуцированная многотельная система 2D.
    
    Представляет собой дерево звеньев, соединенных шарнирами.
    Формирует матрицу масс M(q) и вектор обобщенных сил для решателя.
    
    Атрибуты:
        base: Базовое звено (корень дерева)
        links: Список всех звеньев
        joints: Список всех шарниров
        variables: Список переменных (скорости шарниров)
    &quot;&quot;&quot;
    
    def __init__(self, base_link=None, assembler=None):
        &quot;&quot;&quot;
        Args:
            base_link: Корневое звено (None = земля)
            assembler: MatrixAssembler для автоматической регистрации
        &quot;&quot;&quot;
        self.base = base_link
        self.links: List[DollLink2D] = []
        self.joints: List[DollJoint2D] = []
        self.gravity = np.array([0.0, -9.81])  # [м/с²]
        
        # Соберем переменные из шарниров
        variables = []
        if base_link:
            self._collect_joints(base_link)
            variables = [var for joint in self.joints for var in joint.get_variables()]

        print(&quot;HERE!!!!&quot;)
        print(variables)

        super().__init__(variables, assembler=assembler)
    
    def _collect_joints(self, link: 'DollLink2D'):
        &quot;&quot;&quot;Рекурсивно собрать все звенья и шарниры из дерева.&quot;&quot;&quot;
        if link not in self.links:
            self.links.append(link)

        if link.joint and link.joint not in self.joints:
            self.joints.append(link.joint)

        for child in link.children:
            self._collect_joints(child)
    
    def add_link(self, link: 'DollLink2D'):
        &quot;&quot;&quot;Добавить звено в систему.&quot;&quot;&quot;
        if link not in self.links:
            self.links.append(link)
    
    def update_kinematics(self):
        &quot;&quot;&quot;
        Обновить прямую кинематику всех звеньев.
        Вычисляет положения и скорости на основе текущих значений переменных.
        &quot;&quot;&quot;
        if self.base:
            base_pose = Pose2.identity()
            base_twist = Screw2(ang=np.array([0.0]), lin=np.zeros(2))
            self._update_link_kinematics(self.base, base_pose, base_twist)
    
    def _update_link_kinematics(self, link: 'DollLink2D',
                                pose: Pose2,
                                twist: Screw2):
        &quot;&quot;&quot;
        Рекурсивно обновить кинематику звена и его потомков.
        
        Args:
            link: Текущее звено
            pose: Поза точки привязки
            twist: Твист точки привязки (винт скоростей)
        &quot;&quot;&quot;
        # Обновляем текущее звено
        link.pose = pose
        link.twist = twist
        
        # Обновляем детей через их шарниры
        for child in link.children:
            if child.joint:
                child_pose = child.joint.pose_after_joint(link.pose)
                child_twist = child.joint.twist_after_joint(link.twist)
                self._update_link_kinematics(child, child_pose, child_twist)
    
    def contribute_to_mass(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):
        &quot;&quot;&quot;
        Добавить матрицу масс M(q) в глобальную матрицу.
        
        Для редуцированной системы: M(q) связывает ускорения с силами.
        M строится через якобианы: M = Σ (J_i^T · M_body_i · J_i)
        
        где J_i - якобиан i-го тела относительно обобщенных координат.
        &quot;&quot;&quot;
        # Собираем вклады от всех звеньев
        if self.base:
            self.base.contribute_subtree_inertia(A, index_map)
    
    def contribute_to_b(self, b: np.ndarray, index_map: Dict[Variable, List[int]]):
        &quot;&quot;&quot;
        Добавить обобщенные силы в правую часть.
        
        Включает:
        - Гравитационные силы: Q_g = -∂V/∂q
        - Кориолисовы силы: Q_c = -C(q,q̇)·q̇
        - Приложенные моменты
        &quot;&quot;&quot;        
        # Рекурсивно вычисляем силы, спускаясь по дереву
        if self.base:
            self.base.contribute_subtree_forces(self.gravity, b, index_map)
    
    def get_kinetic_energy(self) -&gt; float:
        &quot;&quot;&quot;Вычислить полную кинетическую энергию системы.&quot;&quot;&quot;
        energy = 0.0
        for link in self.links:
            if link.inertia:
                v = link.twist.vector()
                omega = link.twist.moment()
                energy += link.inertia.get_kinetic_energy(v, omega)
        return energy



class DollJoint2D:
    &quot;&quot;&quot;
    Базовый класс для шарнира в Doll2D.
    
    Шарнир связывает родительское и дочернее звено,
    определяет обобщенную координату и кинематику.
    &quot;&quot;&quot;
    
    def __init__(self, name: str = &quot;joint&quot;):
        self.name = name
        self.parent_link: Optional['DollLink2D'] = None
        self.child_link: Optional['DollLink2D'] = None
    
    def get_variables(self) -&gt; List[Variable]:
        &quot;&quot;&quot;
        Вернуть список переменных, связанных с этим шарниром.
        
        Returns:
            Список переменных (может быть пустым для фиксированных шарниров)
        &quot;&quot;&quot;
        return []
    
    def project_wrench(self, wrench: Screw2, index_map: Dict[Variable, List[int]], b: np.ndarray):
        &quot;&quot;&quot;
        Спроецировать вренч на ось шарнира и добавить в вектор обобщенных сил.
        
        Args:
            wrench: Вренч сил (Screw2) в точке привязки дочернего звена
            index_map: Отображение переменных на индексы
            b: Вектор обобщенных сил
        &quot;&quot;&quot;
        pass  # Фиксированный шарнир не имеет степеней свободы
    
    def inverse_transform_wrench(self, wrench: Screw2) -&gt; Screw2:
        &quot;&quot;&quot;
        Обратная трансформация вренча через шарнир (от child к parent).
        
        Args:
            wrench: Вренч в точке привязки дочернего звена
            
        Returns:
            Вренч в точке привязки родительского звена
        &quot;&quot;&quot;
        raise NotImplementedError(&quot;Метод должен быть реализован в подклассе&quot;)
    
    def pose_after_joint(self, parent_pose: Pose2) -&gt; Pose2:
        &quot;&quot;&quot;
        Вычислить позу дочернего звена на основе позы родителя.
        
        Args:
            parent_pose: Поза точки привязки родителя
            
        Returns:
            Поза точки привязки ребенка
        &quot;&quot;&quot;
        raise NotImplementedError(&quot;Метод должен быть реализован в подклассе&quot;)
    
    def twist_after_joint(self, parent_twist: Screw2) -&gt; Screw2:
        &quot;&quot;&quot;
        Вычислить твист дочернего звена на основе твиста родителя.
        
        Args:
            parent_twist: Твист точки привязки родителя
            
        Returns:
            Твист точки привязки ребенка
        &quot;&quot;&quot;
        raise NotImplementedError(&quot;Метод должен быть реализован в подклассе&quot;)
    

class DollLink2D:
    &quot;&quot;&quot;
    Звено в Doll2D - твердое тело в цепи.
    
    Атрибуты:
        name: Имя звена
        parent: Родительское звено
        children: Дочерние звенья
        joint: Шарнир, связывающий это звено с родителем
        inertia: Инерционные характеристики (масса, момент инерции, ЦМ)
        
        # Состояние (вычисляется кинематикой):
        pose: Поза точки привязки (Pose2)
        twist: Твист точки привязки (Screw2 - винт скоростей)
    &quot;&quot;&quot;
    
    def __init__(self, name: str = &quot;link&quot;, inertia: 'SpatialInertia2D' = SpatialInertia2D()):
        self.name = name
        self.children: List['DollLink2D'] = []
        self.parent: Optional['DollLink2D'] = None
        self.joint: Optional[DollJoint2D] = None
        self.inertia = inertia
        
        # Кинематическое состояние
        self.pose = Pose2.identity()
        self.twist = Screw2(ang=np.array([0.0]), lin=np.zeros(2))
    
    def add_child(self, child: 'DollLink2D', joint: DollJoint2D):
        &quot;&quot;&quot;
        Добавить дочернее звено через шарнир.
        
        Args:
            child: Дочернее звено
            joint: Шарнир, соединяющий parent и child
        &quot;&quot;&quot;
        child.parent = self
        child.joint = joint
        joint.parent_link = self
        joint.child_link = child
        self.children.append(child)
    
    def gravity_wrench(self, gravity: np.ndarray) -&gt; Screw2:
        &quot;&quot;&quot;
        Вычислить вренч гравитационной силы, действующей на звено.
        
        Args:
            gravity: Вектор гравитации [м/с²]
            
        Returns:
            Вренч гравитации (момент + сила) в точке привязки звена
        &quot;&quot;&quot;
        if not self.inertia:
            return Screw2(ang=np.array([0.0]), lin=np.zeros(2))
        
        return self.inertia.gravity_wrench(self.pose, gravity)
    
    def local_wrench(self, gravity: np.ndarray) -&gt; Screw2:
        &quot;&quot;&quot;
        Вычислить суммарный вренч всех сил, действующих на звено.
        Включает:
        - гравитацию
        - кориолисовы и центробежные силы
        - (в будущем) внешние силы
        &quot;&quot;&quot;
        wrench = self.gravity_wrench(gravity)

        coriolis_wrench = self.coriolis_wrench()
        if coriolis_wrench is not None:
            wrench += coriolis_wrench

        # TODO: добавить внешние силы
        return wrench


    def coriolis_wrench(self) -&gt; Optional[Screw2]:
        &quot;&quot;&quot;
        Вычислить вренч кориолисовых и центробежных сил для звена.

        Returns:
            Screw2: (момент, сила) в мировой СК, либо None, если звено неподвижно
        &quot;&quot;&quot;
        if not self.inertia or self.twist is None:
            return None

        ω = float(self.twist.ang.flatten()[0])
        v = self.twist.lin

        # если скорости нулевые — можно не считать
        if abs(ω) &lt; 1e-12 and np.linalg.norm(v) &lt; 1e-12:
            return None

        # Центр масс в мировой СК
        r_c = self.pose.rotation_matrix() @ self.inertia.com  # com — в локальной СК

        # Скорость центра масс
        v_c = v + ω * np.array([-r_c[1], r_c[0]])

        # Кориолисовая сила
        F_c = self.inertia.mass * ω * np.array([-v_c[1], v_c[0]])

        # Момент относительно точки привязки
        M_c = r_c[0] * F_c[1] - r_c[1] * F_c[0]

        return Screw2(ang=np.array([M_c]), lin=F_c)
    
    def contribute_subtree_forces(self, gravity: np.ndarray, 
                                  b: np.ndarray, 
                                  index_map: Dict[Variable, List[int]]) -&gt; Screw2:
        &quot;&quot;&quot;
        Рекурсивно вычислить суммарный вренч сил для поддерева.
        
        Алгоритм:
        1. Вычисляем вренч сил на текущем звене (гравитация, внешние силы)
        2. Рекурсивно получаем вренчи от детей
        3. Трансформируем вренчи детей в точку привязки текущего звена
        4. Суммируем все вренчи
        5. Проецируем на шарнир текущего звена (если есть)
        
        Args:
            gravity: Вектор гравитации [м/с²]
            b: Вектор обобщенных сил
            index_map: Отображение переменных на индексы
            
        Returns:
            Суммарный вренч сил, действующих на поддерево (в точке привязки)
        &quot;&quot;&quot;
        # 1. Вренч сил на текущем звене
        wrench_link = self.local_wrench(gravity)
        
        # 2. Собираем вренчи от детей
        total_wrench = wrench_link
        for child in self.children:
            # Рекурсивно получаем вренч поддерева ребенка
            child_wrench = child.contribute_subtree_forces(gravity, b, index_map)
            
            # Трансформируем вренч ребенка в точку привязки текущего звена
            # Используем обратную трансформацию через шарнир ребенка
            child_wrench = child.joint.inverse_transform_wrench(child_wrench)
            
            total_wrench = total_wrench + child_wrench
        
        # 3. Проецируем на шарнир текущего звена
        # Обобщенная сила = проекция вренча на оси шарнира
        # Для фиксированного шарнира (без переменных) project_wrench ничего не делает
        if self.joint:
            self.joint.project_wrench(total_wrench, index_map, b)
        
        return total_wrench
    
    def contribute_subtree_inertia(self, A: np.ndarray, index_map: Dict[Variable, List[int]]):
        &quot;&quot;&quot;
        Рекурсивно собрать spatial inertia от поддерева, проецировать на переменные.
        Алгоритм:
        1. Собрать spatial inertia от детей, трансформировать к текущему звену
        2. Суммировать с собственной инерцией
        3. Проецировать итоговую spatial inertia на переменные звена (через якобиан)
        4. Рекурсивно пройти по дереву
        &quot;&quot;&quot;
        # 1. Собираем spatial inertia от детей
        subtree_inertia = SpatialInertia2D(0.0, 0.0, np.zeros(2))
        for child in self.children:
            child_inertia = child.contribute_subtree_inertia(A, index_map)
            child_inertia = child_inertia.transform_by(child.joint.child_pose_in_joint)
            subtree_inertia = subtree_inertia + child_inertia

        # 2. Суммируем с собственной инерцией
        total_inertia = subtree_inertia + self.inertia

        # 3. Проецируем через шарнир (если есть)
        if self.joint:
            self.joint.project_inertia(total_inertia, A, index_map)

        # 4. Возвращаем spatial inertia поддерева для родителя
        return total_inertia
    
    def __repr__(self):
        return f&quot;DollLink2D({self.name})&quot;
        

class DollRotatorJoint2D(DollJoint2D):
    &quot;&quot;&quot;
    Вращательный шарнир для Doll2D.
    
    Связывает родительское и дочернее звено через угловую координату.
    
    Атрибуты:
        omega: Переменная угловой скорости [рад/с]
        angle: Текущий угол [рад] (интегрируется из omega)
        joint_pose_in_parent: Поза шарнира в системе координат родителя
        child_pose_in_joint: Поза точки привязки ребенка в системе шарнира
    &quot;&quot;&quot;
    
    def __init__(self, 
                 name: str = &quot;rotator_joint&quot;,
                 joint_pose_in_parent: Pose2 = None,
                 child_pose_in_joint: Pose2 = None,
                 assembler=None):
        &quot;&quot;&quot;
        Args:
            name: Имя шарнира
            joint_pose_in_parent: Поза шарнира в СК родителя
            child_pose_in_joint: Поза точки привязки ребенка в СК шарнира
            assembler: MatrixAssembler для регистрации переменной
        &quot;&quot;&quot;
        super().__init__(name)
        self.omega = Variable(name=f&quot;{name}_omega&quot;, size=1)
        self.angle = 0.0  # текущий угол (интегрируется)
        
        self.joint_pose_in_parent = joint_pose_in_parent if joint_pose_in_parent is not None else Pose2.identity()
        self.child_pose_in_joint = child_pose_in_joint if child_pose_in_joint is not None else Pose2.identity()
        
        if assembler:
            assembler.add_variable(self.omega)
    
    def get_variables(self) -&gt; List[Variable]:
        &quot;&quot;&quot;Вернуть список переменных шарнира.&quot;&quot;&quot;
        return [self.omega]
    
    def project_wrench(self, wrench: Screw2, index_map: Dict[Variable, List[int]], b: np.ndarray):
        &quot;&quot;&quot;
        Спроецировать вренч на ось вращательного шарнира.
        
        Для вращательного шарнира обобщенная сила = момент (угловая компонента вренча).
        
        Args:
            wrench: Вренч сил в точке привязки дочернего звена
            index_map: Отображение переменных на индексы
            b: Вектор обобщенных сил
        &quot;&quot;&quot;
        idx = index_map[self.omega][0]
        # Обобщенная сила для вращательного шарнира = момент
        b[idx] += wrench.moment()

    def project_inertia(self, inertia: 'SpatialInertia2D',
                    A: np.ndarray,
                    index_map: Dict[Variable, List[int]]):
        &quot;&quot;&quot;
        Проецировать spatial inertia на матрицу масс через вращательный DOF.
        Эквивалентно вычислению M_ii = Sᵀ I S, где S — ось вращения.
        &quot;&quot;&quot;
        vars = self.get_variables()
        if not vars:
            return
        
        idx = index_map[vars[0]][0]

        # Вращения в локальной СК шарнира в плоскости xy
        S = np.array([1.0, 0.0, 0.0])  # [ω, vx, vy]

        # Преобразуем ось в систему родителя
        R = self.joint_pose_in_parent.rotation_matrix()
        S_world = np.array([S[0], *(R @ S[1:])])  # [ω, vx, vy]

        # Spatial inertia в матричном виде
        I = inertia.to_matrix()  # 3x3

        # M_ii = Sᵀ I S
        Mjj = float(S_world @ (I @ S_world))

        # Записываем в глобальную матрицу масс
        A[idx, idx] += Mjj
    
    def inverse_transform_wrench(self, wrench: Screw2) -&gt; Screw2:
        &quot;&quot;&quot;
        Обратная трансформация вренча через вращательный шарнир (от child к parent).
        
        Вренч трансформируется обратно по цепочке:
        child -&gt; child_pose_in_joint^-1 -&gt; rotation^-1 -&gt; joint_pose_in_parent^-1 -&gt; parent
        
        Args:
            wrench: Вренч в точке привязки дочернего звена
            
        Returns:
            Вренч в точке привязки родительского звена
        &quot;&quot;&quot;
        # Обратная трансформация по цепочке
        result = wrench.inverse_transform_as_wrench_by(self.child_pose_in_joint)
        joint_rotation = Pose2.rotation(self.angle)
        result = result.inverse_transform_as_wrench_by(joint_rotation)
        result = result.inverse_transform_as_wrench_by(self.joint_pose_in_parent)
        return result
    
    def pose_after_joint(self, parent_pose: Pose2) -&gt; Pose2:
        &quot;&quot;&quot;
        Вычислить позу дочернего звена на основе позы родителя.
        
        Композиция поз:
        child_pose = parent_pose * joint_pose_in_parent * rotation(angle) * child_pose_in_joint
        
        Args:
            parent_pose: Поза точки привязки родителя
            
        Returns:
            Поза точки привязки ребенка
        &quot;&quot;&quot;
        joint_rotation = Pose2.rotation(self.angle)
        joint_pose = parent_pose * self.joint_pose_in_parent * joint_rotation
        child_pose = joint_pose * self.child_pose_in_joint
        return child_pose
    
    def joint_twist_in_joint(self) -&gt; Screw2:
        &quot;&quot;&quot;
        Вычислить твист шарнира в его собственной системе координат.
        
        Возвращает твист, соответствующий собственной угловой скорости шарнира.
        
        Returns:
            Твист шарнира в его системе координат
        &quot;&quot;&quot;
        return Screw2(
            ang=self.omega.value,
            lin=np.zeros(2)
        )

    def twist_after_joint(self, parent_twist: Screw2) -&gt; Screw2:
        &quot;&quot;&quot;
        Вычислить твист дочернего звена на основе твиста родителя.
        
        Трансформация твиста с добавлением собственной скорости шарнира.
        
        Args:
            parent_twist: Твист точки привязки родителя
            
        Returns:
            Твист точки привязки ребенка
        &quot;&quot;&quot;
        # 1. Трансформируем твист родителя в систему шарнира
        parent_twist_in_joint = parent_twist.transform_as_twist_by(self.joint_pose_in_parent)

        # 2. Добавляем собственную угловую скорость шарнира
        joint_twist = parent_twist_in_joint + self.joint_twist_in_joint()
        
        # 3. Трансформируем в точку привязки ребенка
        child_twist = joint_twist.transform_as_twist_by(self.child_pose_in_joint)
        
        return child_twist
    
    def integrate(self, dt: float):
        &quot;&quot;&quot;
        Интегрировать угол из угловой скорости.
        
        Args:
            dt: Шаг по времени [с]
        &quot;&quot;&quot;
        self.angle += self.omega.value * dt
    
    def __repr__(self):
        return f&quot;DollRotatorJoint2D({self.name}, angle={self.angle:.3f}, omega={self.omega.value:.3f})&quot;
</code></pre>
</body>
</html>
