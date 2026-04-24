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
import zencad
import math

numpy.set_printoptions(precision=3, suppress=True)

body = Body2()
body.set_resistance_coefficient(0)

world = World()
world.set_gravity(Screw2(v=[0, -1]))
world.add_body(body)

body.set_position(Motor2.translation(-1, 0) * Motor2.rotation(math.pi/2))
#body.set_right_velocity_global(Screw2(v=[0,0], m=0.01))

force_link = VariableMultiForce(child=body, parent=None, 
    position=Motor2.translation(0, 0) * Motor2.rotation(math.pi/2), senses=[
    Screw2(v=[1, 0]), Screw2(v=[0, 1])])

world.add_link_force(force_link)

sph0 = zencad.disp(zencad.sphere(0.1))

start_time = time.time()
planned_time = start_time

def animate(wdg):
    global planned_time
    current_time = time.time()
    world.iteration(0.01)
    sph0.relocate(zencad.translate(body.translation()[0], body.translation()[1], 0))


zencad.show(animate=animate)