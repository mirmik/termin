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
    def __init__(self):<br>
        super().__init__()<br>
        self.time_step = 0.01<br>
<br>
    def _build_index_maps(self) -&gt; Dict[Variable, List[int]]:<br>
        &quot;&quot;&quot;<br>
        Построить отображение: Variable -&gt; глобальные индексы DOF<br>
        <br>
        Назначает каждой компоненте каждой переменной уникальный<br>
        глобальный индекс в системе.<br>
        &quot;&quot;&quot;<br>
        self._index_map_by_tags = {}<br>
        tags = set(var.tag for var in self.variables)<br>
<br>
        for tag in tags:<br>
            vars_with_tag = [var for var in self.variables if var.tag == tag]<br>
            index_map = self._build_index_map(vars_with_tag)<br>
            self._index_map_by_tags[tag] = index_map<br>
<br>
        self._index_map = self._index_map_by_tags.get(&quot;acceleration&quot;, {})<br>
        self._holonomic_index_map = self._index_map_by_tags.get(&quot;force&quot;, {})<br>
<br>
        self._dirty_index_map = False<br>
<br>
    # def collect_current_q(self, index_map: Dict[Variable, List[int]]):<br>
    #     &quot;&quot;&quot;Собрать текущее значение q из всех переменных&quot;&quot;&quot;<br>
    #     old_q = np.zeros(self.total_variables_by_tag(&quot;acceleration&quot;))<br>
    #     for var in self.variables:<br>
    #         if var.tag == &quot;acceleration&quot;:<br>
    #             indices = index_map[var]<br>
    #             old_q[indices] = var.value_by_rank(2)  # текущее значение<br>
    #     return old_q<br>
<br>
    # def collect_current_q_dot(self, index_map: Dict[Variable, List[int]]):<br>
    #     &quot;&quot;&quot;Собрать текущее значение q_dot из всех переменных&quot;&quot;&quot;<br>
    #     old_q_dot = np.zeros(self.total_variables_by_tag(&quot;acceleration&quot;))<br>
    #     for var in self.variables:<br>
    #         if var.tag == &quot;acceleration&quot;:<br>
    #             indices = index_map[var]<br>
    #             old_q_dot[indices] = var.value_by_rank(1)  # текущее значение скорости<br>
    #     return old_q_dot<br>
<br>
    # def set_old_q(self, q: np.ndarray):<br>
    #     &quot;&quot;&quot;Установить старое значение q&quot;&quot;&quot;<br>
    #     self.old_q = np.array(q)<br>
<br>
    # def set_old_q_dot(self, q_dot: np.ndarray):<br>
    #     &quot;&quot;&quot;Установить старое значение q_dot&quot;&quot;&quot;<br>
    #     self.old_q_dot = np.array(q_dot)<br>
<br>
    def index_maps(self) -&gt; Dict[str, Dict[Variable, List[int]]]:<br>
        &quot;&quot;&quot;<br>
        Получить текущее отображение Variable -&gt; глобальные индексы DOF<br>
        для разных типов переменных<br>
        &quot;&quot;&quot;<br>
        if self._dirty_index_map:<br>
            self._build_index_maps()<br>
        return {<br>
            &quot;acceleration&quot;: self._index_map,<br>
            &quot;force&quot;: self._holonomic_index_map<br>
        }<br>
<br>
    def index_map_by_tag(self, tag: str) -&gt; Dict[Variable, List[int]]:<br>
        &quot;&quot;&quot;<br>
        Получить текущее отображение Variable -&gt; глобальные индексы DOF<br>
        для переменных с заданным тегом<br>
        &quot;&quot;&quot;<br>
        if self._dirty_index_map:<br>
            self._build_index_maps()<br>
        return self._index_map_by_tags.get(tag, {})<br>
<br>
    def assemble_electric_domain(self):<br>
        # Построить карту индексов<br>
        index_maps = {<br>
            &quot;voltage&quot;: self.index_map_by_tag(&quot;voltage&quot;),<br>
            &quot;current&quot;: self.index_map_by_tag(&quot;current&quot;),<br>
            #&quot;charge&quot;: self.index_map_by_tag(&quot;charge&quot;),<br>
        }<br>
<br>
        # Создать глобальные матрицы и вектор<br>
        n_voltage = self.total_variables_by_tag(tag=&quot;voltage&quot;)<br>
        n_currents = self.total_variables_by_tag(tag=&quot;current&quot;)<br>
        #n_charge = self.total_variables_by_tag(tag=&quot;charge&quot;)<br>
<br>
        matrices = {<br>
            &quot;conductance&quot;: np.zeros((n_voltage, n_voltage)),<br>
            &quot;electric_holonomic&quot;: np.zeros((n_currents, n_voltage)),<br>
            &quot;electric_holonomic_rhs&quot;: np.zeros(n_currents),<br>
            &quot;rhs&quot;: np.zeros(n_voltage),<br>
            &quot;current_to_current&quot;: np.zeros((n_currents, n_currents)),<br>
            #&quot;charge_constraint&quot;: np.zeros((n_charge, n_voltage)),<br>
            #&quot;charge_constraint_rhs&quot;: np.zeros((n_charge)),<br>
        }<br>
<br>
        for contribution in self.contributions:<br>
            contribution.contribute(matrices, index_maps)<br>
<br>
        return matrices<br>
<br>
    def assemble_electromechanic_domain(self):<br>
        # Построить карту индексов<br>
        index_maps = {<br>
            &quot;voltage&quot;: self.index_map_by_tag(&quot;voltage&quot;),<br>
            &quot;current&quot;: self.index_map_by_tag(&quot;current&quot;),<br>
            &quot;acceleration&quot;: self.index_map_by_tag(&quot;acceleration&quot;),<br>
            &quot;force&quot;: self.index_map_by_tag(&quot;force&quot;),<br>
        }<br>
<br>
        # Создать глобальные матрицы и вектор<br>
        n_voltage = self.total_variables_by_tag(tag=&quot;voltage&quot;)<br>
        n_currents = self.total_variables_by_tag(tag=&quot;current&quot;)<br>
        n_acceleration = self.total_variables_by_tag(tag=&quot;acceleration&quot;)<br>
        n_force = self.total_variables_by_tag(tag=&quot;force&quot;)<br>
<br>
        matrices = {<br>
            &quot;conductance&quot;: np.zeros((n_voltage, n_voltage)),<br>
            &quot;mass&quot;: np.zeros((n_acceleration, n_acceleration)),<br>
            &quot;load&quot; : np.zeros(n_acceleration),<br>
            &quot;electric_holonomic&quot;: np.zeros((n_currents, n_voltage)),<br>
            &quot;electric_holonomic_rhs&quot;: np.zeros(n_currents),<br>
            &quot;current_to_current&quot;: np.zeros((n_currents, n_currents)),<br>
            &quot;holonomic&quot;: np.zeros((n_force, n_acceleration)),<br>
            &quot;electromechanic_coupling&quot;: np.zeros((n_acceleration, n_currents)),<br>
            &quot;electromechanic_coupling_damping&quot;: np.zeros((n_acceleration, n_currents)),<br>
            &quot;holonomic_load&quot;: np.zeros(n_force),<br>
            &quot;rhs&quot;: np.zeros(n_voltage),<br>
        }<br>
<br>
        for contribution in self.contributions:<br>
            contribution.contribute(matrices, index_maps)<br>
<br>
        return matrices<br>
<br>
    def names_from_variables(self, variables: List[Variable]) -&gt; List[str]:<br>
        &quot;&quot;&quot;Получить список имен переменных из списка Variable&quot;&quot;&quot;<br>
        names = []<br>
        for var in variables:<br>
            names.extend(var.names())<br>
        return names<br>
<br>
    def assemble_extended_system_for_electromechanic(self, matrices: Dict[str, np.ndarray]) -&gt; Tuple[np.ndarray, np.ndarray]:<br>
        n_voltage = self.total_variables_by_tag(tag=&quot;voltage&quot;)<br>
        n_currents = self.total_variables_by_tag(tag=&quot;current&quot;)<br>
        n_acceleration = self.total_variables_by_tag(tag=&quot;acceleration&quot;)<br>
        n_force = self.total_variables_by_tag(tag=&quot;force&quot;)<br>
<br>
        A_ext = np.zeros((n_voltage + n_currents + n_acceleration + n_force,<br>
                          n_voltage + n_currents + n_acceleration + n_force))<br>
<br>
        С_ext = np.zeros((n_voltage + n_currents + n_acceleration + n_force,<br>
                          n_voltage + n_currents + n_acceleration + n_force))<br>
        <br>
<br>
        b_ext = np.zeros(n_voltage + n_currents + n_acceleration + n_force)<br>
        variables = (<br>
            list(self.index_map_by_tag(&quot;voltage&quot;).keys()) +<br>
            list(self.index_map_by_tag(&quot;current&quot;).keys()) +<br>
            list(self.index_map_by_tag(&quot;acceleration&quot;).keys()) +<br>
            list(self.index_map_by_tag(&quot;force&quot;).keys())<br>
        )<br>
        variables = self.names_from_variables(variables)<br>
<br>
        r0 = n_voltage<br>
        r1 = n_voltage + n_currents<br>
        r2 = n_voltage + n_currents + n_acceleration<br>
        r3 = n_voltage + n_currents + n_acceleration + n_force<br>
<br>
        #v = [0:r0]<br>
        #c = [r0:r1]<br>
        #a = [r1:r2]<br>
        #f = [r2:r3]<br>
        print(r0, r1, r2, r3)<br>
        print(matrices[&quot;electromechanic_coupling&quot;].shape)<br>
<br>
        A_ext[0:r0, 0:r0] = matrices[&quot;conductance&quot;]<br>
        A_ext[r0:r1, 0:r0] = matrices[&quot;electric_holonomic&quot;]<br>
        A_ext[0:r0, r0:r1] = matrices[&quot;electric_holonomic&quot;].T<br>
        A_ext[r0:r1, r0:r1] = matrices[&quot;current_to_current&quot;]<br>
<br>
        A_ext[r1:r2, r1:r2] = matrices[&quot;mass&quot;]        <br>
        A_ext[r2:r3, r1:r2] = matrices[&quot;holonomic&quot;]<br>
        A_ext[r1:r2, r2:r3] = matrices[&quot;holonomic&quot;].T<br>
<br>
        A_ext[r1:r2, r0:r1] = matrices[&quot;electromechanic_coupling&quot;]<br>
        #A_ext[r0:r1, r1:r2] = matrices[&quot;electromechanic_coupling&quot;].T<br>
<br>
        b_ext[0:r0] = matrices[&quot;rhs&quot;]<br>
        b_ext[r0:r1] = matrices[&quot;electric_holonomic_rhs&quot;]<br>
        b_ext[r1:r2] = matrices[&quot;load&quot;]<br>
        b_ext[r2:r3] = matrices[&quot;holonomic_load&quot;]<br>
<br>
        EM_damping = matrices[&quot;electromechanic_coupling_damping&quot;]<br>
        q_dot = self.collect_variables(&quot;velocity&quot;)<br>
        b_em = EM_damping @ q_dot<br>
        b_ext[r0:r1] += b_em<br>
<br>
        return A_ext, b_ext, variables<br>
<br>
    def assemble_extended_system_for_electric(self, matrices: Dict[str, np.ndarray]) -&gt; Tuple[np.ndarray, np.ndarray]:<br>
        n_voltage = self.total_variables_by_tag(tag=&quot;voltage&quot;)<br>
        n_currents = self.total_variables_by_tag(tag=&quot;current&quot;)<br>
<br>
        A_ext = np.zeros((n_voltage + n_currents, n_voltage + n_currents))<br>
        b_ext = np.zeros(n_voltage + n_currents)<br>
        variables = (<br>
            list(self.index_map_by_tag(&quot;voltage&quot;).keys()) +<br>
            list(self.index_map_by_tag(&quot;current&quot;).keys()))<br>
        variables = [var for var in variables]<br>
<br>
        r0 = n_voltage<br>
        r1 = n_voltage + n_currents<br>
        c0 = n_voltage<br>
        c1 = n_voltage + n_currents<br>
<br>
        A_ext[0:r0, 0:c0] = matrices[&quot;conductance&quot;]<br>
        A_ext[r0:r1, 0:c0] = matrices[&quot;electric_holonomic&quot;]<br>
        A_ext[0:r0, c0:c1] = matrices[&quot;electric_holonomic&quot;].T<br>
        A_ext[c0:c1, c0:c1] = matrices[&quot;current_to_current&quot;]<br>
<br>
        b_ext[0:r0] = matrices[&quot;rhs&quot;]<br>
        b_ext[r0:r1] = matrices[&quot;electric_holonomic_rhs&quot;]<br>
<br>
        return A_ext, b_ext, variables <br>
<br>
    def assemble(self):<br>
        # Построить карту индексов<br>
        index_maps = self.index_maps()<br>
<br>
        # Создать глобальные матрицы и вектор<br>
        n_dofs = self.total_variables_by_tag(tag=&quot;acceleration&quot;)<br>
        n_positions = self.total_variables_by_tag(tag=&quot;position&quot;)<br>
        n_constraints = self.total_variables_by_tag(tag=&quot;force&quot;)<br>
<br>
        matrices = {<br>
            &quot;mass&quot;: np.zeros((n_dofs, n_dofs)),<br>
            &quot;damping&quot;: np.zeros((n_dofs, n_dofs)),<br>
            &quot;stiffness&quot;: np.zeros((n_dofs, n_positions)),<br>
            &quot;load&quot;: np.zeros(n_dofs),<br>
            &quot;holonomic&quot;: np.zeros((n_constraints, n_dofs)),<br>
            &quot;holonomic_rhs&quot;: np.zeros(n_constraints),<br>
            #&quot;old_q&quot;: self.collect_variables(index_maps[&quot;acceleration&quot;]),<br>
            #&quot;old_q_dot&quot;: self.collect_current_q_dot(index_maps[&quot;acceleration&quot;]),<br>
            #&quot;holonomic_velocity_rhs&quot;: np.zeros(n_constraints),<br>
        }<br>
<br>
        for contribution in self.contributions:<br>
            contribution.contribute(matrices, index_maps)<br>
<br>
        return matrices<br>
<br>
    def assemble_for_constraints_correction(self):<br>
        # Построить карту индексов<br>
        index_maps = self.index_maps()<br>
<br>
        # Создать глобальные матрицы и вектор<br>
        n_dofs = self.total_variables_by_tag(tag=&quot;acceleration&quot;)<br>
        n_constraints = self.total_variables_by_tag(tag=&quot;force&quot;)<br>
<br>
        matrices = {<br>
            &quot;mass&quot;: np.zeros((n_dofs, n_dofs)),<br>
            &quot;holonomic&quot;: np.zeros((n_constraints, n_dofs)),<br>
            &quot;position_error&quot;: np.zeros(n_constraints),<br>
            &quot;holonomic_velocity_rhs&quot;: np.zeros(n_constraints),<br>
        }<br>
<br>
        for contribution in self.contributions:<br>
            contribution.contribute_for_constraints_correction(matrices, index_maps)<br>
<br>
        return matrices<br>
<br>
    def assemble_extended_system(self, matrices: Dict[str, np.ndarray]) -&gt; Tuple[np.ndarray, np.ndarray]:<br>
        A = matrices[&quot;mass&quot;]<br>
        C = matrices[&quot;damping&quot;]<br>
        K = matrices[&quot;stiffness&quot;]<br>
        b = matrices[&quot;load&quot;]<br>
        old_q_dot = self.collect_variables(&quot;velocity&quot;)<br>
        old_q = self.collect_variables(&quot;position&quot;)<br>
        H = matrices[&quot;holonomic&quot;]<br>
        h = matrices[&quot;holonomic_rhs&quot;]<br>
<br>
        variables = (<br>
            list(self.index_map_by_tag(&quot;acceleration&quot;).keys()) + <br>
            list(self.index_map_by_tag(&quot;force&quot;).keys()))<br>
        variables = self.names_from_variables(variables)<br>
<br>
        size = self.total_variables_by_tag(tag=&quot;acceleration&quot;) + self.total_variables_by_tag(tag=&quot;force&quot;)<br>
        n_dofs = self.total_variables_by_tag(tag=&quot;acceleration&quot;)<br>
        n_holonomic = self.total_variables_by_tag(tag=&quot;force&quot;)<br>
<br>
        # Расширенная система<br>
        A_ext = np.zeros((size, size))<br>
        b_ext = np.zeros(size)<br>
<br>
        r0 = A.shape[0]<br>
        r1 = A.shape[0] + n_holonomic<br>
<br>
        c0 = A.shape[1]<br>
        c1 = A.shape[1] + n_holonomic<br>
<br>
        A_ext[0:r0, 0:c0] = A<br>
        A_ext[0:r0, c0:c1] = H.T<br>
        A_ext[r0:r1, 0:c0] = H<br>
        b_ext[0:r0] = b - C @ old_q_dot - K @ old_q<br>
        b_ext[r0:r1] = h<br>
<br>
        return A_ext, b_ext, variables<br>
<br>
    def velocity_project_onto_constraints(self, q_dot: np.ndarray, matrices: Dict[str, np.ndarray]) -&gt; np.ndarray:<br>
        &quot;&quot;&quot;Проецировать скорости на ограничения&quot;&quot;&quot;<br>
        H = matrices[&quot;holonomic&quot;]<br>
        h = matrices[&quot;holonomic_velocity_rhs&quot;]<br>
        M = matrices[&quot;mass&quot;]<br>
        M_inv = np.linalg.inv(M)<br>
        return metric_project_onto_constraints(q_dot, H, M_inv, h=h)<br>
<br>
    def coords_project_onto_constraints(self, q: np.ndarray, matrices: Dict[str, np.ndarray]) -&gt; np.ndarray:<br>
        &quot;&quot;&quot;Проецировать скорости на ограничения&quot;&quot;&quot;<br>
        H = matrices[&quot;holonomic&quot;]<br>
        f = matrices[&quot;position_error&quot;]<br>
        M = matrices[&quot;mass&quot;]<br>
        M_inv = np.linalg.inv(M)<br>
        return metric_project_onto_constraints(q, H, M_inv, error=f)<br>
<br>
    def collect_variables(self, tag: str) -&gt; np.ndarray:<br>
        &quot;&quot;&quot;Собрать текущее значение переменных с заданным тегом из всех переменных&quot;&quot;&quot;<br>
        q = np.zeros(self.total_variables_by_tag(tag))<br>
        index_map = self.index_map_by_tag(tag)<br>
        for var in self.variables:<br>
            if var.tag == tag:<br>
                indices = index_map[var]<br>
                q[indices] = var.value  # текущее значение<br>
        return q<br>
<br>
    def upload_variables(self, tag: str, values: np.ndarray):<br>
        &quot;&quot;&quot;Загрузить значения переменных с заданным тегом обратно в переменные&quot;&quot;&quot;<br>
        index_map = self.index_map_by_tag(tag)<br>
        count = 0<br>
        for var in self.variables:<br>
            if var.tag == tag:<br>
                indices = index_map[var]<br>
                var.set_value(values[indices])<br>
                count += var.size<br>
        if count != len(values):<br>
            raise ValueError(&quot;Количество загруженных значений не соответствует количеству переменных с заданным тегом&quot;)<br>
<br>
    def upload_solution(self, variables: List[Variable], values: np.ndarray):<br>
        &quot;&quot;&quot;Загрузить значения обратно в переменные по списку Variable&quot;&quot;&quot;<br>
        index = 0<br>
        for var in variables:<br>
            size = var.size<br>
            var.set_value(values[index:index + size])<br>
            index += size<br>
        if index != len(values):<br>
            raise ValueError(&quot;Количество загруженных значений не соответствует количеству переменных&quot;)<br>
<br>
    def integrate_with_constraint_projection(self, <br>
                q_ddot: np.ndarray, matrices: Dict[str, np.ndarray]):<br>
        dt = self.time_step<br>
<br>
        self.upload_variables(&quot;acceleration&quot;, q_ddot)<br>
<br>
        for contribution in self.contributions:<br>
            contribution.finish_timestep(dt)<br>
<br>
        q_dot = self.collect_variables(&quot;velocity&quot;)<br>
<br>
        for _ in range(2):  # несколько итераций проекции положений<br>
            q = self.collect_variables(&quot;position&quot;)<br>
            matrices = self.assemble_for_constraints_correction()<br>
            q = self.coords_project_onto_constraints(q, matrices)<br>
            self.upload_variables(&quot;position&quot;, q)<br>
            for contribution in self.contributions:<br>
                if hasattr(contribution, &quot;finish_correction_step&quot;):<br>
                    contribution.finish_correction_step()<br>
        <br>
        matrices = self.assemble_for_constraints_correction()<br>
        q_dot = self.velocity_project_onto_constraints(q_dot, matrices)   <br>
        self.upload_variables(&quot;velocity&quot;, q_dot)<br>
<br>
        return q_dot, q<br>
<br>
    def sort_results(self, x_ext: np.ndarray) -&gt; Tuple[np.ndarray, np.ndarray, np.ndarray]:<br>
        &quot;&quot;&quot;Разделить расширенное решение на ускорения и множители Лагранжа&quot;&quot;&quot;<br>
        n_dofs = self.total_variables_by_tag(tag=&quot;acceleration&quot;)<br>
        n_holonomic = self.total_variables_by_tag(tag=&quot;force&quot;)<br>
<br>
        q_ddot = x_ext[:n_dofs]<br>
        holonomic_lambdas = x_ext[n_dofs:n_dofs + n_holonomic]<br>
<br>
        nonholonomic_lambdas = []<br>
<br>
        return q_ddot, holonomic_lambdas, nonholonomic_lambdas<br>
<br>
    def integrate_velocities(self, old_q_dot: np.ndarray, q_ddot: np.ndarray) -&gt; np.ndarray:<br>
        &quot;&quot;&quot;Интегрировать ускорения для получения новых скоростей&quot;&quot;&quot;<br>
        return old_q_dot + q_ddot * self.time_step<br>
<br>
    def restore_velocity_constraints(self, q_dot: np.ndarray, HN: np.ndarray, hn: np.ndarray) -&gt; np.ndarray:<br>
        &quot;&quot;&quot;Восстановить ограничения на скорости (например, для закрепленных тел)<br>
<br>
            HN - матрица ограничений на скорости, объединение H и N<br>
        &quot;&quot;&quot;<br>
        return project_onto_affine(q_dot, HN, hn)<br>
<br>
    def integrate_positions(self, old_q: np.ndarray, q_dot: np.ndarray, q_ddot: np.ndarray) -&gt; np.ndarray:<br>
        &quot;&quot;&quot;Интегрировать скорости для получения новых положений&quot;&quot;&quot;<br>
        return old_q + q_dot * self.time_step + 0.5 * q_ddot * self.time_step**2<br>
<br>
    # def restore_position_constraints(self, q: np.ndarray, H: np.ndarray, h: np.ndarray) -&gt; np.ndarray:<br>
    #     &quot;&quot;&quot;Восстановить ограничения на положения (например, для закрепленных тел)&quot;&quot;&quot;<br>
    #     return project_onto_affine(q, H, h)<br>
<br>
    def upload_results(self, q_ddot: np.ndarray, q_dot: np.ndarray, q: np.ndarray):<br>
        &quot;&quot;&quot;Загрузить результаты обратно в переменные&quot;&quot;&quot;<br>
        index_map = self.index_maps()[&quot;acceleration&quot;]<br>
        for var in self.variables:<br>
            if var.tag == &quot;acceleration&quot;:<br>
                indices = index_map[var]<br>
                var.set_values(q_ddot[indices], q_dot[indices], q[indices])<br>
<br>
    def upload_result_values(self, q: np.ndarray):<br>
        &quot;&quot;&quot;Загрузить только положения обратно в переменные&quot;&quot;&quot;<br>
        index_map = self.index_maps()[&quot;acceleration&quot;]<br>
        for var in self.variables:<br>
            if var.tag == &quot;acceleration&quot;:<br>
                indices = index_map[var]<br>
                var.set_value(q[indices])<br>
<br>
    def integrate_nonlinear(self):<br>
        &quot;&quot;&quot;Интегрировать нелинейные переменные (если есть)&quot;&quot;&quot;<br>
        index_map = self.index_maps()[&quot;acceleration&quot;]<br>
        for var in self.variables:<br>
            if var.tag == &quot;acceleration&quot;:<br>
                var.integrate_nonlinear(self.time_step)<br>
<!-- END SCAT CODE -->
</body>
</html>
