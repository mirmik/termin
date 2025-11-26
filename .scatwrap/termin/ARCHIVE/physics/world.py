<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/ARCHIVE/physics/world.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
<br>
<br>
from termin.solver import qpc_solver_indexes_array<br>
from termin.ga201 import Screw2<br>
from termin.physics.frame import MultiFrame<br>
<br>
class World:<br>
    def __init__(self):<br>
        self.bodies = []<br>
        self._force_links = []<br>
        self._iteration_counter = 0<br>
        self._gravity = Screw2(v=[0, -1])<br>
        self._last_solution = None<br>
        self._control_links = []<br>
        self._control_task_frames = []<br>
        self._control_multiframe = MultiFrame()<br>
        self._time = 0<br>
        self._correction_enabled = True<br>
<br>
    def time(self):<br>
        return self._time<br>
<br>
    def set_correction_enabled(self, enabled):<br>
        self._correction_enabled = enabled<br>
<br>
    def last_solution(self):<br>
        return self._last_solution<br>
<br>
    def add_link_force(self, force_link):<br>
        self.add_link(force_link)<br>
<br>
    def add_link(self, link):<br>
        self._force_links.append(link)<br>
<br>
    def add_control_link(self, link):<br>
        self._control_links.append(link)<br>
        self._control_multiframe.add_frame(link)<br>
<br>
    def kernel_operator(self, frame):<br>
        return self._control_multiframe.kernel_operator_by_frame(frame)<br>
<br>
    def outkernel_operator(self, frame):<br>
        return self._control_multiframe.outkernel_operator_by_frame(frame)<br>
<br>
<br>
    def add_control_task_frame(self, frame):<br>
        self._control_task_frames.append(frame)<br>
    <br>
    def gravity(self):<br>
        return self._gravity<br>
<br>
    def set_gravity(self, gravity):<br>
        self._gravity = gravity<br>
<br>
    def add_body(self, body):<br>
        self.bodies.append(body)<br>
        body.bind_world(self)<br>
<br>
    def integrate(self, delta):<br>
        for body in self.bodies:<br>
            body.integrate(delta)<br>
<br>
    def C_matrix_list(self):<br>
        arr = []<br>
        for body in self.bodies:<br>
            arr.extend(body.forces_in_right_part())<br>
<br>
        for force_link in self._force_links:<br>
            arr.extend(force_link.C_matrix_list())<br>
        return arr<br>
<br>
    def B_matrix_list(self):<br>
        arr = []<br>
        for force_link in self._force_links:<br>
            arr.extend(force_link.B_matrix_list())<br>
        return arr<br>
<br>
    def H_matrix_list(self):<br>
        arr = []<br>
        for control_link in self._control_links:<br>
            arr.extend(control_link.H_matrix_list())<br>
        return arr<br>
<br>
<br>
    def D_matrix_list(self):<br>
        arr = []<br>
        for force_link in self._force_links:<br>
            arr.extend(force_link.D_matrix_list())<br>
        return arr<br>
<br>
    def D_matrix_list_velocity(self):<br>
        arr = []<br>
        for force_link in self._force_links:<br>
            arr.extend(force_link.D_matrix_list_velocity())<br>
        return arr<br>
<br>
    def D_matrix_list_position(self):<br>
        arr = []<br>
        for force_link in self._force_links:<br>
            arr.extend(force_link.D_matrix_list_position())<br>
        return arr<br>
<br>
    def Ksi_matrix_list(self, delta):<br>
        arr2 = []<br>
        for control_frame in self._control_task_frames:<br>
            arr2.extend(control_frame.Ksi_matrix_list(<br>
                delta, self._control_links))<br>
        for force_link in self._control_links:<br>
            arr2.extend(force_link.Ksi_matrix_list(delta, self._control_links))<br>
        return arr2<br>
<br>
<br>
    def A_matrix_list(self):<br>
        arr = []<br>
        for body in self.bodies:<br>
            matrix = body.main_matrix()<br>
            if matrix.lidxs != matrix.ridxs:<br>
                raise Exception(&quot;Matrix is not square by indexes&quot;)<br>
            arr.append(matrix)<br>
        return arr<br>
<br>
    def iteration(self, delta):<br>
        A_list = self.A_matrix_list()<br>
        B_list = self.B_matrix_list()<br>
        C_list = self.C_matrix_list()<br>
        D_list = self.D_matrix_list()<br>
        H_list = self.H_matrix_list()<br>
        Ksi_list = self.Ksi_matrix_list(delta)<br>
<br>
        x, l, ksi, Q, b = qpc_solver_indexes_array(<br>
            A_list, C_list, B_list, D_list, H_list, Ksi_list)<br>
        x.upbind_values()<br>
<br>
        self.last_Q = Q<br>
        self.last_b = b<br>
        self._last_solution = (x, l, ksi)<br>
<br>
        if self._iteration_counter == 0:<br>
            print(&quot;Equation shape is:&quot;)<br>
            print(&quot;Q:&quot;, self.last_Q.shape)<br>
            print(&quot;Count of equation parts:&quot;)<br>
            print(&quot;A:&quot;, len(A_list))<br>
            print(&quot;B:&quot;, len(B_list))<br>
            print(&quot;C:&quot;, len(C_list))<br>
            print(&quot;D:&quot;, len(D_list))<br>
            print(&quot;H:&quot;, len(H_list))<br>
            print(&quot;Ksi:&quot;, len(Ksi_list))<br>
<br>
        for body in self.bodies:<br>
            body.downbind_solution()<br>
            body.integrate(delta)<br>
<br>
        self._iteration_counter += 1<br>
<br>
        A_list = self.A_matrix_list()<br>
        B_list = self.B_matrix_list()<br>
        D_list_vel = self.D_matrix_list_velocity()<br>
        D_list_pos = self.D_matrix_list_position()<br>
<br>
        if self._correction_enabled:<br>
            self.velocity_correction(A_list, B_list, D_list_vel)<br>
            self.position_correction(A_list, B_list, D_list_pos)<br>
<br>
        self._time += delta<br>
<br>
    def velocity_correction(self, A_list, B_list, D_list):<br>
        x, l, _, Q, b = qpc_solver_indexes_array(<br>
            A_list, [], B_list, D_list)<br>
        x.upbind_values()<br>
<br>
        for body in self.bodies:<br>
            body.downbind_velocity_solution()<br>
            body.velocity_correction()<br>
<br>
    def position_correction(self, A_list, B_list, D_list):<br>
        x, l, _, Q, b = qpc_solver_indexes_array(<br>
            A_list, [], B_list, D_list)<br>
        x.upbind_values()<br>
<br>
        for body in self.bodies:<br>
            body.downbind_position_solution()<br>
            body.position_correction()<br>
<br>
<br>
    def iteration_counter(self):<br>
        return self._iteration_counter<br>
<br>
#    def correction(self):<br>
#        for force_link in self._force_links:<br>
#            force_link.velocity_correction()<br>
<!-- END SCAT CODE -->
</body>
</html>
