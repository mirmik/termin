<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/dynamic_assembler.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from termin.fem.assembler import MatrixAssembler, Variable, Contribution<br>
from typing import Dict, List, Tuple<br>
import numpy as np<br>
from termin.linalg.subspaces import project_onto_affine, metric_project_onto_constraints <br>
from termin.geombase.pose3 import Pose3<br>
<br>
class DynamicMatrixAssembler(MatrixAssembler):<br>
&#9;def __init__(self):<br>
&#9;&#9;super().__init__()<br>
&#9;&#9;self.time_step = 0.01<br>
<br>
&#9;def _build_index_maps(self) -&gt; Dict[Variable, List[int]]:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Построить отображение: Variable -&gt; глобальные индексы DOF<br>
&#9;&#9;<br>
&#9;&#9;Назначает каждой компоненте каждой переменной уникальный<br>
&#9;&#9;глобальный индекс в системе.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self._index_map_by_tags = {}<br>
&#9;&#9;tags = set(var.tag for var in self.variables)<br>
<br>
&#9;&#9;for tag in tags:<br>
&#9;&#9;&#9;vars_with_tag = [var for var in self.variables if var.tag == tag]<br>
&#9;&#9;&#9;index_map = self._build_index_map(vars_with_tag)<br>
&#9;&#9;&#9;self._index_map_by_tags[tag] = index_map<br>
<br>
&#9;&#9;self._index_map = self._index_map_by_tags.get(&quot;acceleration&quot;, {})<br>
&#9;&#9;self._holonomic_index_map = self._index_map_by_tags.get(&quot;force&quot;, {})<br>
<br>
&#9;&#9;self._dirty_index_map = False<br>
<br>
&#9;# def collect_current_q(self, index_map: Dict[Variable, List[int]]):<br>
&#9;#     &quot;&quot;&quot;Собрать текущее значение q из всех переменных&quot;&quot;&quot;<br>
&#9;#     old_q = np.zeros(self.total_variables_by_tag(&quot;acceleration&quot;))<br>
&#9;#     for var in self.variables:<br>
&#9;#         if var.tag == &quot;acceleration&quot;:<br>
&#9;#             indices = index_map[var]<br>
&#9;#             old_q[indices] = var.value_by_rank(2)  # текущее значение<br>
&#9;#     return old_q<br>
<br>
&#9;# def collect_current_q_dot(self, index_map: Dict[Variable, List[int]]):<br>
&#9;#     &quot;&quot;&quot;Собрать текущее значение q_dot из всех переменных&quot;&quot;&quot;<br>
&#9;#     old_q_dot = np.zeros(self.total_variables_by_tag(&quot;acceleration&quot;))<br>
&#9;#     for var in self.variables:<br>
&#9;#         if var.tag == &quot;acceleration&quot;:<br>
&#9;#             indices = index_map[var]<br>
&#9;#             old_q_dot[indices] = var.value_by_rank(1)  # текущее значение скорости<br>
&#9;#     return old_q_dot<br>
<br>
&#9;# def set_old_q(self, q: np.ndarray):<br>
&#9;#     &quot;&quot;&quot;Установить старое значение q&quot;&quot;&quot;<br>
&#9;#     self.old_q = np.array(q)<br>
<br>
&#9;# def set_old_q_dot(self, q_dot: np.ndarray):<br>
&#9;#     &quot;&quot;&quot;Установить старое значение q_dot&quot;&quot;&quot;<br>
&#9;#     self.old_q_dot = np.array(q_dot)<br>
<br>
&#9;def index_maps(self) -&gt; Dict[str, Dict[Variable, List[int]]]:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Получить текущее отображение Variable -&gt; глобальные индексы DOF<br>
&#9;&#9;для разных типов переменных<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;if self._dirty_index_map:<br>
&#9;&#9;&#9;self._build_index_maps()<br>
&#9;&#9;return {<br>
&#9;&#9;&#9;&quot;acceleration&quot;: self._index_map,<br>
&#9;&#9;&#9;&quot;force&quot;: self._holonomic_index_map<br>
&#9;&#9;}<br>
<br>
&#9;def index_map_by_tag(self, tag: str) -&gt; Dict[Variable, List[int]]:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Получить текущее отображение Variable -&gt; глобальные индексы DOF<br>
&#9;&#9;для переменных с заданным тегом<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;if self._dirty_index_map:<br>
&#9;&#9;&#9;self._build_index_maps()<br>
&#9;&#9;return self._index_map_by_tags.get(tag, {})<br>
<br>
&#9;def assemble_electric_domain(self):<br>
&#9;&#9;# Построить карту индексов<br>
&#9;&#9;index_maps = {<br>
&#9;&#9;&#9;&quot;voltage&quot;: self.index_map_by_tag(&quot;voltage&quot;),<br>
&#9;&#9;&#9;&quot;current&quot;: self.index_map_by_tag(&quot;current&quot;),<br>
&#9;&#9;&#9;#&quot;charge&quot;: self.index_map_by_tag(&quot;charge&quot;),<br>
&#9;&#9;}<br>
<br>
&#9;&#9;# Создать глобальные матрицы и вектор<br>
&#9;&#9;n_voltage = self.total_variables_by_tag(tag=&quot;voltage&quot;)<br>
&#9;&#9;n_currents = self.total_variables_by_tag(tag=&quot;current&quot;)<br>
&#9;&#9;#n_charge = self.total_variables_by_tag(tag=&quot;charge&quot;)<br>
<br>
&#9;&#9;matrices = {<br>
&#9;&#9;&#9;&quot;conductance&quot;: np.zeros((n_voltage, n_voltage)),<br>
&#9;&#9;&#9;&quot;electric_holonomic&quot;: np.zeros((n_currents, n_voltage)),<br>
&#9;&#9;&#9;&quot;electric_holonomic_rhs&quot;: np.zeros(n_currents),<br>
&#9;&#9;&#9;&quot;rhs&quot;: np.zeros(n_voltage),<br>
&#9;&#9;&#9;&quot;current_to_current&quot;: np.zeros((n_currents, n_currents)),<br>
&#9;&#9;&#9;#&quot;charge_constraint&quot;: np.zeros((n_charge, n_voltage)),<br>
&#9;&#9;&#9;#&quot;charge_constraint_rhs&quot;: np.zeros((n_charge)),<br>
&#9;&#9;}<br>
<br>
&#9;&#9;for contribution in self.contributions:<br>
&#9;&#9;&#9;contribution.contribute(matrices, index_maps)<br>
<br>
&#9;&#9;return matrices<br>
<br>
&#9;def assemble_electromechanic_domain(self):<br>
&#9;&#9;# Построить карту индексов<br>
&#9;&#9;index_maps = {<br>
&#9;&#9;&#9;&quot;voltage&quot;: self.index_map_by_tag(&quot;voltage&quot;),<br>
&#9;&#9;&#9;&quot;current&quot;: self.index_map_by_tag(&quot;current&quot;),<br>
&#9;&#9;&#9;&quot;acceleration&quot;: self.index_map_by_tag(&quot;acceleration&quot;),<br>
&#9;&#9;&#9;&quot;force&quot;: self.index_map_by_tag(&quot;force&quot;),<br>
&#9;&#9;}<br>
<br>
&#9;&#9;# Создать глобальные матрицы и вектор<br>
&#9;&#9;n_voltage = self.total_variables_by_tag(tag=&quot;voltage&quot;)<br>
&#9;&#9;n_currents = self.total_variables_by_tag(tag=&quot;current&quot;)<br>
&#9;&#9;n_acceleration = self.total_variables_by_tag(tag=&quot;acceleration&quot;)<br>
&#9;&#9;n_force = self.total_variables_by_tag(tag=&quot;force&quot;)<br>
<br>
&#9;&#9;matrices = {<br>
&#9;&#9;&#9;&quot;conductance&quot;: np.zeros((n_voltage, n_voltage)),<br>
&#9;&#9;&#9;&quot;mass&quot;: np.zeros((n_acceleration, n_acceleration)),<br>
&#9;&#9;&#9;&quot;load&quot; : np.zeros(n_acceleration),<br>
&#9;&#9;&#9;&quot;electric_holonomic&quot;: np.zeros((n_currents, n_voltage)),<br>
&#9;&#9;&#9;&quot;electric_holonomic_rhs&quot;: np.zeros(n_currents),<br>
&#9;&#9;&#9;&quot;current_to_current&quot;: np.zeros((n_currents, n_currents)),<br>
&#9;&#9;&#9;&quot;holonomic&quot;: np.zeros((n_force, n_acceleration)),<br>
&#9;&#9;&#9;&quot;electromechanic_coupling&quot;: np.zeros((n_acceleration, n_currents)),<br>
&#9;&#9;&#9;&quot;electromechanic_coupling_damping&quot;: np.zeros((n_acceleration, n_currents)),<br>
&#9;&#9;&#9;&quot;holonomic_load&quot;: np.zeros(n_force),<br>
&#9;&#9;&#9;&quot;rhs&quot;: np.zeros(n_voltage),<br>
&#9;&#9;}<br>
<br>
&#9;&#9;for contribution in self.contributions:<br>
&#9;&#9;&#9;contribution.contribute(matrices, index_maps)<br>
<br>
&#9;&#9;return matrices<br>
<br>
&#9;def names_from_variables(self, variables: List[Variable]) -&gt; List[str]:<br>
&#9;&#9;&quot;&quot;&quot;Получить список имен переменных из списка Variable&quot;&quot;&quot;<br>
&#9;&#9;names = []<br>
&#9;&#9;for var in variables:<br>
&#9;&#9;&#9;names.extend(var.names())<br>
&#9;&#9;return names<br>
<br>
&#9;def assemble_extended_system_for_electromechanic(self, matrices: Dict[str, np.ndarray]) -&gt; Tuple[np.ndarray, np.ndarray]:<br>
&#9;&#9;n_voltage = self.total_variables_by_tag(tag=&quot;voltage&quot;)<br>
&#9;&#9;n_currents = self.total_variables_by_tag(tag=&quot;current&quot;)<br>
&#9;&#9;n_acceleration = self.total_variables_by_tag(tag=&quot;acceleration&quot;)<br>
&#9;&#9;n_force = self.total_variables_by_tag(tag=&quot;force&quot;)<br>
<br>
&#9;&#9;A_ext = np.zeros((n_voltage + n_currents + n_acceleration + n_force,<br>
&#9;&#9;&#9;&#9;&#9;&#9;n_voltage + n_currents + n_acceleration + n_force))<br>
<br>
&#9;&#9;С_ext = np.zeros((n_voltage + n_currents + n_acceleration + n_force,<br>
&#9;&#9;&#9;&#9;&#9;&#9;n_voltage + n_currents + n_acceleration + n_force))<br>
&#9;&#9;<br>
<br>
&#9;&#9;b_ext = np.zeros(n_voltage + n_currents + n_acceleration + n_force)<br>
&#9;&#9;variables = (<br>
&#9;&#9;&#9;list(self.index_map_by_tag(&quot;voltage&quot;).keys()) +<br>
&#9;&#9;&#9;list(self.index_map_by_tag(&quot;current&quot;).keys()) +<br>
&#9;&#9;&#9;list(self.index_map_by_tag(&quot;acceleration&quot;).keys()) +<br>
&#9;&#9;&#9;list(self.index_map_by_tag(&quot;force&quot;).keys())<br>
&#9;&#9;)<br>
&#9;&#9;variables = self.names_from_variables(variables)<br>
<br>
&#9;&#9;r0 = n_voltage<br>
&#9;&#9;r1 = n_voltage + n_currents<br>
&#9;&#9;r2 = n_voltage + n_currents + n_acceleration<br>
&#9;&#9;r3 = n_voltage + n_currents + n_acceleration + n_force<br>
<br>
&#9;&#9;#v = [0:r0]<br>
&#9;&#9;#c = [r0:r1]<br>
&#9;&#9;#a = [r1:r2]<br>
&#9;&#9;#f = [r2:r3]<br>
&#9;&#9;print(r0, r1, r2, r3)<br>
&#9;&#9;print(matrices[&quot;electromechanic_coupling&quot;].shape)<br>
<br>
&#9;&#9;A_ext[0:r0, 0:r0] = matrices[&quot;conductance&quot;]<br>
&#9;&#9;A_ext[r0:r1, 0:r0] = matrices[&quot;electric_holonomic&quot;]<br>
&#9;&#9;A_ext[0:r0, r0:r1] = matrices[&quot;electric_holonomic&quot;].T<br>
&#9;&#9;A_ext[r0:r1, r0:r1] = matrices[&quot;current_to_current&quot;]<br>
<br>
&#9;&#9;A_ext[r1:r2, r1:r2] = matrices[&quot;mass&quot;]        <br>
&#9;&#9;A_ext[r2:r3, r1:r2] = matrices[&quot;holonomic&quot;]<br>
&#9;&#9;A_ext[r1:r2, r2:r3] = matrices[&quot;holonomic&quot;].T<br>
<br>
&#9;&#9;A_ext[r1:r2, r0:r1] = matrices[&quot;electromechanic_coupling&quot;]<br>
&#9;&#9;#A_ext[r0:r1, r1:r2] = matrices[&quot;electromechanic_coupling&quot;].T<br>
<br>
&#9;&#9;b_ext[0:r0] = matrices[&quot;rhs&quot;]<br>
&#9;&#9;b_ext[r0:r1] = matrices[&quot;electric_holonomic_rhs&quot;]<br>
&#9;&#9;b_ext[r1:r2] = matrices[&quot;load&quot;]<br>
&#9;&#9;b_ext[r2:r3] = matrices[&quot;holonomic_load&quot;]<br>
<br>
&#9;&#9;EM_damping = matrices[&quot;electromechanic_coupling_damping&quot;]<br>
&#9;&#9;q_dot = self.collect_variables(&quot;velocity&quot;)<br>
&#9;&#9;b_em = EM_damping @ q_dot<br>
&#9;&#9;b_ext[r0:r1] += b_em<br>
<br>
&#9;&#9;return A_ext, b_ext, variables<br>
<br>
&#9;def assemble_extended_system_for_electric(self, matrices: Dict[str, np.ndarray]) -&gt; Tuple[np.ndarray, np.ndarray]:<br>
&#9;&#9;n_voltage = self.total_variables_by_tag(tag=&quot;voltage&quot;)<br>
&#9;&#9;n_currents = self.total_variables_by_tag(tag=&quot;current&quot;)<br>
<br>
&#9;&#9;A_ext = np.zeros((n_voltage + n_currents, n_voltage + n_currents))<br>
&#9;&#9;b_ext = np.zeros(n_voltage + n_currents)<br>
&#9;&#9;variables = (<br>
&#9;&#9;&#9;list(self.index_map_by_tag(&quot;voltage&quot;).keys()) +<br>
&#9;&#9;&#9;list(self.index_map_by_tag(&quot;current&quot;).keys()))<br>
&#9;&#9;variables = [var for var in variables]<br>
<br>
&#9;&#9;r0 = n_voltage<br>
&#9;&#9;r1 = n_voltage + n_currents<br>
&#9;&#9;c0 = n_voltage<br>
&#9;&#9;c1 = n_voltage + n_currents<br>
<br>
&#9;&#9;A_ext[0:r0, 0:c0] = matrices[&quot;conductance&quot;]<br>
&#9;&#9;A_ext[r0:r1, 0:c0] = matrices[&quot;electric_holonomic&quot;]<br>
&#9;&#9;A_ext[0:r0, c0:c1] = matrices[&quot;electric_holonomic&quot;].T<br>
&#9;&#9;A_ext[c0:c1, c0:c1] = matrices[&quot;current_to_current&quot;]<br>
<br>
&#9;&#9;b_ext[0:r0] = matrices[&quot;rhs&quot;]<br>
&#9;&#9;b_ext[r0:r1] = matrices[&quot;electric_holonomic_rhs&quot;]<br>
<br>
&#9;&#9;return A_ext, b_ext, variables <br>
<br>
&#9;def assemble(self):<br>
&#9;&#9;# Построить карту индексов<br>
&#9;&#9;index_maps = self.index_maps()<br>
<br>
&#9;&#9;# Создать глобальные матрицы и вектор<br>
&#9;&#9;n_dofs = self.total_variables_by_tag(tag=&quot;acceleration&quot;)<br>
&#9;&#9;n_positions = self.total_variables_by_tag(tag=&quot;position&quot;)<br>
&#9;&#9;n_constraints = self.total_variables_by_tag(tag=&quot;force&quot;)<br>
<br>
&#9;&#9;matrices = {<br>
&#9;&#9;&#9;&quot;mass&quot;: np.zeros((n_dofs, n_dofs)),<br>
&#9;&#9;&#9;&quot;damping&quot;: np.zeros((n_dofs, n_dofs)),<br>
&#9;&#9;&#9;&quot;stiffness&quot;: np.zeros((n_dofs, n_positions)),<br>
&#9;&#9;&#9;&quot;load&quot;: np.zeros(n_dofs),<br>
&#9;&#9;&#9;&quot;holonomic&quot;: np.zeros((n_constraints, n_dofs)),<br>
&#9;&#9;&#9;&quot;holonomic_rhs&quot;: np.zeros(n_constraints),<br>
&#9;&#9;&#9;#&quot;old_q&quot;: self.collect_variables(index_maps[&quot;acceleration&quot;]),<br>
&#9;&#9;&#9;#&quot;old_q_dot&quot;: self.collect_current_q_dot(index_maps[&quot;acceleration&quot;]),<br>
&#9;&#9;&#9;#&quot;holonomic_velocity_rhs&quot;: np.zeros(n_constraints),<br>
&#9;&#9;}<br>
<br>
&#9;&#9;for contribution in self.contributions:<br>
&#9;&#9;&#9;contribution.contribute(matrices, index_maps)<br>
<br>
&#9;&#9;return matrices<br>
<br>
&#9;def assemble_for_constraints_correction(self):<br>
&#9;&#9;# Построить карту индексов<br>
&#9;&#9;index_maps = self.index_maps()<br>
<br>
&#9;&#9;# Создать глобальные матрицы и вектор<br>
&#9;&#9;n_dofs = self.total_variables_by_tag(tag=&quot;acceleration&quot;)<br>
&#9;&#9;n_constraints = self.total_variables_by_tag(tag=&quot;force&quot;)<br>
<br>
&#9;&#9;matrices = {<br>
&#9;&#9;&#9;&quot;mass&quot;: np.zeros((n_dofs, n_dofs)),<br>
&#9;&#9;&#9;&quot;holonomic&quot;: np.zeros((n_constraints, n_dofs)),<br>
&#9;&#9;&#9;&quot;position_error&quot;: np.zeros(n_constraints),<br>
&#9;&#9;&#9;&quot;holonomic_velocity_rhs&quot;: np.zeros(n_constraints),<br>
&#9;&#9;}<br>
<br>
&#9;&#9;for contribution in self.contributions:<br>
&#9;&#9;&#9;contribution.contribute_for_constraints_correction(matrices, index_maps)<br>
<br>
&#9;&#9;return matrices<br>
<br>
&#9;def assemble_extended_system(self, matrices: Dict[str, np.ndarray]) -&gt; Tuple[np.ndarray, np.ndarray]:<br>
&#9;&#9;A = matrices[&quot;mass&quot;]<br>
&#9;&#9;C = matrices[&quot;damping&quot;]<br>
&#9;&#9;K = matrices[&quot;stiffness&quot;]<br>
&#9;&#9;b = matrices[&quot;load&quot;]<br>
&#9;&#9;old_q_dot = self.collect_variables(&quot;velocity&quot;)<br>
&#9;&#9;old_q = self.collect_variables(&quot;position&quot;)<br>
&#9;&#9;H = matrices[&quot;holonomic&quot;]<br>
&#9;&#9;h = matrices[&quot;holonomic_rhs&quot;]<br>
<br>
&#9;&#9;variables = (<br>
&#9;&#9;&#9;list(self.index_map_by_tag(&quot;acceleration&quot;).keys()) + <br>
&#9;&#9;&#9;list(self.index_map_by_tag(&quot;force&quot;).keys()))<br>
&#9;&#9;variables = self.names_from_variables(variables)<br>
<br>
&#9;&#9;size = self.total_variables_by_tag(tag=&quot;acceleration&quot;) + self.total_variables_by_tag(tag=&quot;force&quot;)<br>
&#9;&#9;n_dofs = self.total_variables_by_tag(tag=&quot;acceleration&quot;)<br>
&#9;&#9;n_holonomic = self.total_variables_by_tag(tag=&quot;force&quot;)<br>
<br>
&#9;&#9;# Расширенная система<br>
&#9;&#9;A_ext = np.zeros((size, size))<br>
&#9;&#9;b_ext = np.zeros(size)<br>
<br>
&#9;&#9;r0 = A.shape[0]<br>
&#9;&#9;r1 = A.shape[0] + n_holonomic<br>
<br>
&#9;&#9;c0 = A.shape[1]<br>
&#9;&#9;c1 = A.shape[1] + n_holonomic<br>
<br>
&#9;&#9;A_ext[0:r0, 0:c0] = A<br>
&#9;&#9;A_ext[0:r0, c0:c1] = H.T<br>
&#9;&#9;A_ext[r0:r1, 0:c0] = H<br>
&#9;&#9;b_ext[0:r0] = b - C @ old_q_dot - K @ old_q<br>
&#9;&#9;b_ext[r0:r1] = h<br>
<br>
&#9;&#9;return A_ext, b_ext, variables<br>
<br>
&#9;def velocity_project_onto_constraints(self, q_dot: np.ndarray, matrices: Dict[str, np.ndarray]) -&gt; np.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Проецировать скорости на ограничения&quot;&quot;&quot;<br>
&#9;&#9;H = matrices[&quot;holonomic&quot;]<br>
&#9;&#9;h = matrices[&quot;holonomic_velocity_rhs&quot;]<br>
&#9;&#9;M = matrices[&quot;mass&quot;]<br>
&#9;&#9;M_inv = np.linalg.inv(M)<br>
&#9;&#9;return metric_project_onto_constraints(q_dot, H, M_inv, h=h)<br>
<br>
&#9;def coords_project_onto_constraints(self, q: np.ndarray, matrices: Dict[str, np.ndarray]) -&gt; np.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Проецировать скорости на ограничения&quot;&quot;&quot;<br>
&#9;&#9;H = matrices[&quot;holonomic&quot;]<br>
&#9;&#9;f = matrices[&quot;position_error&quot;]<br>
&#9;&#9;M = matrices[&quot;mass&quot;]<br>
&#9;&#9;M_inv = np.linalg.inv(M)<br>
&#9;&#9;return metric_project_onto_constraints(q, H, M_inv, error=f)<br>
<br>
&#9;def collect_variables(self, tag: str) -&gt; np.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Собрать текущее значение переменных с заданным тегом из всех переменных&quot;&quot;&quot;<br>
&#9;&#9;q = np.zeros(self.total_variables_by_tag(tag))<br>
&#9;&#9;index_map = self.index_map_by_tag(tag)<br>
&#9;&#9;for var in self.variables:<br>
&#9;&#9;&#9;if var.tag == tag:<br>
&#9;&#9;&#9;&#9;indices = index_map[var]<br>
&#9;&#9;&#9;&#9;q[indices] = var.value  # текущее значение<br>
&#9;&#9;return q<br>
<br>
&#9;def upload_variables(self, tag: str, values: np.ndarray):<br>
&#9;&#9;&quot;&quot;&quot;Загрузить значения переменных с заданным тегом обратно в переменные&quot;&quot;&quot;<br>
&#9;&#9;index_map = self.index_map_by_tag(tag)<br>
&#9;&#9;count = 0<br>
&#9;&#9;for var in self.variables:<br>
&#9;&#9;&#9;if var.tag == tag:<br>
&#9;&#9;&#9;&#9;indices = index_map[var]<br>
&#9;&#9;&#9;&#9;var.set_value(values[indices])<br>
&#9;&#9;&#9;&#9;count += var.size<br>
&#9;&#9;if count != len(values):<br>
&#9;&#9;&#9;raise ValueError(&quot;Количество загруженных значений не соответствует количеству переменных с заданным тегом&quot;)<br>
<br>
&#9;def upload_solution(self, variables: List[Variable], values: np.ndarray):<br>
&#9;&#9;&quot;&quot;&quot;Загрузить значения обратно в переменные по списку Variable&quot;&quot;&quot;<br>
&#9;&#9;index = 0<br>
&#9;&#9;for var in variables:<br>
&#9;&#9;&#9;size = var.size<br>
&#9;&#9;&#9;var.set_value(values[index:index + size])<br>
&#9;&#9;&#9;index += size<br>
&#9;&#9;if index != len(values):<br>
&#9;&#9;&#9;raise ValueError(&quot;Количество загруженных значений не соответствует количеству переменных&quot;)<br>
<br>
&#9;def integrate_with_constraint_projection(self, <br>
&#9;&#9;&#9;&#9;q_ddot: np.ndarray, matrices: Dict[str, np.ndarray]):<br>
&#9;&#9;dt = self.time_step<br>
<br>
&#9;&#9;self.upload_variables(&quot;acceleration&quot;, q_ddot)<br>
<br>
&#9;&#9;for contribution in self.contributions:<br>
&#9;&#9;&#9;contribution.finish_timestep(dt)<br>
<br>
&#9;&#9;q_dot = self.collect_variables(&quot;velocity&quot;)<br>
<br>
&#9;&#9;for _ in range(2):  # несколько итераций проекции положений<br>
&#9;&#9;&#9;q = self.collect_variables(&quot;position&quot;)<br>
&#9;&#9;&#9;matrices = self.assemble_for_constraints_correction()<br>
&#9;&#9;&#9;q = self.coords_project_onto_constraints(q, matrices)<br>
&#9;&#9;&#9;self.upload_variables(&quot;position&quot;, q)<br>
&#9;&#9;&#9;for contribution in self.contributions:<br>
&#9;&#9;&#9;&#9;if hasattr(contribution, &quot;finish_correction_step&quot;):<br>
&#9;&#9;&#9;&#9;&#9;contribution.finish_correction_step()<br>
&#9;&#9;<br>
&#9;&#9;matrices = self.assemble_for_constraints_correction()<br>
&#9;&#9;q_dot = self.velocity_project_onto_constraints(q_dot, matrices)   <br>
&#9;&#9;self.upload_variables(&quot;velocity&quot;, q_dot)<br>
<br>
&#9;&#9;return q_dot, q<br>
<br>
&#9;def sort_results(self, x_ext: np.ndarray) -&gt; Tuple[np.ndarray, np.ndarray, np.ndarray]:<br>
&#9;&#9;&quot;&quot;&quot;Разделить расширенное решение на ускорения и множители Лагранжа&quot;&quot;&quot;<br>
&#9;&#9;n_dofs = self.total_variables_by_tag(tag=&quot;acceleration&quot;)<br>
&#9;&#9;n_holonomic = self.total_variables_by_tag(tag=&quot;force&quot;)<br>
<br>
&#9;&#9;q_ddot = x_ext[:n_dofs]<br>
&#9;&#9;holonomic_lambdas = x_ext[n_dofs:n_dofs + n_holonomic]<br>
<br>
&#9;&#9;nonholonomic_lambdas = []<br>
<br>
&#9;&#9;return q_ddot, holonomic_lambdas, nonholonomic_lambdas<br>
<br>
&#9;def integrate_velocities(self, old_q_dot: np.ndarray, q_ddot: np.ndarray) -&gt; np.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Интегрировать ускорения для получения новых скоростей&quot;&quot;&quot;<br>
&#9;&#9;return old_q_dot + q_ddot * self.time_step<br>
<br>
&#9;def restore_velocity_constraints(self, q_dot: np.ndarray, HN: np.ndarray, hn: np.ndarray) -&gt; np.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Восстановить ограничения на скорости (например, для закрепленных тел)<br>
<br>
&#9;&#9;&#9;HN - матрица ограничений на скорости, объединение H и N<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;return project_onto_affine(q_dot, HN, hn)<br>
<br>
&#9;def integrate_positions(self, old_q: np.ndarray, q_dot: np.ndarray, q_ddot: np.ndarray) -&gt; np.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Интегрировать скорости для получения новых положений&quot;&quot;&quot;<br>
&#9;&#9;return old_q + q_dot * self.time_step + 0.5 * q_ddot * self.time_step**2<br>
<br>
&#9;# def restore_position_constraints(self, q: np.ndarray, H: np.ndarray, h: np.ndarray) -&gt; np.ndarray:<br>
&#9;#     &quot;&quot;&quot;Восстановить ограничения на положения (например, для закрепленных тел)&quot;&quot;&quot;<br>
&#9;#     return project_onto_affine(q, H, h)<br>
<br>
&#9;def upload_results(self, q_ddot: np.ndarray, q_dot: np.ndarray, q: np.ndarray):<br>
&#9;&#9;&quot;&quot;&quot;Загрузить результаты обратно в переменные&quot;&quot;&quot;<br>
&#9;&#9;index_map = self.index_maps()[&quot;acceleration&quot;]<br>
&#9;&#9;for var in self.variables:<br>
&#9;&#9;&#9;if var.tag == &quot;acceleration&quot;:<br>
&#9;&#9;&#9;&#9;indices = index_map[var]<br>
&#9;&#9;&#9;&#9;var.set_values(q_ddot[indices], q_dot[indices], q[indices])<br>
<br>
&#9;def upload_result_values(self, q: np.ndarray):<br>
&#9;&#9;&quot;&quot;&quot;Загрузить только положения обратно в переменные&quot;&quot;&quot;<br>
&#9;&#9;index_map = self.index_maps()[&quot;acceleration&quot;]<br>
&#9;&#9;for var in self.variables:<br>
&#9;&#9;&#9;if var.tag == &quot;acceleration&quot;:<br>
&#9;&#9;&#9;&#9;indices = index_map[var]<br>
&#9;&#9;&#9;&#9;var.set_value(q[indices])<br>
<br>
&#9;def integrate_nonlinear(self):<br>
&#9;&#9;&quot;&quot;&quot;Интегрировать нелинейные переменные (если есть)&quot;&quot;&quot;<br>
&#9;&#9;index_map = self.index_maps()[&quot;acceleration&quot;]<br>
&#9;&#9;for var in self.variables:<br>
&#9;&#9;&#9;if var.tag == &quot;acceleration&quot;:<br>
&#9;&#9;&#9;&#9;var.integrate_nonlinear(self.time_step)<br>
<!-- END SCAT CODE -->
</body>
</html>
