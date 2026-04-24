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

numpy.set_printoptions(precision=3, suppress=True)

body = Body2()

world = World()
world.add_body(body)

body.set_position(Motor2.translation(0, -100))
#body.set_right_velocity_global(Screw2(v=[0,0], m=0.01))

force_link = VariableMultiForce(child=body, parent=None, position=Motor2.translation(0, 0), senses=[
    Screw2(v=[1, 0]), Screw2(v=[0, 1])])

world.add_link_force(force_link)

start_time = time.time()
planned_time = start_time
while True:
    current_time = time.time()
    world.iteration(0.01)

    if 1 == 1 or world.iteration_counter() % 10 == 0:
        print()
        print("Position:", body.translation())
        print("Velocity:", body.right_velocity_global())
        print("Last solution:", world.last_solution()[0])

    planned_time += 0.01
    sleep_interval = planned_time - time.time()
    if sleep_interval > 0:
        time.sleep(sleep_interval)

    # break

print(force_link.B_matrix_list()[0])
