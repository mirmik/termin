<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/ARCHIVE/physics/body.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#!/usr/bin/env python3<br>
<br>
import numpy<br>
from termin.physics.screw_commutator import VariableValueCommutator<br>
from termin.physics.indexed_matrix import IndexedMatrix, IndexedVector<br>
from termin.physics.pose_object import PoseObject<br>
from termin.physics.screw_commutator import ScrewCommutator<br>
from termin.ga201 import Motor2<br>
from termin.ga201 import Screw2<br>
from termin.physics.frame import Frame<br>
<br>
class Body(Frame):<br>
&#9;def __init__(self, space_dim, dof, screws) -&gt; None:<br>
&#9;&#9;super().__init__(pose_object=PoseObject(), screws=screws)<br>
&#9;&#9;self.space_dim = space_dim<br>
&#9;&#9;self.dof = dof<br>
&#9;&#9;self._right_acceleration_global = Screw2()<br>
&#9;&#9;self._right_velocity_global = Screw2()<br>
&#9;&#9;self._resistance_coefficient = 0<br>
&#9;&#9;self._right_velocity_correction = Screw2()<br>
&#9;&#9;self._right_position_correction = Screw2()<br>
&#9;&#9;self._world = None<br>
<br>
&#9;def bind_world(self, w):<br>
&#9;&#9;self._world = w<br>
<br>
&#9;def set_resistance_coefficient(self, coeff):<br>
&#9;&#9;self._resistance_coefficient = coeff<br>
<br>
&#9;def translation(self):<br>
&#9;&#9;return self.position().factorize_translation_vector()<br>
<br>
&#9;def rotation(self):<br>
&#9;&#9;return self.position().factorize_rotation_angle()<br>
<br>
&#9;def downbind_solution(self):<br>
&#9;&#9;self._right_acceleration_global = Screw2(<br>
&#9;&#9;&#9;m=self._screw_commutator.values()[0],<br>
&#9;&#9;&#9;v=numpy.array(self._screw_commutator.values()[1:])<br>
&#9;&#9;).rotate_by(self.position())<br>
<br>
&#9;def downbind_velocity_solution(self):<br>
&#9;&#9;self._right_velocity_correction = Screw2(<br>
&#9;&#9;&#9;m=self._screw_commutator.values()[0],<br>
&#9;&#9;&#9;v=numpy.array(self._screw_commutator.values()[1:])<br>
&#9;&#9;)<br>
<br>
&#9;def downbind_position_solution(self):<br>
&#9;&#9;self._right_position_correction = Screw2(<br>
&#9;&#9;&#9;m=self._screw_commutator.values()[0],<br>
&#9;&#9;&#9;v=numpy.array(self._screw_commutator.values()[1:])<br>
&#9;&#9;)<br>
<br>
<br>
&#9;# def unbind_force(self, force):<br>
&#9;#     if force.is_right_global() and force.is_linked_to(self):<br>
&#9;#         self._right_forces_global.remove(force)<br>
&#9;#     elif force.is_right() and force.is_linked_to(self):<br>
&#9;#         self._right_forces.remove(force)<br>
&#9;#     else:<br>
&#9;#         raise Exception(&quot;Force is not linked to this body&quot;)<br>
<br>
&#9;#     force.clean_bind_information()<br>
<br>
&#9;# def add_right_force_global(self, force):<br>
&#9;#     self._right_forces_global.append(force)<br>
&#9;#     force.set_right_global_type()<br>
&#9;#     force.set_linked_object(self)<br>
<br>
&#9;# def add_right_force(self, force):<br>
&#9;#     self._right_forces.append(force)<br>
&#9;#     force.set_right_type()<br>
&#9;#     force.set_linked_object(self)<br>
<br>
&#9;def right_acceleration(self):<br>
&#9;&#9;return self._right_acceleration_global.inverse_rotate_by(self.position())<br>
<br>
&#9;def right_acceleration_global(self):<br>
&#9;&#9;return self._right_acceleration_global<br>
<br>
&#9;def right_velocity_global(self):<br>
&#9;&#9;return self._right_velocity_global<br>
&#9;&#9;#return self._right_velocity.rotate_by(self.position())<br>
<br>
&#9;def right_velocity(self):<br>
&#9;&#9;return self._right_velocity_global.inverse_rotate_by(self.position())<br>
&#9;&#9;#return self._right_velocity<br>
<br>
&#9;def set_right_velocity_global(self, vel):<br>
&#9;&#9;self._right_velocity_global = vel<br>
&#9;&#9;#self._right_velocity = vel.inverse_rotate_by(self.position())<br>
<br>
&#9;def set_right_velocity(self, vel):<br>
&#9;&#9;self._right_velocity_global = vel.rotate_by(self.position())<br>
&#9;&#9;#self._right_velocity = vel<br>
<br>
&#9;def position(self):<br>
&#9;&#9;return self._pose_object.position()<br>
<br>
&#9;def global_position(self):<br>
&#9;&#9;return self._pose_object.position()<br>
<br>
&#9;def right_mass_matrix(self):<br>
&#9;&#9;return self._mass_matrix<br>
<br>
&#9;def indexed_right_mass_matrix(self):<br>
&#9;&#9;return IndexedMatrix(self.right_mass_matrix(), None, None)<br>
<br>
&#9;# def right_mass_matrix_global(self):<br>
&#9;#     motor_matrix = self.position().rotation_matrix()<br>
&#9;#     return motor_matrix.T @ self._mass_matrix @ motor_matrix<br>
<br>
&#9;def indexed_right_mass_matrix_global(self):<br>
&#9;&#9;return IndexedMatrix(self.right_mass_matrix(),<br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;self.equation_indexes(),<br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;self.equation_indexes(),<br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;lcomm = self.equation_indexer(),<br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;rcomm = self.equation_indexer()<br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;)<br>
<br>
&#9;def main_matrix(self):<br>
&#9;&#9;return self.indexed_right_mass_matrix_global()<br>
<br>
&#9;def set_position(self, pos):<br>
&#9;&#9;self._pose_object.update_position(pos)<br>
<br>
&#9;def right_kinetic_screw(self):<br>
&#9;&#9;return Screw2.from_array(self._mass_matrix @ self.right_velocity().toarray())<br>
<br>
&#9;def right_kinetic_screw_global(self):<br>
&#9;&#9;rscrew = self.right_kinetic_screw()<br>
&#9;&#9;return rscrew.rotate_by(self.position())<br>
<br>
&#9;#def computation_indexes(self):<br>
&#9;#    return self._commutator.sources()<br>
<br>
&#9;def right_gravity(self):<br>
&#9;&#9;world_gravity = self._world.gravity().inverse_rotate_by(self.position())<br>
&#9;&#9;return IndexedVector(<br>
&#9;&#9;&#9;(world_gravity*self._mass).toarray(),<br>
&#9;&#9;&#9;self.equation_indexes(), self.commutator())<br>
<br>
&#9;def right_resistance(self):<br>
&#9;&#9;return IndexedVector(<br>
&#9;&#9;&#9;(- self.right_velocity().toarray()<br>
&#9;&#9;&#9;* self._resistance_coefficient) * 1,<br>
&#9;&#9;&#9;self.equation_indexes(), self.commutator()<br>
&#9;&#9;)<br>
<br>
&#9;def forces_in_right_part(self):<br>
&#9;&#9;return ([<br>
&#9;&#9;&#9;self.right_gravity(),<br>
&#9;&#9;&#9;self.right_resistance()<br>
&#9;&#9;])<br>
<br>
&#9;def derivative(self, p, v, a):<br>
&#9;&#9;l = v / 2<br>
&#9;&#9;r = a<br>
&#9;&#9;return l, r<br>
<br>
&#9;def summation(self, x, f, h):<br>
&#9;&#9;p, v = x<br>
&#9;&#9;l, r = f<br>
&#9;&#9;p1 = p + l * h<br>
&#9;&#9;v1 = v + r * h<br>
&#9;&#9;return p1, v1<br>
<br>
&#9;def summ_f(self, f1, f2, f3, f4):<br>
&#9;&#9;l1 = f1[0]<br>
&#9;&#9;l2 = f2[0]<br>
&#9;&#9;l3 = f3[0]<br>
&#9;&#9;l4 = f4[0]<br>
&#9;&#9;r1 = f1[1]<br>
&#9;&#9;r2 = f2[1]<br>
&#9;&#9;r3 = f3[1]<br>
&#9;&#9;r4 = f4[1]<br>
&#9;&#9;l = l1 + l2*2 + l3*2 + l4<br>
&#9;&#9;r = r1 + r2*2 + r3*2 + r4<br>
&#9;&#9;return l, r<br>
<br>
&#9;def integrate_runge_kutta(self, delta):<br>
&#9;&#9;p = self.position()<br>
&#9;&#9;v = self.right_velocity()<br>
&#9;&#9;a = self.right_acceleration()<br>
&#9;&#9;x0 = (Screw2(),v)<br>
<br>
&#9;&#9;f1 = self.derivative(*x0, a)<br>
&#9;&#9;f2 = self.derivative(*self.summation(x0, f1, delta/2), a)<br>
&#9;&#9;f3 = self.derivative(*self.summation(x0, f2, delta/2), a)<br>
&#9;&#9;f4 = self.derivative(*self.summation(x0, f3, delta), a)<br>
<br>
&#9;&#9;add = self.summ_f(f1, f2, f3, f4)<br>
&#9;&#9;add = (add[0]*1/6, add[1]*1/6)<br>
&#9;&#9;p1, v1 = self.summation(x0, add, delta)<br>
&#9;&#9;p2 = p * Motor2.from_screw(p1)<br>
&#9;&#9;p2.self_unitize()<br>
&#9;&#9;self.set_right_velocity(v1)<br>
&#9;&#9;self.set_position(p2)<br>
<br>
&#9;def integrate_euler(self, delta):<br>
&#9;&#9;acc = self.right_acceleration_global()<br>
&#9;&#9;rvel = self.right_velocity_global() + acc * delta<br>
&#9;&#9;self.set_right_velocity_global(rvel)<br>
&#9;&#9;drvel = self.right_velocity() * delta<br>
&#9;&#9;self.set_position(self.position() * Motor2.from_screw(drvel))<br>
&#9;&#9;self.position().self_unitize()<br>
<br>
&#9;def integrate_euler2(self, delta):<br>
&#9;&#9;p = self.position()<br>
&#9;&#9;v = self.right_velocity()<br>
&#9;&#9;a = self.right_acceleration()<br>
<br>
&#9;&#9;x0 = (Screw2(),v)<br>
&#9;&#9;f1 = self.derivative(*x0, a)<br>
<br>
&#9;&#9;add = (f1[0], f1[1])<br>
&#9;&#9;p1, v1 = self.summation(x0, add, delta)<br>
<br>
&#9;&#9;p2 = p * Motor2.from_screw(p1)<br>
&#9;&#9;p2.self_unitize()<br>
&#9;&#9;self.set_right_velocity(v1)<br>
&#9;&#9;self.set_position(p2)<br>
<br>
<br>
&#9;def integrate_euler_with_correction(self, delta):<br>
&#9;&#9;rvel1 = self.right_velocity()<br>
&#9;&#9;rvel2 = rvel1 + self.right_acceleration() * delta<br>
&#9;&#9;self.set_right_velocity(rvel2)<br>
<br>
&#9;&#9;mot1 = self.position() * Motor2.from_screw(rvel1 * delta)<br>
&#9;&#9;mot1.self_unitize()<br>
&#9;&#9;mot2 = self.position() * Motor2.from_screw(rvel2 * delta)<br>
&#9;&#9;mot2.self_unitize()<br>
<br>
&#9;&#9;self.set_position(mot2.average_with(mot1))<br>
<br>
&#9;def integrate_method(self, delta):<br>
&#9;&#9;p = self.position()<br>
&#9;&#9;v0 = self.right_velocity()<br>
&#9;&#9;a = self.right_acceleration()<br>
&#9;&#9;v = (v0 + a * delta) / 2 + v0 / 2<br>
<br>
&#9;&#9;dp1 = (p.mul_screw(v)) / 2<br>
&#9;&#9;dp2 = (dp1.mul_screw(v) + p.mul_screw(a)) / 2<br>
&#9;&#9;dp3 = (dp2.mul_screw(v) + dp1.mul_screw(a*2)) / 2<br>
&#9;&#9;dp4 = (dp3.mul_screw(v) + dp2.mul_screw(a*3)) / 2<br>
&#9;&#9;dp5 = (dp4.mul_screw(v) + dp3.mul_screw(a*4)) / 2<br>
<br>
&#9;&#9;r = (p + dp1.mul_scalar(delta) <br>
&#9;&#9;&#9;+ dp2.mul_scalar(delta*delta/2)<br>
&#9;&#9;&#9;+ dp3.mul_scalar(delta*delta*delta/2/3)<br>
&#9;&#9;&#9;+ dp4.mul_scalar(delta*delta*delta*delta/2/3/4)<br>
&#9;&#9;&#9;+ dp5.mul_scalar(delta*delta*delta*delta*delta/2/3/4/5)<br>
&#9;&#9;)<br>
&#9;&#9;r.self_unitize()<br>
<br>
&#9;&#9;self.set_right_velocity(v0 + a * delta)<br>
&#9;&#9;self.set_position(r)<br>
<br>
&#9;def velocity_correction(self):<br>
&#9;&#9;self.set_right_velocity(self.right_velocity() + self._right_velocity_correction)<br>
&#9;&#9;<br>
&#9;def position_correction(self):<br>
&#9;&#9;self.set_position(self.position() * Motor2.from_screw(<br>
&#9;&#9;&#9;self._right_position_correction))<br>
&#9;&#9;self.position().self_unitize()<br>
<br>
&#9;def integrate(self, delta):<br>
&#9;&#9;#self.integrate_runge_kutta(delta)<br>
&#9;&#9;<br>
&#9;&#9;self.integrate_method(delta)<br>
&#9;&#9;#self.integrate_euler(delta)<br>
&#9;&#9;<br>
&#9;&#9;#self.integrate_euler(delta/4)<br>
&#9;&#9;#self.integrate_euler(delta/4)<br>
&#9;&#9;#self.integrate_euler(delta/4)<br>
&#9;&#9;#self.integrate_euler_with_correction(delta)<br>
&#9;&#9;<br>
&#9;def acceleration_indexes(self):<br>
&#9;&#9;return self._screw_commutator.sources()<br>
<br>
&#9;def acceleration_indexer(self) -&gt; ScrewCommutator:<br>
&#9;&#9;return self._screw_commutator<br>
<br>
&#9;def equation_indexes(self):<br>
&#9;&#9;return self._screw_commutator.sources()<br>
<br>
&#9;def equation_indexer(self) -&gt; ScrewCommutator:<br>
&#9;&#9;return self._screw_commutator<br>
<br>
<br>
<br>
class Body2(Body):<br>
&#9;def __init__(self, mass=1, inertia=numpy.diag([0.00001])):<br>
&#9;&#9;super().__init__(space_dim=2, dof=3, screws=[<br>
&#9;&#9;&#9;Screw2(m=1),<br>
&#9;&#9;&#9;Screw2(v=numpy.array([1, 0])),<br>
&#9;&#9;&#9;Screw2(v=numpy.array([0, 1]))<br>
&#9;&#9;])<br>
&#9;&#9;self._mass = mass<br>
&#9;&#9;self._mass_matrix = self.create_matrix_of_mass(mass, inertia)<br>
<br>
&#9;def create_matrix_of_mass(self, mass, inertia):<br>
&#9;&#9;A = inertia<br>
&#9;&#9;B = numpy.zeros((1, 2))<br>
&#9;&#9;C = numpy.zeros((2, 1))<br>
&#9;&#9;D = numpy.diag((mass, mass))<br>
<br>
&#9;&#9;return numpy.block([<br>
&#9;&#9;&#9;[A, B],<br>
&#9;&#9;&#9;[C, D]<br>
&#9;&#9;])<br>
<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
&#9;pass<br>
<!-- END SCAT CODE -->
</body>
</html>
