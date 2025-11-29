from termin.fem.assembler import MatrixAssembler, Variable, Contribution
from typing import Dict, List, Tuple
import numpy as np
from termin.linalg.subspaces import project_onto_affine, metric_project_onto_constraints 
from termin.geombase.pose3 import Pose3

class DynamicMatrixAssembler(MatrixAssembler):
    def __init__(self):
        super().__init__()
        self.time_step = 0.01

    def _build_index_maps(self) -> Dict[Variable, List[int]]:
        """
        Построить отображение: Variable -> глобальные индексы DOF
        
        Назначает каждой компоненте каждой переменной уникальный
        глобальный индекс в системе.
        """
        self._index_map_by_tags = {}
        tags = set(var.tag for var in self.variables)

        for tag in tags:
            vars_with_tag = [var for var in self.variables if var.tag == tag]
            index_map = self._build_index_map(vars_with_tag)
            self._index_map_by_tags[tag] = index_map

        self._index_map = self._index_map_by_tags.get("acceleration", {})
        self._holonomic_index_map = self._index_map_by_tags.get("force", {})

        self._dirty_index_map = False

    # def collect_current_q(self, index_map: Dict[Variable, List[int]]):
    #     """Собрать текущее значение q из всех переменных"""
    #     old_q = np.zeros(self.total_variables_by_tag("acceleration"))
    #     for var in self.variables:
    #         if var.tag == "acceleration":
    #             indices = index_map[var]
    #             old_q[indices] = var.value_by_rank(2)  # текущее значение
    #     return old_q

    # def collect_current_q_dot(self, index_map: Dict[Variable, List[int]]):
    #     """Собрать текущее значение q_dot из всех переменных"""
    #     old_q_dot = np.zeros(self.total_variables_by_tag("acceleration"))
    #     for var in self.variables:
    #         if var.tag == "acceleration":
    #             indices = index_map[var]
    #             old_q_dot[indices] = var.value_by_rank(1)  # текущее значение скорости
    #     return old_q_dot

    # def set_old_q(self, q: np.ndarray):
    #     """Установить старое значение q"""
    #     self.old_q = np.array(q)

    # def set_old_q_dot(self, q_dot: np.ndarray):
    #     """Установить старое значение q_dot"""
    #     self.old_q_dot = np.array(q_dot)

    def index_maps(self) -> Dict[str, Dict[Variable, List[int]]]:
        """
        Получить текущее отображение Variable -> глобальные индексы DOF
        для разных типов переменных
        """
        if self._dirty_index_map:
            self._build_index_maps()
        return {
            "acceleration": self._index_map,
            "force": self._holonomic_index_map
        }

    def index_map_by_tag(self, tag: str) -> Dict[Variable, List[int]]:
        """
        Получить текущее отображение Variable -> глобальные индексы DOF
        для переменных с заданным тегом
        """
        if self._dirty_index_map:
            self._build_index_maps()
        return self._index_map_by_tags.get(tag, {})

    def assemble_electric_domain(self):
        # Построить карту индексов
        index_maps = {
            "voltage": self.index_map_by_tag("voltage"),
            "current": self.index_map_by_tag("current"),
            #"charge": self.index_map_by_tag("charge"),
        }

        # Создать глобальные матрицы и вектор
        n_voltage = self.total_variables_by_tag(tag="voltage")
        n_currents = self.total_variables_by_tag(tag="current")
        #n_charge = self.total_variables_by_tag(tag="charge")

        matrices = {
            "conductance": np.zeros((n_voltage, n_voltage)),
            "electric_holonomic": np.zeros((n_currents, n_voltage)),
            "electric_holonomic_rhs": np.zeros(n_currents),
            "rhs": np.zeros(n_voltage),
            "current_to_current": np.zeros((n_currents, n_currents)),
            #"charge_constraint": np.zeros((n_charge, n_voltage)),
            #"charge_constraint_rhs": np.zeros((n_charge)),
        }

        for contribution in self.contributions:
            contribution.contribute(matrices, index_maps)

        return matrices

    def assemble_electromechanic_domain(self):
        # Построить карту индексов
        index_maps = {
            "voltage": self.index_map_by_tag("voltage"),
            "current": self.index_map_by_tag("current"),
            "acceleration": self.index_map_by_tag("acceleration"),
            "force": self.index_map_by_tag("force"),
        }

        # Создать глобальные матрицы и вектор
        n_voltage = self.total_variables_by_tag(tag="voltage")
        n_currents = self.total_variables_by_tag(tag="current")
        n_acceleration = self.total_variables_by_tag(tag="acceleration")
        n_force = self.total_variables_by_tag(tag="force")

        matrices = {
            "conductance": np.zeros((n_voltage, n_voltage)),
            "mass": np.zeros((n_acceleration, n_acceleration)),
            "load" : np.zeros(n_acceleration),
            "electric_holonomic": np.zeros((n_currents, n_voltage)),
            "electric_holonomic_rhs": np.zeros(n_currents),
            "current_to_current": np.zeros((n_currents, n_currents)),
            "holonomic": np.zeros((n_force, n_acceleration)),
            "electromechanic_coupling": np.zeros((n_acceleration, n_currents)),
            "electromechanic_coupling_damping": np.zeros((n_acceleration, n_currents)),
            "holonomic_load": np.zeros(n_force),
            "rhs": np.zeros(n_voltage),
        }

        for contribution in self.contributions:
            contribution.contribute(matrices, index_maps)

        return matrices

    def names_from_variables(self, variables: List[Variable]) -> List[str]:
        """Получить список имен переменных из списка Variable"""
        names = []
        for var in variables:
            names.extend(var.names())
        return names

    def assemble_extended_system_for_electromechanic(self, matrices: Dict[str, np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
        n_voltage = self.total_variables_by_tag(tag="voltage")
        n_currents = self.total_variables_by_tag(tag="current")
        n_acceleration = self.total_variables_by_tag(tag="acceleration")
        n_force = self.total_variables_by_tag(tag="force")

        A_ext = np.zeros((n_voltage + n_currents + n_acceleration + n_force,
                          n_voltage + n_currents + n_acceleration + n_force))

        С_ext = np.zeros((n_voltage + n_currents + n_acceleration + n_force,
                          n_voltage + n_currents + n_acceleration + n_force))
        

        b_ext = np.zeros(n_voltage + n_currents + n_acceleration + n_force)
        variables = (
            list(self.index_map_by_tag("voltage").keys()) +
            list(self.index_map_by_tag("current").keys()) +
            list(self.index_map_by_tag("acceleration").keys()) +
            list(self.index_map_by_tag("force").keys())
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
        A_ext[0:r0, 0:r0] = matrices["conductance"]
        A_ext[r0:r1, 0:r0] = matrices["electric_holonomic"]
        A_ext[0:r0, r0:r1] = matrices["electric_holonomic"].T
        A_ext[r0:r1, r0:r1] = matrices["current_to_current"]

        A_ext[r1:r2, r1:r2] = matrices["mass"]        
        A_ext[r2:r3, r1:r2] = matrices["holonomic"]
        A_ext[r1:r2, r2:r3] = matrices["holonomic"].T

        A_ext[r1:r2, r0:r1] = matrices["electromechanic_coupling"]
        #A_ext[r0:r1, r1:r2] = matrices["electromechanic_coupling"].T

        b_ext[0:r0] = matrices["rhs"]
        b_ext[r0:r1] = matrices["electric_holonomic_rhs"]
        b_ext[r1:r2] = matrices["load"]
        b_ext[r2:r3] = matrices["holonomic_load"]

        EM_damping = matrices["electromechanic_coupling_damping"]
        q_dot = self.collect_variables("velocity")
        b_em = EM_damping @ q_dot
        b_ext[r0:r1] += b_em

        return A_ext, b_ext, variables

    def assemble_extended_system_for_electric(self, matrices: Dict[str, np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
        n_voltage = self.total_variables_by_tag(tag="voltage")
        n_currents = self.total_variables_by_tag(tag="current")

        A_ext = np.zeros((n_voltage + n_currents, n_voltage + n_currents))
        b_ext = np.zeros(n_voltage + n_currents)
        variables = (
            list(self.index_map_by_tag("voltage").keys()) +
            list(self.index_map_by_tag("current").keys()))
        variables = [var for var in variables]

        r0 = n_voltage
        r1 = n_voltage + n_currents
        c0 = n_voltage
        c1 = n_voltage + n_currents

        A_ext[0:r0, 0:c0] = matrices["conductance"]
        A_ext[r0:r1, 0:c0] = matrices["electric_holonomic"]
        A_ext[0:r0, c0:c1] = matrices["electric_holonomic"].T
        A_ext[c0:c1, c0:c1] = matrices["current_to_current"]

        b_ext[0:r0] = matrices["rhs"]
        b_ext[r0:r1] = matrices["electric_holonomic_rhs"]

        return A_ext, b_ext, variables 

    def assemble(self):
        # Построить карту индексов
        index_maps = self.index_maps()

        # Создать глобальные матрицы и вектор
        n_dofs = self.total_variables_by_tag(tag="acceleration")
        n_positions = self.total_variables_by_tag(tag="position")
        n_constraints = self.total_variables_by_tag(tag="force")

        matrices = {
            "mass": np.zeros((n_dofs, n_dofs)),
            "damping": np.zeros((n_dofs, n_dofs)),
            "stiffness": np.zeros((n_dofs, n_positions)),
            "load": np.zeros(n_dofs),
            "holonomic": np.zeros((n_constraints, n_dofs)),
            "holonomic_rhs": np.zeros(n_constraints),
            #"old_q": self.collect_variables(index_maps["acceleration"]),
            #"old_q_dot": self.collect_current_q_dot(index_maps["acceleration"]),
            #"holonomic_velocity_rhs": np.zeros(n_constraints),
        }

        for contribution in self.contributions:
            contribution.contribute(matrices, index_maps)

        return matrices

    def assemble_for_constraints_correction(self):
        # Построить карту индексов
        index_maps = self.index_maps()

        # Создать глобальные матрицы и вектор
        n_dofs = self.total_variables_by_tag(tag="acceleration")
        n_constraints = self.total_variables_by_tag(tag="force")

        matrices = {
            "mass": np.zeros((n_dofs, n_dofs)),
            "holonomic": np.zeros((n_constraints, n_dofs)),
            "position_error": np.zeros(n_constraints),
            "holonomic_velocity_rhs": np.zeros(n_constraints),
        }

        for contribution in self.contributions:
            contribution.contribute_for_constraints_correction(matrices, index_maps)

        return matrices

    def assemble_extended_system(self, matrices: Dict[str, np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
        A = matrices["mass"]
        C = matrices["damping"]
        K = matrices["stiffness"]
        b = matrices["load"]
        old_q_dot = self.collect_variables("velocity")
        old_q = self.collect_variables("position")
        H = matrices["holonomic"]
        h = matrices["holonomic_rhs"]

        variables = (
            list(self.index_map_by_tag("acceleration").keys()) + 
            list(self.index_map_by_tag("force").keys()))
        variables = self.names_from_variables(variables)

        size = self.total_variables_by_tag(tag="acceleration") + self.total_variables_by_tag(tag="force")
        n_dofs = self.total_variables_by_tag(tag="acceleration")
        n_holonomic = self.total_variables_by_tag(tag="force")

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

    def velocity_project_onto_constraints(self, q_dot: np.ndarray, matrices: Dict[str, np.ndarray]) -> np.ndarray:
        """Проецировать скорости на ограничения"""
        H = matrices["holonomic"]
        h = matrices["holonomic_velocity_rhs"]
        M = matrices["mass"]
        M_inv = np.linalg.inv(M)
        return metric_project_onto_constraints(q_dot, H, M_inv, h=h)

    def coords_project_onto_constraints(self, q: np.ndarray, matrices: Dict[str, np.ndarray]) -> np.ndarray:
        """Проецировать скорости на ограничения"""
        H = matrices["holonomic"]
        f = matrices["position_error"]
        M = matrices["mass"]
        M_inv = np.linalg.inv(M)
        return metric_project_onto_constraints(q, H, M_inv, error=f)

    def collect_variables(self, tag: str) -> np.ndarray:
        """Собрать текущее значение переменных с заданным тегом из всех переменных"""
        q = np.zeros(self.total_variables_by_tag(tag))
        index_map = self.index_map_by_tag(tag)
        for var in self.variables:
            if var.tag == tag:
                indices = index_map[var]
                q[indices] = var.value  # текущее значение
        return q

    def upload_variables(self, tag: str, values: np.ndarray):
        """Загрузить значения переменных с заданным тегом обратно в переменные"""
        index_map = self.index_map_by_tag(tag)
        count = 0
        for var in self.variables:
            if var.tag == tag:
                indices = index_map[var]
                var.set_value(values[indices])
                count += var.size
        if count != len(values):
            raise ValueError("Количество загруженных значений не соответствует количеству переменных с заданным тегом")

    def upload_solution(self, variables: List[Variable], values: np.ndarray):
        """Загрузить значения обратно в переменные по списку Variable"""
        index = 0
        for var in variables:
            size = var.size
            var.set_value(values[index:index + size])
            index += size
        if index != len(values):
            raise ValueError("Количество загруженных значений не соответствует количеству переменных")

    def integrate_with_constraint_projection(self, 
                q_ddot: np.ndarray, matrices: Dict[str, np.ndarray]):
        dt = self.time_step

        self.upload_variables("acceleration", q_ddot)

        for contribution in self.contributions:
            contribution.finish_timestep(dt)

        q_dot = self.collect_variables("velocity")

        for _ in range(2):  # несколько итераций проекции положений
            q = self.collect_variables("position")
            matrices = self.assemble_for_constraints_correction()
            q = self.coords_project_onto_constraints(q, matrices)
            self.upload_variables("position", q)
            for contribution in self.contributions:
                if hasattr(contribution, "finish_correction_step"):
                    contribution.finish_correction_step()
        
        matrices = self.assemble_for_constraints_correction()
        q_dot = self.velocity_project_onto_constraints(q_dot, matrices)   
        self.upload_variables("velocity", q_dot)

        return q_dot, q

    def sort_results(self, x_ext: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Разделить расширенное решение на ускорения и множители Лагранжа"""
        n_dofs = self.total_variables_by_tag(tag="acceleration")
        n_holonomic = self.total_variables_by_tag(tag="force")

        q_ddot = x_ext[:n_dofs]
        holonomic_lambdas = x_ext[n_dofs:n_dofs + n_holonomic]

        nonholonomic_lambdas = []

        return q_ddot, holonomic_lambdas, nonholonomic_lambdas

    def integrate_velocities(self, old_q_dot: np.ndarray, q_ddot: np.ndarray) -> np.ndarray:
        """Интегрировать ускорения для получения новых скоростей"""
        return old_q_dot + q_ddot * self.time_step

    def restore_velocity_constraints(self, q_dot: np.ndarray, HN: np.ndarray, hn: np.ndarray) -> np.ndarray:
        """Восстановить ограничения на скорости (например, для закрепленных тел)

            HN - матрица ограничений на скорости, объединение H и N
        """
        return project_onto_affine(q_dot, HN, hn)

    def integrate_positions(self, old_q: np.ndarray, q_dot: np.ndarray, q_ddot: np.ndarray) -> np.ndarray:
        """Интегрировать скорости для получения новых положений"""
        return old_q + q_dot * self.time_step + 0.5 * q_ddot * self.time_step**2

    # def restore_position_constraints(self, q: np.ndarray, H: np.ndarray, h: np.ndarray) -> np.ndarray:
    #     """Восстановить ограничения на положения (например, для закрепленных тел)"""
    #     return project_onto_affine(q, H, h)

    def upload_results(self, q_ddot: np.ndarray, q_dot: np.ndarray, q: np.ndarray):
        """Загрузить результаты обратно в переменные"""
        index_map = self.index_maps()["acceleration"]
        for var in self.variables:
            if var.tag == "acceleration":
                indices = index_map[var]
                var.set_values(q_ddot[indices], q_dot[indices], q[indices])

    def upload_result_values(self, q: np.ndarray):
        """Загрузить только положения обратно в переменные"""
        index_map = self.index_maps()["acceleration"]
        for var in self.variables:
            if var.tag == "acceleration":
                indices = index_map[var]
                var.set_value(q[indices])

    def integrate_nonlinear(self):
        """Интегрировать нелинейные переменные (если есть)"""
        index_map = self.index_maps()["acceleration"]
        for var in self.variables:
            if var.tag == "acceleration":
                var.integrate_nonlinear(self.time_step)
