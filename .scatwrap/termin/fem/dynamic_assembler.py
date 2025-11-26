<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/dynamic_assembler.py</title>
</head>
<body>
<pre><code>
from termin.fem.assembler import MatrixAssembler, Variable, Contribution
from typing import Dict, List, Tuple
import numpy as np
from termin.linalg.subspaces import project_onto_affine, metric_project_onto_constraints 
from termin.geombase.pose3 import Pose3

class DynamicMatrixAssembler(MatrixAssembler):
    def __init__(self):
        super().__init__()
        self.time_step = 0.01

    def _build_index_maps(self) -&gt; Dict[Variable, List[int]]:
        &quot;&quot;&quot;
        Построить отображение: Variable -&gt; глобальные индексы DOF
        
        Назначает каждой компоненте каждой переменной уникальный
        глобальный индекс в системе.
        &quot;&quot;&quot;
        self._index_map_by_tags = {}
        tags = set(var.tag for var in self.variables)

        for tag in tags:
            vars_with_tag = [var for var in self.variables if var.tag == tag]
            index_map = self._build_index_map(vars_with_tag)
            self._index_map_by_tags[tag] = index_map

        self._index_map = self._index_map_by_tags.get(&quot;acceleration&quot;, {})
        self._holonomic_index_map = self._index_map_by_tags.get(&quot;force&quot;, {})

        self._dirty_index_map = False

    # def collect_current_q(self, index_map: Dict[Variable, List[int]]):
    #     &quot;&quot;&quot;Собрать текущее значение q из всех переменных&quot;&quot;&quot;
    #     old_q = np.zeros(self.total_variables_by_tag(&quot;acceleration&quot;))
    #     for var in self.variables:
    #         if var.tag == &quot;acceleration&quot;:
    #             indices = index_map[var]
    #             old_q[indices] = var.value_by_rank(2)  # текущее значение
    #     return old_q

    # def collect_current_q_dot(self, index_map: Dict[Variable, List[int]]):
    #     &quot;&quot;&quot;Собрать текущее значение q_dot из всех переменных&quot;&quot;&quot;
    #     old_q_dot = np.zeros(self.total_variables_by_tag(&quot;acceleration&quot;))
    #     for var in self.variables:
    #         if var.tag == &quot;acceleration&quot;:
    #             indices = index_map[var]
    #             old_q_dot[indices] = var.value_by_rank(1)  # текущее значение скорости
    #     return old_q_dot

    # def set_old_q(self, q: np.ndarray):
    #     &quot;&quot;&quot;Установить старое значение q&quot;&quot;&quot;
    #     self.old_q = np.array(q)

    # def set_old_q_dot(self, q_dot: np.ndarray):
    #     &quot;&quot;&quot;Установить старое значение q_dot&quot;&quot;&quot;
    #     self.old_q_dot = np.array(q_dot)

    def index_maps(self) -&gt; Dict[str, Dict[Variable, List[int]]]:
        &quot;&quot;&quot;
        Получить текущее отображение Variable -&gt; глобальные индексы DOF
        для разных типов переменных
        &quot;&quot;&quot;
        if self._dirty_index_map:
            self._build_index_maps()
        return {
            &quot;acceleration&quot;: self._index_map,
            &quot;force&quot;: self._holonomic_index_map
        }

    def index_map_by_tag(self, tag: str) -&gt; Dict[Variable, List[int]]:
        &quot;&quot;&quot;
        Получить текущее отображение Variable -&gt; глобальные индексы DOF
        для переменных с заданным тегом
        &quot;&quot;&quot;
        if self._dirty_index_map:
            self._build_index_maps()
        return self._index_map_by_tags.get(tag, {})

    def assemble_electric_domain(self):
        # Построить карту индексов
        index_maps = {
            &quot;voltage&quot;: self.index_map_by_tag(&quot;voltage&quot;),
            &quot;current&quot;: self.index_map_by_tag(&quot;current&quot;),
            #&quot;charge&quot;: self.index_map_by_tag(&quot;charge&quot;),
        }

        # Создать глобальные матрицы и вектор
        n_voltage = self.total_variables_by_tag(tag=&quot;voltage&quot;)
        n_currents = self.total_variables_by_tag(tag=&quot;current&quot;)
        #n_charge = self.total_variables_by_tag(tag=&quot;charge&quot;)

        matrices = {
            &quot;conductance&quot;: np.zeros((n_voltage, n_voltage)),
            &quot;electric_holonomic&quot;: np.zeros((n_currents, n_voltage)),
            &quot;electric_holonomic_rhs&quot;: np.zeros(n_currents),
            &quot;rhs&quot;: np.zeros(n_voltage),
            &quot;current_to_current&quot;: np.zeros((n_currents, n_currents)),
            #&quot;charge_constraint&quot;: np.zeros((n_charge, n_voltage)),
            #&quot;charge_constraint_rhs&quot;: np.zeros((n_charge)),
        }

        for contribution in self.contributions:
            contribution.contribute(matrices, index_maps)

        return matrices

    def assemble_electromechanic_domain(self):
        # Построить карту индексов
        index_maps = {
            &quot;voltage&quot;: self.index_map_by_tag(&quot;voltage&quot;),
            &quot;current&quot;: self.index_map_by_tag(&quot;current&quot;),
            &quot;acceleration&quot;: self.index_map_by_tag(&quot;acceleration&quot;),
            &quot;force&quot;: self.index_map_by_tag(&quot;force&quot;),
        }

        # Создать глобальные матрицы и вектор
        n_voltage = self.total_variables_by_tag(tag=&quot;voltage&quot;)
        n_currents = self.total_variables_by_tag(tag=&quot;current&quot;)
        n_acceleration = self.total_variables_by_tag(tag=&quot;acceleration&quot;)
        n_force = self.total_variables_by_tag(tag=&quot;force&quot;)

        matrices = {
            &quot;conductance&quot;: np.zeros((n_voltage, n_voltage)),
            &quot;mass&quot;: np.zeros((n_acceleration, n_acceleration)),
            &quot;load&quot; : np.zeros(n_acceleration),
            &quot;electric_holonomic&quot;: np.zeros((n_currents, n_voltage)),
            &quot;electric_holonomic_rhs&quot;: np.zeros(n_currents),
            &quot;current_to_current&quot;: np.zeros((n_currents, n_currents)),
            &quot;holonomic&quot;: np.zeros((n_force, n_acceleration)),
            &quot;electromechanic_coupling&quot;: np.zeros((n_acceleration, n_currents)),
            &quot;electromechanic_coupling_damping&quot;: np.zeros((n_acceleration, n_currents)),
            &quot;holonomic_load&quot;: np.zeros(n_force),
            &quot;rhs&quot;: np.zeros(n_voltage),
        }

        for contribution in self.contributions:
            contribution.contribute(matrices, index_maps)

        return matrices

    def names_from_variables(self, variables: List[Variable]) -&gt; List[str]:
        &quot;&quot;&quot;Получить список имен переменных из списка Variable&quot;&quot;&quot;
        names = []
        for var in variables:
            names.extend(var.names())
        return names

    def assemble_extended_system_for_electromechanic(self, matrices: Dict[str, np.ndarray]) -&gt; Tuple[np.ndarray, np.ndarray]:
        n_voltage = self.total_variables_by_tag(tag=&quot;voltage&quot;)
        n_currents = self.total_variables_by_tag(tag=&quot;current&quot;)
        n_acceleration = self.total_variables_by_tag(tag=&quot;acceleration&quot;)
        n_force = self.total_variables_by_tag(tag=&quot;force&quot;)

        A_ext = np.zeros((n_voltage + n_currents + n_acceleration + n_force,
                          n_voltage + n_currents + n_acceleration + n_force))

        С_ext = np.zeros((n_voltage + n_currents + n_acceleration + n_force,
                          n_voltage + n_currents + n_acceleration + n_force))
        

        b_ext = np.zeros(n_voltage + n_currents + n_acceleration + n_force)
        variables = (
            list(self.index_map_by_tag(&quot;voltage&quot;).keys()) +
            list(self.index_map_by_tag(&quot;current&quot;).keys()) +
            list(self.index_map_by_tag(&quot;acceleration&quot;).keys()) +
            list(self.index_map_by_tag(&quot;force&quot;).keys())
        )
        variables = self.names_from_variables(variables)

        r0 = n_voltage
        r1 = n_voltage + n_currents
        r2 = n_voltage + n_currents + n_acceleration
        r3 = n_voltage + n_currents + n_acceleration + n_force

        #v = [0:r0]
        #c = [r0:r1]
        #a = [r1:r2]
        #f = [r2:r3]
        print(r0, r1, r2, r3)
        print(matrices[&quot;electromechanic_coupling&quot;].shape)

        A_ext[0:r0, 0:r0] = matrices[&quot;conductance&quot;]
        A_ext[r0:r1, 0:r0] = matrices[&quot;electric_holonomic&quot;]
        A_ext[0:r0, r0:r1] = matrices[&quot;electric_holonomic&quot;].T
        A_ext[r0:r1, r0:r1] = matrices[&quot;current_to_current&quot;]

        A_ext[r1:r2, r1:r2] = matrices[&quot;mass&quot;]        
        A_ext[r2:r3, r1:r2] = matrices[&quot;holonomic&quot;]
        A_ext[r1:r2, r2:r3] = matrices[&quot;holonomic&quot;].T

        A_ext[r1:r2, r0:r1] = matrices[&quot;electromechanic_coupling&quot;]
        #A_ext[r0:r1, r1:r2] = matrices[&quot;electromechanic_coupling&quot;].T

        b_ext[0:r0] = matrices[&quot;rhs&quot;]
        b_ext[r0:r1] = matrices[&quot;electric_holonomic_rhs&quot;]
        b_ext[r1:r2] = matrices[&quot;load&quot;]
        b_ext[r2:r3] = matrices[&quot;holonomic_load&quot;]

        EM_damping = matrices[&quot;electromechanic_coupling_damping&quot;]
        q_dot = self.collect_variables(&quot;velocity&quot;)
        b_em = EM_damping @ q_dot
        b_ext[r0:r1] += b_em

        return A_ext, b_ext, variables

    def assemble_extended_system_for_electric(self, matrices: Dict[str, np.ndarray]) -&gt; Tuple[np.ndarray, np.ndarray]:
        n_voltage = self.total_variables_by_tag(tag=&quot;voltage&quot;)
        n_currents = self.total_variables_by_tag(tag=&quot;current&quot;)

        A_ext = np.zeros((n_voltage + n_currents, n_voltage + n_currents))
        b_ext = np.zeros(n_voltage + n_currents)
        variables = (
            list(self.index_map_by_tag(&quot;voltage&quot;).keys()) +
            list(self.index_map_by_tag(&quot;current&quot;).keys()))
        variables = [var for var in variables]

        r0 = n_voltage
        r1 = n_voltage + n_currents
        c0 = n_voltage
        c1 = n_voltage + n_currents

        A_ext[0:r0, 0:c0] = matrices[&quot;conductance&quot;]
        A_ext[r0:r1, 0:c0] = matrices[&quot;electric_holonomic&quot;]
        A_ext[0:r0, c0:c1] = matrices[&quot;electric_holonomic&quot;].T
        A_ext[c0:c1, c0:c1] = matrices[&quot;current_to_current&quot;]

        b_ext[0:r0] = matrices[&quot;rhs&quot;]
        b_ext[r0:r1] = matrices[&quot;electric_holonomic_rhs&quot;]

        return A_ext, b_ext, variables 

    def assemble(self):
        # Построить карту индексов
        index_maps = self.index_maps()

        # Создать глобальные матрицы и вектор
        n_dofs = self.total_variables_by_tag(tag=&quot;acceleration&quot;)
        n_positions = self.total_variables_by_tag(tag=&quot;position&quot;)
        n_constraints = self.total_variables_by_tag(tag=&quot;force&quot;)

        matrices = {
            &quot;mass&quot;: np.zeros((n_dofs, n_dofs)),
            &quot;damping&quot;: np.zeros((n_dofs, n_dofs)),
            &quot;stiffness&quot;: np.zeros((n_dofs, n_positions)),
            &quot;load&quot;: np.zeros(n_dofs),
            &quot;holonomic&quot;: np.zeros((n_constraints, n_dofs)),
            &quot;holonomic_rhs&quot;: np.zeros(n_constraints),
            #&quot;old_q&quot;: self.collect_variables(index_maps[&quot;acceleration&quot;]),
            #&quot;old_q_dot&quot;: self.collect_current_q_dot(index_maps[&quot;acceleration&quot;]),
            #&quot;holonomic_velocity_rhs&quot;: np.zeros(n_constraints),
        }

        for contribution in self.contributions:
            contribution.contribute(matrices, index_maps)

        return matrices

    def assemble_for_constraints_correction(self):
        # Построить карту индексов
        index_maps = self.index_maps()

        # Создать глобальные матрицы и вектор
        n_dofs = self.total_variables_by_tag(tag=&quot;acceleration&quot;)
        n_constraints = self.total_variables_by_tag(tag=&quot;force&quot;)

        matrices = {
            &quot;mass&quot;: np.zeros((n_dofs, n_dofs)),
            &quot;holonomic&quot;: np.zeros((n_constraints, n_dofs)),
            &quot;position_error&quot;: np.zeros(n_constraints),
            &quot;holonomic_velocity_rhs&quot;: np.zeros(n_constraints),
        }

        for contribution in self.contributions:
            contribution.contribute_for_constraints_correction(matrices, index_maps)

        return matrices

    def assemble_extended_system(self, matrices: Dict[str, np.ndarray]) -&gt; Tuple[np.ndarray, np.ndarray]:
        A = matrices[&quot;mass&quot;]
        C = matrices[&quot;damping&quot;]
        K = matrices[&quot;stiffness&quot;]
        b = matrices[&quot;load&quot;]
        old_q_dot = self.collect_variables(&quot;velocity&quot;)
        old_q = self.collect_variables(&quot;position&quot;)
        H = matrices[&quot;holonomic&quot;]
        h = matrices[&quot;holonomic_rhs&quot;]

        variables = (
            list(self.index_map_by_tag(&quot;acceleration&quot;).keys()) + 
            list(self.index_map_by_tag(&quot;force&quot;).keys()))
        variables = self.names_from_variables(variables)

        size = self.total_variables_by_tag(tag=&quot;acceleration&quot;) + self.total_variables_by_tag(tag=&quot;force&quot;)
        n_dofs = self.total_variables_by_tag(tag=&quot;acceleration&quot;)
        n_holonomic = self.total_variables_by_tag(tag=&quot;force&quot;)

        # Расширенная система
        A_ext = np.zeros((size, size))
        b_ext = np.zeros(size)

        r0 = A.shape[0]
        r1 = A.shape[0] + n_holonomic

        c0 = A.shape[1]
        c1 = A.shape[1] + n_holonomic

        A_ext[0:r0, 0:c0] = A
        A_ext[0:r0, c0:c1] = H.T
        A_ext[r0:r1, 0:c0] = H
        b_ext[0:r0] = b - C @ old_q_dot - K @ old_q
        b_ext[r0:r1] = h

        return A_ext, b_ext, variables

    def velocity_project_onto_constraints(self, q_dot: np.ndarray, matrices: Dict[str, np.ndarray]) -&gt; np.ndarray:
        &quot;&quot;&quot;Проецировать скорости на ограничения&quot;&quot;&quot;
        H = matrices[&quot;holonomic&quot;]
        h = matrices[&quot;holonomic_velocity_rhs&quot;]
        M = matrices[&quot;mass&quot;]
        M_inv = np.linalg.inv(M)
        return metric_project_onto_constraints(q_dot, H, M_inv, h=h)

    def coords_project_onto_constraints(self, q: np.ndarray, matrices: Dict[str, np.ndarray]) -&gt; np.ndarray:
        &quot;&quot;&quot;Проецировать скорости на ограничения&quot;&quot;&quot;
        H = matrices[&quot;holonomic&quot;]
        f = matrices[&quot;position_error&quot;]
        M = matrices[&quot;mass&quot;]
        M_inv = np.linalg.inv(M)
        return metric_project_onto_constraints(q, H, M_inv, error=f)

    def collect_variables(self, tag: str) -&gt; np.ndarray:
        &quot;&quot;&quot;Собрать текущее значение переменных с заданным тегом из всех переменных&quot;&quot;&quot;
        q = np.zeros(self.total_variables_by_tag(tag))
        index_map = self.index_map_by_tag(tag)
        for var in self.variables:
            if var.tag == tag:
                indices = index_map[var]
                q[indices] = var.value  # текущее значение
        return q

    def upload_variables(self, tag: str, values: np.ndarray):
        &quot;&quot;&quot;Загрузить значения переменных с заданным тегом обратно в переменные&quot;&quot;&quot;
        index_map = self.index_map_by_tag(tag)
        count = 0
        for var in self.variables:
            if var.tag == tag:
                indices = index_map[var]
                var.set_value(values[indices])
                count += var.size
        if count != len(values):
            raise ValueError(&quot;Количество загруженных значений не соответствует количеству переменных с заданным тегом&quot;)

    def upload_solution(self, variables: List[Variable], values: np.ndarray):
        &quot;&quot;&quot;Загрузить значения обратно в переменные по списку Variable&quot;&quot;&quot;
        index = 0
        for var in variables:
            size = var.size
            var.set_value(values[index:index + size])
            index += size
        if index != len(values):
            raise ValueError(&quot;Количество загруженных значений не соответствует количеству переменных&quot;)

    def integrate_with_constraint_projection(self, 
                q_ddot: np.ndarray, matrices: Dict[str, np.ndarray]):
        dt = self.time_step

        self.upload_variables(&quot;acceleration&quot;, q_ddot)

        for contribution in self.contributions:
            contribution.finish_timestep(dt)

        q_dot = self.collect_variables(&quot;velocity&quot;)

        for _ in range(2):  # несколько итераций проекции положений
            q = self.collect_variables(&quot;position&quot;)
            matrices = self.assemble_for_constraints_correction()
            q = self.coords_project_onto_constraints(q, matrices)
            self.upload_variables(&quot;position&quot;, q)
            for contribution in self.contributions:
                if hasattr(contribution, &quot;finish_correction_step&quot;):
                    contribution.finish_correction_step()
        
        matrices = self.assemble_for_constraints_correction()
        q_dot = self.velocity_project_onto_constraints(q_dot, matrices)   
        self.upload_variables(&quot;velocity&quot;, q_dot)

        return q_dot, q

    def sort_results(self, x_ext: np.ndarray) -&gt; Tuple[np.ndarray, np.ndarray, np.ndarray]:
        &quot;&quot;&quot;Разделить расширенное решение на ускорения и множители Лагранжа&quot;&quot;&quot;
        n_dofs = self.total_variables_by_tag(tag=&quot;acceleration&quot;)
        n_holonomic = self.total_variables_by_tag(tag=&quot;force&quot;)

        q_ddot = x_ext[:n_dofs]
        holonomic_lambdas = x_ext[n_dofs:n_dofs + n_holonomic]

        nonholonomic_lambdas = []

        return q_ddot, holonomic_lambdas, nonholonomic_lambdas

    def integrate_velocities(self, old_q_dot: np.ndarray, q_ddot: np.ndarray) -&gt; np.ndarray:
        &quot;&quot;&quot;Интегрировать ускорения для получения новых скоростей&quot;&quot;&quot;
        return old_q_dot + q_ddot * self.time_step

    def restore_velocity_constraints(self, q_dot: np.ndarray, HN: np.ndarray, hn: np.ndarray) -&gt; np.ndarray:
        &quot;&quot;&quot;Восстановить ограничения на скорости (например, для закрепленных тел)

            HN - матрица ограничений на скорости, объединение H и N
        &quot;&quot;&quot;
        return project_onto_affine(q_dot, HN, hn)

    def integrate_positions(self, old_q: np.ndarray, q_dot: np.ndarray, q_ddot: np.ndarray) -&gt; np.ndarray:
        &quot;&quot;&quot;Интегрировать скорости для получения новых положений&quot;&quot;&quot;
        return old_q + q_dot * self.time_step + 0.5 * q_ddot * self.time_step**2

    # def restore_position_constraints(self, q: np.ndarray, H: np.ndarray, h: np.ndarray) -&gt; np.ndarray:
    #     &quot;&quot;&quot;Восстановить ограничения на положения (например, для закрепленных тел)&quot;&quot;&quot;
    #     return project_onto_affine(q, H, h)

    def upload_results(self, q_ddot: np.ndarray, q_dot: np.ndarray, q: np.ndarray):
        &quot;&quot;&quot;Загрузить результаты обратно в переменные&quot;&quot;&quot;
        index_map = self.index_maps()[&quot;acceleration&quot;]
        for var in self.variables:
            if var.tag == &quot;acceleration&quot;:
                indices = index_map[var]
                var.set_values(q_ddot[indices], q_dot[indices], q[indices])

    def upload_result_values(self, q: np.ndarray):
        &quot;&quot;&quot;Загрузить только положения обратно в переменные&quot;&quot;&quot;
        index_map = self.index_maps()[&quot;acceleration&quot;]
        for var in self.variables:
            if var.tag == &quot;acceleration&quot;:
                indices = index_map[var]
                var.set_value(q[indices])

    def integrate_nonlinear(self):
        &quot;&quot;&quot;Интегрировать нелинейные переменные (если есть)&quot;&quot;&quot;
        index_map = self.index_maps()[&quot;acceleration&quot;]
        for var in self.variables:
            if var.tag == &quot;acceleration&quot;:
                var.integrate_nonlinear(self.time_step)

</code></pre>
</body>
</html>
