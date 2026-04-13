

from termin.solver import qpc_solver_indexes_array
from termin.ga201 import Screw2
from termin.physics.frame import MultiFrame

class World:
    def __init__(self):
        self.bodies = []
        self._force_links = []
        self._iteration_counter = 0
        self._gravity = Screw2(v=[0, -1])
        self._last_solution = None
        self._control_links = []
        self._control_task_frames = []
        self._control_multiframe = MultiFrame()
        self._time = 0
        self._correction_enabled = True

    def time(self):
        return self._time

    def set_correction_enabled(self, enabled):
        self._correction_enabled = enabled

    def last_solution(self):
        return self._last_solution

    def add_link_force(self, force_link):
        self.add_link(force_link)

    def add_link(self, link):
        self._force_links.append(link)

    def add_control_link(self, link):
        self._control_links.append(link)
        self._control_multiframe.add_frame(link)

    def kernel_operator(self, frame):
        return self._control_multiframe.kernel_operator_by_frame(frame)

    def outkernel_operator(self, frame):
        return self._control_multiframe.outkernel_operator_by_frame(frame)


    def add_control_task_frame(self, frame):
        self._control_task_frames.append(frame)
    
    def gravity(self):
        return self._gravity

    def set_gravity(self, gravity):
        self._gravity = gravity

    def add_body(self, body):
        self.bodies.append(body)
        body.bind_world(self)

    def integrate(self, delta):
        for body in self.bodies:
            body.integrate(delta)

    def C_matrix_list(self):
        arr = []
        for body in self.bodies:
            arr.extend(body.forces_in_right_part())

        for force_link in self._force_links:
            arr.extend(force_link.C_matrix_list())
        return arr

    def B_matrix_list(self):
        arr = []
        for force_link in self._force_links:
            arr.extend(force_link.B_matrix_list())
        return arr

    def H_matrix_list(self):
        arr = []
        for control_link in self._control_links:
            arr.extend(control_link.H_matrix_list())
        return arr


    def D_matrix_list(self):
        arr = []
        for force_link in self._force_links:
            arr.extend(force_link.D_matrix_list())
        return arr

    def D_matrix_list_velocity(self):
        arr = []
        for force_link in self._force_links:
            arr.extend(force_link.D_matrix_list_velocity())
        return arr

    def D_matrix_list_position(self):
        arr = []
        for force_link in self._force_links:
            arr.extend(force_link.D_matrix_list_position())
        return arr

    def Ksi_matrix_list(self, delta):
        arr2 = []
        for control_frame in self._control_task_frames:
            arr2.extend(control_frame.Ksi_matrix_list(
                delta, self._control_links))
        for force_link in self._control_links:
            arr2.extend(force_link.Ksi_matrix_list(delta, self._control_links))
        return arr2


    def A_matrix_list(self):
        arr = []
        for body in self.bodies:
            matrix = body.main_matrix()
            if matrix.lidxs != matrix.ridxs:
                raise Exception("Matrix is not square by indexes")
            arr.append(matrix)
        return arr

    def iteration(self, delta):
        A_list = self.A_matrix_list()
        B_list = self.B_matrix_list()
        C_list = self.C_matrix_list()
        D_list = self.D_matrix_list()
        H_list = self.H_matrix_list()
        Ksi_list = self.Ksi_matrix_list(delta)

        x, l, ksi, Q, b = qpc_solver_indexes_array(
            A_list, C_list, B_list, D_list, H_list, Ksi_list)
        x.upbind_values()

        self.last_Q = Q
        self.last_b = b
        self._last_solution = (x, l, ksi)

        if self._iteration_counter == 0:
            print("Equation shape is:")
            print("Q:", self.last_Q.shape)
            print("Count of equation parts:")
            print("A:", len(A_list))
            print("B:", len(B_list))
            print("C:", len(C_list))
            print("D:", len(D_list))
            print("H:", len(H_list))
            print("Ksi:", len(Ksi_list))

        for body in self.bodies:
            body.downbind_solution()
            body.integrate(delta)

        self._iteration_counter += 1

        A_list = self.A_matrix_list()
        B_list = self.B_matrix_list()
        D_list_vel = self.D_matrix_list_velocity()
        D_list_pos = self.D_matrix_list_position()

        if self._correction_enabled:
            self.velocity_correction(A_list, B_list, D_list_vel)
            self.position_correction(A_list, B_list, D_list_pos)

        self._time += delta

    def velocity_correction(self, A_list, B_list, D_list):
        x, l, _, Q, b = qpc_solver_indexes_array(
            A_list, [], B_list, D_list)
        x.upbind_values()

        for body in self.bodies:
            body.downbind_velocity_solution()
            body.velocity_correction()

    def position_correction(self, A_list, B_list, D_list):
        x, l, _, Q, b = qpc_solver_indexes_array(
            A_list, [], B_list, D_list)
        x.upbind_values()

        for body in self.bodies:
            body.downbind_position_solution()
            body.position_correction()


    def iteration_counter(self):
        return self._iteration_counter

#    def correction(self):
#        for force_link in self._force_links:
#            force_link.velocity_correction()