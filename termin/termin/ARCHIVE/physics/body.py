#!/usr/bin/env python3

import numpy
from termin.physics.screw_commutator import VariableValueCommutator
from termin.physics.indexed_matrix import IndexedMatrix, IndexedVector
from termin.physics.pose_object import PoseObject
from termin.physics.screw_commutator import ScrewCommutator
from termin.ga201 import Motor2
from termin.ga201 import Screw2
from termin.physics.frame import Frame

class Body(Frame):
    def __init__(self, space_dim, dof, screws) -> None:
        super().__init__(pose_object=PoseObject(), screws=screws)
        self.space_dim = space_dim
        self.dof = dof
        self._right_acceleration_global = Screw2()
        self._right_velocity_global = Screw2()
        self._resistance_coefficient = 0
        self._right_velocity_correction = Screw2()
        self._right_position_correction = Screw2()
        self._world = None

    def bind_world(self, w):
        self._world = w

    def set_resistance_coefficient(self, coeff):
        self._resistance_coefficient = coeff

    def translation(self):
        return self.position().factorize_translation_vector()

    def rotation(self):
        return self.position().factorize_rotation_angle()

    def downbind_solution(self):
        self._right_acceleration_global = Screw2(
            m=self._screw_commutator.values()[0],
            v=numpy.array(self._screw_commutator.values()[1:])
        ).rotate_by(self.position())

    def downbind_velocity_solution(self):
        self._right_velocity_correction = Screw2(
            m=self._screw_commutator.values()[0],
            v=numpy.array(self._screw_commutator.values()[1:])
        )

    def downbind_position_solution(self):
        self._right_position_correction = Screw2(
            m=self._screw_commutator.values()[0],
            v=numpy.array(self._screw_commutator.values()[1:])
        )


    # def unbind_force(self, force):
    #     if force.is_right_global() and force.is_linked_to(self):
    #         self._right_forces_global.remove(force)
    #     elif force.is_right() and force.is_linked_to(self):
    #         self._right_forces.remove(force)
    #     else:
    #         raise Exception("Force is not linked to this body")

    #     force.clean_bind_information()

    # def add_right_force_global(self, force):
    #     self._right_forces_global.append(force)
    #     force.set_right_global_type()
    #     force.set_linked_object(self)

    # def add_right_force(self, force):
    #     self._right_forces.append(force)
    #     force.set_right_type()
    #     force.set_linked_object(self)

    def right_acceleration(self):
        return self._right_acceleration_global.inverse_rotate_by(self.position())

    def right_acceleration_global(self):
        return self._right_acceleration_global

    def right_velocity_global(self):
        return self._right_velocity_global
        #return self._right_velocity.rotate_by(self.position())

    def right_velocity(self):
        return self._right_velocity_global.inverse_rotate_by(self.position())
        #return self._right_velocity

    def set_right_velocity_global(self, vel):
        self._right_velocity_global = vel
        #self._right_velocity = vel.inverse_rotate_by(self.position())

    def set_right_velocity(self, vel):
        self._right_velocity_global = vel.rotate_by(self.position())
        #self._right_velocity = vel
 
    def position(self):
        return self._pose_object.position()

    def global_position(self):
        return self._pose_object.position()

    def right_mass_matrix(self):
        return self._mass_matrix

    def indexed_right_mass_matrix(self):
        return IndexedMatrix(self.right_mass_matrix(), None, None)

    # def right_mass_matrix_global(self):
    #     motor_matrix = self.position().rotation_matrix()
    #     return motor_matrix.T @ self._mass_matrix @ motor_matrix

    def indexed_right_mass_matrix_global(self):
        return IndexedMatrix(self.right_mass_matrix(),
                             self.equation_indexes(),
                             self.equation_indexes(),
                             lcomm = self.equation_indexer(),
                             rcomm = self.equation_indexer()
                             )

    def main_matrix(self):
        return self.indexed_right_mass_matrix_global()

    def set_position(self, pos):
        self._pose_object.update_position(pos)

    def right_kinetic_screw(self):
        return Screw2.from_array(self._mass_matrix @ self.right_velocity().toarray())

    def right_kinetic_screw_global(self):
        rscrew = self.right_kinetic_screw()
        return rscrew.rotate_by(self.position())

    #def computation_indexes(self):
    #    return self._commutator.sources()

    def right_gravity(self):
        world_gravity = self._world.gravity().inverse_rotate_by(self.position())
        return IndexedVector(
            (world_gravity*self._mass).toarray(),
            self.equation_indexes(), self.commutator())

    def right_resistance(self):
        return IndexedVector(
            (- self.right_velocity().toarray()
             * self._resistance_coefficient) * 1,
            self.equation_indexes(), self.commutator()
        )

    def forces_in_right_part(self):
        return ([
            self.right_gravity(),
            self.right_resistance()
        ])

    def derivative(self, p, v, a):
        l = v / 2
        r = a
        return l, r

    def summation(self, x, f, h):
        p, v = x
        l, r = f
        p1 = p + l * h
        v1 = v + r * h
        return p1, v1

    def summ_f(self, f1, f2, f3, f4):
        l1 = f1[0]
        l2 = f2[0]
        l3 = f3[0]
        l4 = f4[0]
        r1 = f1[1]
        r2 = f2[1]
        r3 = f3[1]
        r4 = f4[1]
        l = l1 + l2*2 + l3*2 + l4
        r = r1 + r2*2 + r3*2 + r4
        return l, r

    def integrate_runge_kutta(self, delta):
        p = self.position()
        v = self.right_velocity()
        a = self.right_acceleration()
        x0 = (Screw2(),v)

        f1 = self.derivative(*x0, a)
        f2 = self.derivative(*self.summation(x0, f1, delta/2), a)
        f3 = self.derivative(*self.summation(x0, f2, delta/2), a)
        f4 = self.derivative(*self.summation(x0, f3, delta), a)

        add = self.summ_f(f1, f2, f3, f4)
        add = (add[0]*1/6, add[1]*1/6)
        p1, v1 = self.summation(x0, add, delta)
        p2 = p * Motor2.from_screw(p1)
        p2.self_unitize()
        self.set_right_velocity(v1)
        self.set_position(p2)

    def integrate_euler(self, delta):
        acc = self.right_acceleration_global()
        rvel = self.right_velocity_global() + acc * delta
        self.set_right_velocity_global(rvel)
        drvel = self.right_velocity() * delta
        self.set_position(self.position() * Motor2.from_screw(drvel))
        self.position().self_unitize()

    def integrate_euler2(self, delta):
        p = self.position()
        v = self.right_velocity()
        a = self.right_acceleration()

        x0 = (Screw2(),v)
        f1 = self.derivative(*x0, a)

        add = (f1[0], f1[1])
        p1, v1 = self.summation(x0, add, delta)

        p2 = p * Motor2.from_screw(p1)
        p2.self_unitize()
        self.set_right_velocity(v1)
        self.set_position(p2)


    def integrate_euler_with_correction(self, delta):
        rvel1 = self.right_velocity()
        rvel2 = rvel1 + self.right_acceleration() * delta
        self.set_right_velocity(rvel2)

        mot1 = self.position() * Motor2.from_screw(rvel1 * delta)
        mot1.self_unitize()
        mot2 = self.position() * Motor2.from_screw(rvel2 * delta)
        mot2.self_unitize()

        self.set_position(mot2.average_with(mot1))

    def integrate_method(self, delta):
        p = self.position()
        v0 = self.right_velocity()
        a = self.right_acceleration()
        v = (v0 + a * delta) / 2 + v0 / 2

        dp1 = (p.mul_screw(v)) / 2
        dp2 = (dp1.mul_screw(v) + p.mul_screw(a)) / 2
        dp3 = (dp2.mul_screw(v) + dp1.mul_screw(a*2)) / 2
        dp4 = (dp3.mul_screw(v) + dp2.mul_screw(a*3)) / 2
        dp5 = (dp4.mul_screw(v) + dp3.mul_screw(a*4)) / 2

        r = (p + dp1.mul_scalar(delta) 
            + dp2.mul_scalar(delta*delta/2)
            + dp3.mul_scalar(delta*delta*delta/2/3)
            + dp4.mul_scalar(delta*delta*delta*delta/2/3/4)
            + dp5.mul_scalar(delta*delta*delta*delta*delta/2/3/4/5)
        )
        r.self_unitize()

        self.set_right_velocity(v0 + a * delta)
        self.set_position(r)

    def velocity_correction(self):
        self.set_right_velocity(self.right_velocity() + self._right_velocity_correction)
        
    def position_correction(self):
        self.set_position(self.position() * Motor2.from_screw(
            self._right_position_correction))
        self.position().self_unitize()

    def integrate(self, delta):
        #self.integrate_runge_kutta(delta)
        
        self.integrate_method(delta)
        #self.integrate_euler(delta)
        
        #self.integrate_euler(delta/4)
        #self.integrate_euler(delta/4)
        #self.integrate_euler(delta/4)
        #self.integrate_euler_with_correction(delta)
        
    def acceleration_indexes(self):
        return self._screw_commutator.sources()

    def acceleration_indexer(self) -> ScrewCommutator:
        return self._screw_commutator

    def equation_indexes(self):
        return self._screw_commutator.sources()

    def equation_indexer(self) -> ScrewCommutator:
        return self._screw_commutator



class Body2(Body):
    def __init__(self, mass=1, inertia=numpy.diag([0.00001])):
        super().__init__(space_dim=2, dof=3, screws=[
            Screw2(m=1),
            Screw2(v=numpy.array([1, 0])),
            Screw2(v=numpy.array([0, 1]))
        ])
        self._mass = mass
        self._mass_matrix = self.create_matrix_of_mass(mass, inertia)

    def create_matrix_of_mass(self, mass, inertia):
        A = inertia
        B = numpy.zeros((1, 2))
        C = numpy.zeros((2, 1))
        D = numpy.diag((mass, mass))

        return numpy.block([
            [A, B],
            [C, D]
        ])


if __name__ == "__main__":
    pass
