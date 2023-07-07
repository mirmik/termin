#!/usr/bin/env python3
import time

from terminus.zencad_adapter import *
from terminus.barrier import *
from terminus.ga201.line import Line2
from terminus.ga201.point import Point2
from terminus.ga201.motor import Motor2
from terminus.ga201.join import join_point_point, oriented_distance
from terminus.ga201.convex_body import ConvexBody2, ConvexWorld2
import math

import zencad
zencad.disable_lazy()

#zencad.set_default_point_color(zencad.Color(1,0,0))

class Jacobian:
    def __init__(self, matrix):
        self.matrix = matrix

    def scale(self, a):
        return Jacobian(self.matrix * a)

    def __str__(self):
        return str(self.matrix)

    def solve(self, vector):
        p = numpy.linalg.inv(self.matrix)
        return p.dot(vector)

    def solve2(self, vector):
        jt = self.T()
        jtj = self.T().matmul(self)
        v = jt.dot(vector)
        return jtj.solve(v)

    def dot(self, vector):
        return self.matrix.dot(vector)

    def T(self):
        return Jacobian(self.matrix.T)

    def qdim(self):
        return self.matrix.shape[1]
    
    def with_expanded_qdim(self, nqdim):
        qd = self.qdim()
        rows = self.matrix.shape[0]
        conctable = np.zeros((rows, nqdim-qd))
        ntable = numpy.concatenate((self.matrix, conctable), axis=1)
        return Jacobian(ntable)

    def matmul(self, oth):
        return Jacobian(numpy.matmul(self.matrix, oth.matrix))

    def __str__(self):
        return str(self.matrix)

    def __repr__(self):
        return str(self.matrix)

    def __add__(self, oth):
        return Jacobian(self.matrix + oth.matrix)

def solve_2d_velocity_system(jacobians, velocities, alphas, prepare_q, gamma):
    qdim = jacobians[0].qdim()
    sdim = len(jacobians)

    J = jacobians[0].T().matmul(jacobians[0])
    B = jacobians[0].T().dot(velocities[0])

#    return J.solve(B)

    b = numpy.zeros((qdim,1), dtype=numpy.float64)
    for i in range(sdim):
        D = jacobians[i].T().dot(velocities[i])
        bb = alphas[i] * D
        b = b + bb
    b += gamma

    A = Jacobian(numpy.zeros((qdim, qdim), dtype=numpy.float64))
    for i in range(sdim):
        jtj = jacobians[i].T().matmul(jacobians[i])
        a = jtj.scale(alphas[i])
        A += a
    A.matrix += prepare_q

    x = A.solve(b)
    return x


class SensorPoint(zencad.assemble.unit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add(zencad.point3(0,0))

    def evaluate_parent_kinematic_units(self):
        self.parent_kinematic_units = []
        for p in self.parents_list():
            if isinstance(p, zencad.assemble.kinematic_unit):
                self.parent_kinematic_units.append(p)
        self.parent_kinematic_units = list(reversed(self.parent_kinematic_units))

    def jacobi_matrix(self):
        return Jacobian(right_jacobi_matrix_lin2(self.parent_kinematic_units, self))

    def expanded_jacobi_matrix(self, qdim):
        j = Jacobian(right_jacobi_matrix_lin2(self.parent_kinematic_units, self))
        if j.qdim() < qdim:
            j = j.with_expanded_qdim(qdim)
        return j

    def draw_sensivities_arrow(self, sens):
        for p in self.parent_kinematic_units:
            sens = right_sensivity_screw2_of_kinunit(p, self)
            motor = zencad_transform_to_motor2(self.global_location)
            sens = sens.rotate_by_angle(motor.factorize_rotation_angle())
            center = self.global_location.translation()
            arrow = zencad.segment(center, center+zencad.point3(sens.v[0], sens.v[1], 0))
            zencad.display(arrow)

    def center_as_point(self):
        trans = self.global_location
        tr = trans.translation()
        return Point2(tr.x, tr.y, 1)

    def projection_to(self, body):
        tr = self.global_location.translation()
        p = Point2(tr.x, tr.y, 1)
        proj = body.point_projection(p)
        return proj

    def global_to_local(self, vec):
        motor = zencad_transform_to_motor2(self.global_location)
        return motor.rotate_nparray_inverse(vec)

    def local_to_global(self, vec):
        motor = zencad_transform_to_motor2(self.global_location)
        return motor.rotate_nparray(vec)


class Link(zencad.assemble.unit):
    def __init__(self, l):
        super().__init__()
        self.add(zencad.segment((0,0),(0,l)))
        self.spoints = [
            SensorPoint(location=zencad.move(0,l*2/8,0)),
            SensorPoint(location=zencad.move(0,l*4/8,0)),
            SensorPoint(location=zencad.move(0,l*6/8,0)),
            SensorPoint(location=zencad.move(0,l*8/8,0)),
        ]
        for s in self.spoints:
            self.add_child(s)

    def final_sensor(self):
        return self.spoints[-1]

class Manipulator(zencad.assemble.unit):
    def __init__(self):
        super().__init__()
        self.N = 4
        self.L = 1
        self.A = -math.pi/8
        self.make_body()
        self.sensor_points = self.get_sensor_points()
        for s in self.sensor_points:
            s.evaluate_parent_kinematic_units()

        self.half_sensor = self.links[1].final_sensor()
        self.final_sensor = self.links[-1].final_sensor()

        self.init_position()

    def init_position(self):
        for i in range(self.N):
            self.rots[i].set_coord(self.A)
        self.location_update()

    def qdim(self):
        return len(self.rots)

    def draw_sensivities_arrow(self):
        for s in self.sensor_points:
            s.draw_sensivities_arrow(s)

    def get_sensor_points(self):
        spoints = []
        for u in self.links:
            spoints.extend(u.spoints)
        return spoints

    def make_body(self):
        self.links = [Link(self.L) for i in range(self.N)]
        self.rots = [zencad.assemble.rotator((0,0,1))  for i in range(self.N)]

        for u, r in zip(self.links, self.rots):
            r.link(u)

        self.add_child(self.rots[0])
        for i in range(self.N-1):
            self.links[i].add_child(self.rots[i+1])
            self.rots[i+1].relocate(zencad.move(0,self.L,0))
        
        for i in range(self.N):
            self.rots[i].set_coord(self.A)

        self.location_update()

    def final_jacobian(self):
        return self.final_sensor.jacobi_matrix()

    def apply_speed_control(self, s, delta_t = 0.01):
        for i in range(self.N):
            self.rots[i].set_coord(self.rots[i].coord + s[i] * delta_t)
        self.location_update()

    

#convex = ConvexBody2(lines)
#draw_body2(convex)

# ip1 = draw_point2(Point2(0,0))
# ip2 = draw_point2(Point2(0,0))

# q1 = Motor.rotation(math.pi/2)
# q2 = Motor.translation(2,0)
# q3 = Motor.rotation(math.pi/2)
# q4 = Motor.translation(2,0)
# q = q1 * q2 * q3 * q4
# p = Point2(1, 0)

manipulator = Manipulator()

zencad.disp(manipulator)
#manipulator.draw_sensivities_arrow()

body = ConvexBody2.from_points([
    #Point2(1,0.1),
    Point2(0.5,1),
    Point2(1.0,1),
    Point2(0.5,0),
])

body2 = ConvexBody2.from_points([
    #Point2(1,0.1),
    Point2(0.5+0.2,3-0.2),
    Point2(1.0+0.2,2.5-0.2),
    Point2(0.5+0.2,2-0.2),
])

draw_body2(body)
draw_body2(body2)

world = ConvexWorld2([body, body2])

for s in manipulator.sensor_points:
    s.interactive_projection_point = zencad.display(zencad.point3(0,0))
    #s.line_interactive = zencad.display(
    #    zencad.interactive.line(p1=(0,0), p2=(-1,-1))
    #)

P21 = [2,1.5]
P22 = [2.1,0.5]
P23 = [2.5,0]
P24 = [1,0]
P25 = [2,1.5]
P26 = [1.5,3]

zencad.display(zencad.point3(P21))
zencad.display(zencad.point3(P22))
zencad.display(zencad.point3(P23))
zencad.display(zencad.point3(P24))
zencad.display(zencad.point3(P25))
zencad.display(zencad.point3(P26))

start_time = time.time()
def animate(wdg):
    t = time.time() - start_time
    
    current1_pos = manipulator.half_sensor.global_location.translation()
    current1_pos = numpy.array([current1_pos.x, current1_pos.y])

    current2_pos = manipulator.final_sensor.global_location.translation()
    current2_pos = numpy.array([current2_pos.x, current2_pos.y])

#    t = 10

    TT = 5
    FT = 6*TT
    if (t%(FT)) < TT*1:
        target2_pos = numpy.array(P21)
    elif (t%(FT)) < TT*2:
        target2_pos = numpy.array(P22)
    elif (t%(FT)) < TT*3:
        target2_pos = numpy.array(P23)
    elif (t%(FT)) < TT*4:
        target2_pos = numpy.array(P24)
    elif (t%(FT)) < TT*5:
        target2_pos = numpy.array(P25)
    else:
        target2_pos = numpy.array(P26)

#    tgt1 = (target1_pos - current1_pos)  * 5
    tgt2 = (target2_pos - current2_pos)  * 3
 #   target1_speed = manipulator.half_sensor.global_to_local(tgt1)
    target2_speed = manipulator.final_sensor.global_to_local(tgt2)
    
    #j = manipulator.final_sensor.jacobi_matrix()
    #s = j.solve2(target_speed)
    #d = j.dot(s)
    #t = manipulator.final_sensor.local_to_global(d)
    #s = s.reshape((manipulator.N))

    sdim = len(manipulator.sensor_points) 
    qdim = manipulator.qdim()   
    
    jacobians = [ 
        #manipulator.half_sensor.expanded_jacobi_matrix(qdim),
        manipulator.final_sensor.expanded_jacobi_matrix(qdim),
    ]
    alphas = [
    #    1, 
        1
    ]
    velocities = [
    #    target1_speed.reshape([2,1]),
        target2_speed.reshape([2,1]),
    ] 

    #print(jacobians[0])

    for i, s in enumerate(manipulator.sensor_points):
        center = s.center_as_point()
        proj_to_nearest = s.projection_to(world)
        diff = proj_to_nearest - center
        diffnorm = diff.bulk_norm()
        udiff = diff / diffnorm
        L = 0.3
        barrier_value = shotki_barrier(b=2, l=L)(diffnorm)
        alpha = alpha_function(l=L, k=0.5)(diffnorm) + 0.001
        
#        if i % 4 == 3:
 #           alpha = alpha * 20

        if alpha != 0:
            v = numpy.array([udiff.x,udiff.y], dtype=numpy.float64).reshape((2,1))
            alphas.append(alpha)
            v = s.global_to_local(v)
            u = v / numpy.linalg.norm(v)
            P = numpy.array([
                u[0]*u[0], u[0]*u[1],
                u[1]*u[0], u[1]*u[1],
            ]).reshape((2,2))
            J = s.expanded_jacobi_matrix(qdim)
            PJ = Jacobian(numpy.matmul(P, J.matrix))
            jacobians.append(PJ)
            velocities.append(-v*barrier_value)

    prepare_q = numpy.diag([0.1] * qdim)
    gamma = numpy.array([0.01,0.01,0.01,0.01]).reshape((qdim,1)) * 0
    #prepare_q[qdim-1,qdim-1] = 1

    for i in range(len(velocities)):
        n = numpy.linalg.norm(velocities[i])
        V = 2
        if n > V:
            velocities[i] = velocities[i] / n * V

    q = solve_2d_velocity_system(jacobians, velocities, alphas, prepare_q, gamma)
    q = q.reshape((manipulator.N))

    qn = numpy.linalg.norm(q)
    #q = q / qn
    #print(q)
    manipulator.apply_speed_control(q)

    for s in manipulator.sensor_points:
        trans = s.global_location.translation()
        p = Point2(trans.x, trans.y)
        pp = world.point_projection(p)
        s.interactive_projection_point.relocate(zencad.move(pp.x, pp.y))
        #s.line_interactive.set_points(p1=(p.x,p.y), p2=(pp.x, pp.y))
        #s.line_interactive.redisplay()


zencad.show(animate = animate)
animate(None)
zencad.show()