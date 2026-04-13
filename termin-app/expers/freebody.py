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
numpy.set_printoptions(precision=3, suppress=True)

body = Body2()
body.set_resistance_coefficient(0)
body.set_right_velocity_global(Screw2(v=[0, 0], m=1))

world = World()
world.set_gravity(Screw2(v=[0, -0.1]))
world.add_body(body)

body.set_position(Motor2.translation(0, 0) * Motor2.rotation(math.pi/2))
sph0 = zencad.disp(zencad.sphere(1))

def animate(wdg):
    world.iteration(0.01)
    sph0.relocate(zencad.translate(body.translation()[0], body.translation()[1], 0)
                    * zencad.rotateZ(body.rotation())
    )

zencad.show(animate=animate)
