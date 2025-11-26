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
&#9;def __init__(self):<br>
&#9;&#9;self.bodies = []<br>
&#9;&#9;self._force_links = []<br>
&#9;&#9;self._iteration_counter = 0<br>
&#9;&#9;self._gravity = Screw2(v=[0, -1])<br>
&#9;&#9;self._last_solution = None<br>
&#9;&#9;self._control_links = []<br>
&#9;&#9;self._control_task_frames = []<br>
&#9;&#9;self._control_multiframe = MultiFrame()<br>
&#9;&#9;self._time = 0<br>
&#9;&#9;self._correction_enabled = True<br>
<br>
&#9;def time(self):<br>
&#9;&#9;return self._time<br>
<br>
&#9;def set_correction_enabled(self, enabled):<br>
&#9;&#9;self._correction_enabled = enabled<br>
<br>
&#9;def last_solution(self):<br>
&#9;&#9;return self._last_solution<br>
<br>
&#9;def add_link_force(self, force_link):<br>
&#9;&#9;self.add_link(force_link)<br>
<br>
&#9;def add_link(self, link):<br>
&#9;&#9;self._force_links.append(link)<br>
<br>
&#9;def add_control_link(self, link):<br>
&#9;&#9;self._control_links.append(link)<br>
&#9;&#9;self._control_multiframe.add_frame(link)<br>
<br>
&#9;def kernel_operator(self, frame):<br>
&#9;&#9;return self._control_multiframe.kernel_operator_by_frame(frame)<br>
<br>
&#9;def outkernel_operator(self, frame):<br>
&#9;&#9;return self._control_multiframe.outkernel_operator_by_frame(frame)<br>
<br>
<br>
&#9;def add_control_task_frame(self, frame):<br>
&#9;&#9;self._control_task_frames.append(frame)<br>
&#9;<br>
&#9;def gravity(self):<br>
&#9;&#9;return self._gravity<br>
<br>
&#9;def set_gravity(self, gravity):<br>
&#9;&#9;self._gravity = gravity<br>
<br>
&#9;def add_body(self, body):<br>
&#9;&#9;self.bodies.append(body)<br>
&#9;&#9;body.bind_world(self)<br>
<br>
&#9;def integrate(self, delta):<br>
&#9;&#9;for body in self.bodies:<br>
&#9;&#9;&#9;body.integrate(delta)<br>
<br>
&#9;def C_matrix_list(self):<br>
&#9;&#9;arr = []<br>
&#9;&#9;for body in self.bodies:<br>
&#9;&#9;&#9;arr.extend(body.forces_in_right_part())<br>
<br>
&#9;&#9;for force_link in self._force_links:<br>
&#9;&#9;&#9;arr.extend(force_link.C_matrix_list())<br>
&#9;&#9;return arr<br>
<br>
&#9;def B_matrix_list(self):<br>
&#9;&#9;arr = []<br>
&#9;&#9;for force_link in self._force_links:<br>
&#9;&#9;&#9;arr.extend(force_link.B_matrix_list())<br>
&#9;&#9;return arr<br>
<br>
&#9;def H_matrix_list(self):<br>
&#9;&#9;arr = []<br>
&#9;&#9;for control_link in self._control_links:<br>
&#9;&#9;&#9;arr.extend(control_link.H_matrix_list())<br>
&#9;&#9;return arr<br>
<br>
<br>
&#9;def D_matrix_list(self):<br>
&#9;&#9;arr = []<br>
&#9;&#9;for force_link in self._force_links:<br>
&#9;&#9;&#9;arr.extend(force_link.D_matrix_list())<br>
&#9;&#9;return arr<br>
<br>
&#9;def D_matrix_list_velocity(self):<br>
&#9;&#9;arr = []<br>
&#9;&#9;for force_link in self._force_links:<br>
&#9;&#9;&#9;arr.extend(force_link.D_matrix_list_velocity())<br>
&#9;&#9;return arr<br>
<br>
&#9;def D_matrix_list_position(self):<br>
&#9;&#9;arr = []<br>
&#9;&#9;for force_link in self._force_links:<br>
&#9;&#9;&#9;arr.extend(force_link.D_matrix_list_position())<br>
&#9;&#9;return arr<br>
<br>
&#9;def Ksi_matrix_list(self, delta):<br>
&#9;&#9;arr2 = []<br>
&#9;&#9;for control_frame in self._control_task_frames:<br>
&#9;&#9;&#9;arr2.extend(control_frame.Ksi_matrix_list(<br>
&#9;&#9;&#9;&#9;delta, self._control_links))<br>
&#9;&#9;for force_link in self._control_links:<br>
&#9;&#9;&#9;arr2.extend(force_link.Ksi_matrix_list(delta, self._control_links))<br>
&#9;&#9;return arr2<br>
<br>
<br>
&#9;def A_matrix_list(self):<br>
&#9;&#9;arr = []<br>
&#9;&#9;for body in self.bodies:<br>
&#9;&#9;&#9;matrix = body.main_matrix()<br>
&#9;&#9;&#9;if matrix.lidxs != matrix.ridxs:<br>
&#9;&#9;&#9;&#9;raise Exception(&quot;Matrix is not square by indexes&quot;)<br>
&#9;&#9;&#9;arr.append(matrix)<br>
&#9;&#9;return arr<br>
<br>
&#9;def iteration(self, delta):<br>
&#9;&#9;A_list = self.A_matrix_list()<br>
&#9;&#9;B_list = self.B_matrix_list()<br>
&#9;&#9;C_list = self.C_matrix_list()<br>
&#9;&#9;D_list = self.D_matrix_list()<br>
&#9;&#9;H_list = self.H_matrix_list()<br>
&#9;&#9;Ksi_list = self.Ksi_matrix_list(delta)<br>
<br>
&#9;&#9;x, l, ksi, Q, b = qpc_solver_indexes_array(<br>
&#9;&#9;&#9;A_list, C_list, B_list, D_list, H_list, Ksi_list)<br>
&#9;&#9;x.upbind_values()<br>
<br>
&#9;&#9;self.last_Q = Q<br>
&#9;&#9;self.last_b = b<br>
&#9;&#9;self._last_solution = (x, l, ksi)<br>
<br>
&#9;&#9;if self._iteration_counter == 0:<br>
&#9;&#9;&#9;print(&quot;Equation shape is:&quot;)<br>
&#9;&#9;&#9;print(&quot;Q:&quot;, self.last_Q.shape)<br>
&#9;&#9;&#9;print(&quot;Count of equation parts:&quot;)<br>
&#9;&#9;&#9;print(&quot;A:&quot;, len(A_list))<br>
&#9;&#9;&#9;print(&quot;B:&quot;, len(B_list))<br>
&#9;&#9;&#9;print(&quot;C:&quot;, len(C_list))<br>
&#9;&#9;&#9;print(&quot;D:&quot;, len(D_list))<br>
&#9;&#9;&#9;print(&quot;H:&quot;, len(H_list))<br>
&#9;&#9;&#9;print(&quot;Ksi:&quot;, len(Ksi_list))<br>
<br>
&#9;&#9;for body in self.bodies:<br>
&#9;&#9;&#9;body.downbind_solution()<br>
&#9;&#9;&#9;body.integrate(delta)<br>
<br>
&#9;&#9;self._iteration_counter += 1<br>
<br>
&#9;&#9;A_list = self.A_matrix_list()<br>
&#9;&#9;B_list = self.B_matrix_list()<br>
&#9;&#9;D_list_vel = self.D_matrix_list_velocity()<br>
&#9;&#9;D_list_pos = self.D_matrix_list_position()<br>
<br>
&#9;&#9;if self._correction_enabled:<br>
&#9;&#9;&#9;self.velocity_correction(A_list, B_list, D_list_vel)<br>
&#9;&#9;&#9;self.position_correction(A_list, B_list, D_list_pos)<br>
<br>
&#9;&#9;self._time += delta<br>
<br>
&#9;def velocity_correction(self, A_list, B_list, D_list):<br>
&#9;&#9;x, l, _, Q, b = qpc_solver_indexes_array(<br>
&#9;&#9;&#9;A_list, [], B_list, D_list)<br>
&#9;&#9;x.upbind_values()<br>
<br>
&#9;&#9;for body in self.bodies:<br>
&#9;&#9;&#9;body.downbind_velocity_solution()<br>
&#9;&#9;&#9;body.velocity_correction()<br>
<br>
&#9;def position_correction(self, A_list, B_list, D_list):<br>
&#9;&#9;x, l, _, Q, b = qpc_solver_indexes_array(<br>
&#9;&#9;&#9;A_list, [], B_list, D_list)<br>
&#9;&#9;x.upbind_values()<br>
<br>
&#9;&#9;for body in self.bodies:<br>
&#9;&#9;&#9;body.downbind_position_solution()<br>
&#9;&#9;&#9;body.position_correction()<br>
<br>
<br>
&#9;def iteration_counter(self):<br>
&#9;&#9;return self._iteration_counter<br>
<br>
#    def correction(self):<br>
#        for force_link in self._force_links:<br>
#            force_link.velocity_correction()<br>
<!-- END SCAT CODE -->
</body>
</html>
