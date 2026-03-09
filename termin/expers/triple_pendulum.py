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

S = 0
#numpy.set_printoptions(precision=1, suppress=True)

body1 = Body2(mass=1)

world = World()
world.set_gravity(Screw2(v=[0, -10]))
world.add_body(body1)

body1.set_resistance_coefficient(S)

body1.set_position(Motor2.translation(0, -10))

force_link1 = VariableMultiForce(child=body1, parent=None, position=Motor2.translation(0, 0), senses=[
    Screw2(v=[1, 0]), Screw2(v=[0, 1])], stiffness=[1, 1])
world.add_link_force(force_link1)


def add_body(parent, position, mass = 1):
    body = Body2(mass=mass)
    world.add_body(body)
    body.set_position(position)
    body.set_resistance_coefficient(S)
    force_link = VariableMultiForce(child=body, parent=parent, position=parent.position(), senses=[
        Screw2(v=[1, 0]), Screw2(v=[0, 1])], stiffness=[1, 1])
    world.add_link_force(force_link)
    sph = zencad.disp(zencad.sphere(1))
    return body, sph


sph0 = zencad.disp(zencad.sphere(1))

body2, sph1 = add_body(body1, Motor2.translation(10, -10), mass=1)
body3, sph2 = add_body(body2, Motor2.translation(20, -10), mass=1)
body4, sph3 = add_body(body3, Motor2.translation(30, -10), mass=1)
body5, sph4 = add_body(body4, Motor2.translation(40, -10), mass=1)
body6, sph5 = add_body(body5, Motor2.translation(50, -10), mass=1)
body7, sph6 = add_body(body6, Motor2.translation(60, -10), mass=1)
body8, sph7 = add_body(body7, Motor2.translation(70, -10), mass=1)
body9, sph8 = add_body(body8, Motor2.translation(80, -10), mass=1)
body10, sph9 = add_body(body9, Motor2.translation(90, -10), mass=1)
body11, sph10 = add_body(body10, Motor2.translation(100, -10), mass=1)
body12, sph11 = add_body(body11, Motor2.translation(110, -10), mass=1)
body13, sph12 = add_body(body12, Motor2.translation(120, -10), mass=1)
body14, sph13 = add_body(body13, Motor2.translation(130, -10), mass=1)
body15, sph14 = add_body(body14, Motor2.translation(140, -10), mass=1)


start_time = time.time()
planned_time = start_time

#while True:
last_time = time.time()
start_time = time.time()
def animate(wdg):
    global last_time
    global planned_time
    current_time = time.time()

    if time.time() - start_time < 1:
        return

    world.iteration(0.02)
    
    sph0.relocate(zencad.translate(body1.translation()[0], body1.translation()[1], 0))
    sph1.relocate(zencad.translate(body2.translation()[0], body2.translation()[1], 0))
    sph2.relocate(zencad.translate(body3.translation()[0], body3.translation()[1], 0))
    sph3.relocate(zencad.translate(body4.translation()[0], body4.translation()[1], 0))
    sph4.relocate(zencad.translate(body5.translation()[0], body5.translation()[1], 0))
    sph5.relocate(zencad.translate(body6.translation()[0], body6.translation()[1], 0))
    sph6.relocate(zencad.translate(body7.translation()[0], body7.translation()[1], 0))
    sph7.relocate(zencad.translate(body8.translation()[0], body8.translation()[1], 0))
    sph8.relocate(zencad.translate(body9.translation()[0], body9.translation()[1], 0))
    sph9.relocate(zencad.translate(body10.translation()[0], body10.translation()[1], 0))
    sph10.relocate(zencad.translate(body11.translation()[0], body11.translation()[1], 0))
    sph11.relocate(zencad.translate(body12.translation()[0], body12.translation()[1], 0))
    sph12.relocate(zencad.translate(body13.translation()[0], body13.translation()[1], 0))
    sph13.relocate(zencad.translate(body14.translation()[0], body14.translation()[1], 0))
    sph14.relocate(zencad.translate(body15.translation()[0], body15.translation()[1], 0))
    
    print(time.time() - last_time)
    last_time = time.time()


def main():
    start_time = time.time()
    while True:
        animate(None)
        if time.time() - start_time > 10:
            break

zencad.show(animate=animate, animate_step=0.02)


# import cProfile, pstats
# profiler = cProfile.Profile()
# profiler.enable()
# main()
# profiler.disable()
# stats = pstats.Stats(profiler).sort_stats('tottime')
# stats.print_stats()