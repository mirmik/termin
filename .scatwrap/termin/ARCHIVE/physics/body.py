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
    def __init__(self, space_dim, dof, screws) -&gt; None:<br>
        super().__init__(pose_object=PoseObject(), screws=screws)<br>
        self.space_dim = space_dim<br>
        self.dof = dof<br>
        self._right_acceleration_global = Screw2()<br>
        self._right_velocity_global = Screw2()<br>
        self._resistance_coefficient = 0<br>
        self._right_velocity_correction = Screw2()<br>
        self._right_position_correction = Screw2()<br>
        self._world = None<br>
<br>
    def bind_world(self, w):<br>
        self._world = w<br>
<br>
    def set_resistance_coefficient(self, coeff):<br>
        self._resistance_coefficient = coeff<br>
<br>
    def translation(self):<br>
        return self.position().factorize_translation_vector()<br>
<br>
    def rotation(self):<br>
        return self.position().factorize_rotation_angle()<br>
<br>
    def downbind_solution(self):<br>
        self._right_acceleration_global = Screw2(<br>
            m=self._screw_commutator.values()[0],<br>
            v=numpy.array(self._screw_commutator.values()[1:])<br>
        ).rotate_by(self.position())<br>
<br>
    def downbind_velocity_solution(self):<br>
        self._right_velocity_correction = Screw2(<br>
            m=self._screw_commutator.values()[0],<br>
            v=numpy.array(self._screw_commutator.values()[1:])<br>
        )<br>
<br>
    def downbind_position_solution(self):<br>
        self._right_position_correction = Screw2(<br>
            m=self._screw_commutator.values()[0],<br>
            v=numpy.array(self._screw_commutator.values()[1:])<br>
        )<br>
<br>
<br>
    # def unbind_force(self, force):<br>
    #     if force.is_right_global() and force.is_linked_to(self):<br>
    #         self._right_forces_global.remove(force)<br>
    #     elif force.is_right() and force.is_linked_to(self):<br>
    #         self._right_forces.remove(force)<br>
    #     else:<br>
    #         raise Exception(&quot;Force is not linked to this body&quot;)<br>
<br>
    #     force.clean_bind_information()<br>
<br>
    # def add_right_force_global(self, force):<br>
    #     self._right_forces_global.append(force)<br>
    #     force.set_right_global_type()<br>
    #     force.set_linked_object(self)<br>
<br>
    # def add_right_force(self, force):<br>
    #     self._right_forces.append(force)<br>
    #     force.set_right_type()<br>
    #     force.set_linked_object(self)<br>
<br>
    def right_acceleration(self):<br>
        return self._right_acceleration_global.inverse_rotate_by(self.position())<br>
<br>
    def right_acceleration_global(self):<br>
        return self._right_acceleration_global<br>
<br>
    def right_velocity_global(self):<br>
        return self._right_velocity_global<br>
        #return self._right_velocity.rotate_by(self.position())<br>
<br>
    def right_velocity(self):<br>
        return self._right_velocity_global.inverse_rotate_by(self.position())<br>
        #return self._right_velocity<br>
<br>
    def set_right_velocity_global(self, vel):<br>
        self._right_velocity_global = vel<br>
        #self._right_velocity = vel.inverse_rotate_by(self.position())<br>
<br>
    def set_right_velocity(self, vel):<br>
        self._right_velocity_global = vel.rotate_by(self.position())<br>
        #self._right_velocity = vel<br>
 <br>
    def position(self):<br>
        return self._pose_object.position()<br>
<br>
    def global_position(self):<br>
        return self._pose_object.position()<br>
<br>
    def right_mass_matrix(self):<br>
        return self._mass_matrix<br>
<br>
    def indexed_right_mass_matrix(self):<br>
        return IndexedMatrix(self.right_mass_matrix(), None, None)<br>
<br>
    # def right_mass_matrix_global(self):<br>
    #     motor_matrix = self.position().rotation_matrix()<br>
    #     return motor_matrix.T @ self._mass_matrix @ motor_matrix<br>
<br>
    def indexed_right_mass_matrix_global(self):<br>
        return IndexedMatrix(self.right_mass_matrix(),<br>
                             self.equation_indexes(),<br>
                             self.equation_indexes(),<br>
                             lcomm = self.equation_indexer(),<br>
                             rcomm = self.equation_indexer()<br>
                             )<br>
<br>
    def main_matrix(self):<br>
        return self.indexed_right_mass_matrix_global()<br>
<br>
    def set_position(self, pos):<br>
        self._pose_object.update_position(pos)<br>
<br>
    def right_kinetic_screw(self):<br>
        return Screw2.from_array(self._mass_matrix @ self.right_velocity().toarray())<br>
<br>
    def right_kinetic_screw_global(self):<br>
        rscrew = self.right_kinetic_screw()<br>
        return rscrew.rotate_by(self.position())<br>
<br>
    #def computation_indexes(self):<br>
    #    return self._commutator.sources()<br>
<br>
    def right_gravity(self):<br>
        world_gravity = self._world.gravity().inverse_rotate_by(self.position())<br>
        return IndexedVector(<br>
            (world_gravity*self._mass).toarray(),<br>
            self.equation_indexes(), self.commutator())<br>
<br>
    def right_resistance(self):<br>
        return IndexedVector(<br>
            (- self.right_velocity().toarray()<br>
             * self._resistance_coefficient) * 1,<br>
            self.equation_indexes(), self.commutator()<br>
        )<br>
<br>
    def forces_in_right_part(self):<br>
        return ([<br>
            self.right_gravity(),<br>
            self.right_resistance()<br>
        ])<br>
<br>
    def derivative(self, p, v, a):<br>
        l = v / 2<br>
        r = a<br>
        return l, r<br>
<br>
    def summation(self, x, f, h):<br>
        p, v = x<br>
        l, r = f<br>
        p1 = p + l * h<br>
        v1 = v + r * h<br>
        return p1, v1<br>
<br>
    def summ_f(self, f1, f2, f3, f4):<br>
        l1 = f1[0]<br>
        l2 = f2[0]<br>
        l3 = f3[0]<br>
        l4 = f4[0]<br>
        r1 = f1[1]<br>
        r2 = f2[1]<br>
        r3 = f3[1]<br>
        r4 = f4[1]<br>
        l = l1 + l2*2 + l3*2 + l4<br>
        r = r1 + r2*2 + r3*2 + r4<br>
        return l, r<br>
<br>
    def integrate_runge_kutta(self, delta):<br>
        p = self.position()<br>
        v = self.right_velocity()<br>
        a = self.right_acceleration()<br>
        x0 = (Screw2(),v)<br>
<br>
        f1 = self.derivative(*x0, a)<br>
        f2 = self.derivative(*self.summation(x0, f1, delta/2), a)<br>
        f3 = self.derivative(*self.summation(x0, f2, delta/2), a)<br>
        f4 = self.derivative(*self.summation(x0, f3, delta), a)<br>
<br>
        add = self.summ_f(f1, f2, f3, f4)<br>
        add = (add[0]*1/6, add[1]*1/6)<br>
        p1, v1 = self.summation(x0, add, delta)<br>
        p2 = p * Motor2.from_screw(p1)<br>
        p2.self_unitize()<br>
        self.set_right_velocity(v1)<br>
        self.set_position(p2)<br>
<br>
    def integrate_euler(self, delta):<br>
        acc = self.right_acceleration_global()<br>
        rvel = self.right_velocity_global() + acc * delta<br>
        self.set_right_velocity_global(rvel)<br>
        drvel = self.right_velocity() * delta<br>
        self.set_position(self.position() * Motor2.from_screw(drvel))<br>
        self.position().self_unitize()<br>
<br>
    def integrate_euler2(self, delta):<br>
        p = self.position()<br>
        v = self.right_velocity()<br>
        a = self.right_acceleration()<br>
<br>
        x0 = (Screw2(),v)<br>
        f1 = self.derivative(*x0, a)<br>
<br>
        add = (f1[0], f1[1])<br>
        p1, v1 = self.summation(x0, add, delta)<br>
<br>
        p2 = p * Motor2.from_screw(p1)<br>
        p2.self_unitize()<br>
        self.set_right_velocity(v1)<br>
        self.set_position(p2)<br>
<br>
<br>
    def integrate_euler_with_correction(self, delta):<br>
        rvel1 = self.right_velocity()<br>
        rvel2 = rvel1 + self.right_acceleration() * delta<br>
        self.set_right_velocity(rvel2)<br>
<br>
        mot1 = self.position() * Motor2.from_screw(rvel1 * delta)<br>
        mot1.self_unitize()<br>
        mot2 = self.position() * Motor2.from_screw(rvel2 * delta)<br>
        mot2.self_unitize()<br>
<br>
        self.set_position(mot2.average_with(mot1))<br>
<br>
    def integrate_method(self, delta):<br>
        p = self.position()<br>
        v0 = self.right_velocity()<br>
        a = self.right_acceleration()<br>
        v = (v0 + a * delta) / 2 + v0 / 2<br>
<br>
        dp1 = (p.mul_screw(v)) / 2<br>
        dp2 = (dp1.mul_screw(v) + p.mul_screw(a)) / 2<br>
        dp3 = (dp2.mul_screw(v) + dp1.mul_screw(a*2)) / 2<br>
        dp4 = (dp3.mul_screw(v) + dp2.mul_screw(a*3)) / 2<br>
        dp5 = (dp4.mul_screw(v) + dp3.mul_screw(a*4)) / 2<br>
<br>
        r = (p + dp1.mul_scalar(delta) <br>
            + dp2.mul_scalar(delta*delta/2)<br>
            + dp3.mul_scalar(delta*delta*delta/2/3)<br>
            + dp4.mul_scalar(delta*delta*delta*delta/2/3/4)<br>
            + dp5.mul_scalar(delta*delta*delta*delta*delta/2/3/4/5)<br>
        )<br>
        r.self_unitize()<br>
<br>
        self.set_right_velocity(v0 + a * delta)<br>
        self.set_position(r)<br>
<br>
    def velocity_correction(self):<br>
        self.set_right_velocity(self.right_velocity() + self._right_velocity_correction)<br>
        <br>
    def position_correction(self):<br>
        self.set_position(self.position() * Motor2.from_screw(<br>
            self._right_position_correction))<br>
        self.position().self_unitize()<br>
<br>
    def integrate(self, delta):<br>
        #self.integrate_runge_kutta(delta)<br>
        <br>
        self.integrate_method(delta)<br>
        #self.integrate_euler(delta)<br>
        <br>
        #self.integrate_euler(delta/4)<br>
        #self.integrate_euler(delta/4)<br>
        #self.integrate_euler(delta/4)<br>
        #self.integrate_euler_with_correction(delta)<br>
        <br>
    def acceleration_indexes(self):<br>
        return self._screw_commutator.sources()<br>
<br>
    def acceleration_indexer(self) -&gt; ScrewCommutator:<br>
        return self._screw_commutator<br>
<br>
    def equation_indexes(self):<br>
        return self._screw_commutator.sources()<br>
<br>
    def equation_indexer(self) -&gt; ScrewCommutator:<br>
        return self._screw_commutator<br>
<br>
<br>
<br>
class Body2(Body):<br>
    def __init__(self, mass=1, inertia=numpy.diag([0.00001])):<br>
        super().__init__(space_dim=2, dof=3, screws=[<br>
            Screw2(m=1),<br>
            Screw2(v=numpy.array([1, 0])),<br>
            Screw2(v=numpy.array([0, 1]))<br>
        ])<br>
        self._mass = mass<br>
        self._mass_matrix = self.create_matrix_of_mass(mass, inertia)<br>
<br>
    def create_matrix_of_mass(self, mass, inertia):<br>
        A = inertia<br>
        B = numpy.zeros((1, 2))<br>
        C = numpy.zeros((2, 1))<br>
        D = numpy.diag((mass, mass))<br>
<br>
        return numpy.block([<br>
            [A, B],<br>
            [C, D]<br>
        ])<br>
<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
    pass<br>
<!-- END SCAT CODE -->
</body>
</html>
