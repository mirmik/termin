#!/usr/bin/env python3

import time
from termin.physics.indexed_matrix import IndexedVector
from termin.physics.body import Body2
from termin.solver import quadratic_problem_solver_indexes_array
from termin.physics.world import World
from termin.physics.force import Force
from termin.physics.force_link import VariableMultiForce
from termin.ga201 import Screw2
from termin.ga201 import Motor2
import numpy
import zencad

#numpy.set_printoptions(precision=1, suppress=True)

body1 = Body2(mass=1)
body2 = Body2()

world = World()
world.add_body(body1)
world.add_body(body2)

body1.set_resistance_coefficient(10)
body2.set_resistance_coefficient(10)

body1.set_position(Motor2.translation(0, -10))
body2.set_position(Motor2.translation(0, -20))

force_link1 = VariableMultiForce(child=body1, parent=None, position=Motor2.translation(0, 0), senses=[
    Screw2(v=[1, 0]), Screw2(v=[0, 1])], stiffness=[0.5, 0.5])
world.add_link_force(force_link1)

force_link2 = VariableMultiForce(child=body2, parent=body1, position=Motor2.translation(0, -10), senses=[
    Screw2(v=[1, 0]), Screw2(v=[0, 1])], stiffness=[0.5, 0.5])
world.add_link_force(force_link2)


body2.set_position(Motor2.translation(0, -30))
body2.set_right_velocity(Screw2(v=[0, -10]))

start_time = time.time()
planned_time = start_time

sph0 = zencad.disp(zencad.sphere(1))
sph1 = zencad.disp(zencad.sphere(1))

def animate(wdg):
    global planned_time

    world.correction()
    current_time = time.time()
    world.iteration(0.001)
    #exit()

    if 1 == 1 or world.iteration_counter() % 10 == 0:
        print()
        #print("dQd1:", force_link2.B_matrix_list()[1])
        print("Position1:", body1.translation())
        print("Position2:", body2.translation())
        #print("Solution:", world.last_solution()[0])
        #print("Splution:", world.last_solution()[1])

    sph0.relocate(zencad.translate(0, body1.translation()[1], 0))
    sph1.relocate(zencad.translate(0, body2.translation()[1], 0))

    planned_time += 0.01
    sleep_interval = planned_time - time.time()
    if sleep_interval > 0:
        time.sleep(sleep_interval)

    # break

zencad.show(animate=animate)