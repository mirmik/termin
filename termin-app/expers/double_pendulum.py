#!/usr/bin/env python3

import time
from termin.physics.indexed_matrix import IndexedVector
from termin.physics.body import Body2
from termin.physics.world import World
from termin.physics.force import Force
from termin.physics.force_link import VariableMultiForce
from termin.ga201 import Screw2
from termin.ga201 import Motor2
import numpy
import math
import zencad

numpy.set_printoptions(precision=2, suppress=True)

body1 = Body2(mass=1, inertia=1)
body2 = Body2(mass=1, inertia=1)

world = World()
world.add_body(body1)
world.add_body(body2)
world.set_gravity(Screw2(v=[0, -10]))

body1.set_resistance_coefficient(0)
body2.set_resistance_coefficient(0)

#body1.set_position(Motor2.translation(0, 10) * Motor2.rotation(0))
body1.set_position(Motor2.translation(0, 10) * Motor2.rotation(math.pi/2))
#body2.set_position(Motor2.translation(10, -10)  * Motor2.rotation(math.pi/2))
body2.set_position(Motor2.translation(10, -10))

force_link1 = VariableMultiForce(child=body1, parent=None, position=Motor2.translation(0, 0) * Motor2.rotation(0), senses=[
    Screw2(v=[1, 0]), Screw2(v=[0, 1])], stiffness=[1, 1])
world.add_link_force(force_link1)

force_link2 = VariableMultiForce(child=body2, parent=body1, position=Motor2.translation(0, 10) * Motor2.rotation(math.pi/2), senses=[
    Screw2(v=[1, 0]), Screw2(v=[0, 1])], stiffness=[1, 1])

world.add_link_force(force_link2)

sph0 = zencad.disp(zencad.sphere(1))
sph1 = zencad.disp(zencad.sphere(1))

start_time = time.time()
planned_time = start_time

#print(body2.screw_commutator().position())
#print(force_link2.screw_commutator().position())
#print(force_link2.screw_commutator().derivative(body1.screw_commutator()))

#while True:
def animate(wdg):
    global planned_time
    current_time = time.time()
    world.iteration(0.01)

    print(world.last_Q)
    print(world.last_b)

    #print(body2.right_acceleration_global(), body2.right_velocity_global())

    sph0.relocate(zencad.translate(body1.translation()[0], body1.translation()[1], 0))
    sph1.relocate(zencad.translate(body2.translation()[0], body2.translation()[1], 0))


#animate(None)  
zencad.show(animate=animate)