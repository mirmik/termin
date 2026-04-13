#!/usr/bin/env python3
import time

from termin.zencad_adapter import *
from termin.barrier import *
from termin.ga201.line import Line2
from termin.ga201.point import Point2
from termin.ga201.motor import Motor2
from termin.ga201.join import join_point_point, oriented_distance
from termin.ga201.convex_body import ConvexBody2, ConvexWorld2
import math
import zencad
import pickle
import rxsignal
import rxsignal.rxmqtt

zencad.disable_lazy()

publisher = rxsignal.rxmqtt.mqtt_rxclient()

zencad.set_default_point_color(zencad.Color(0,0,0))
zencad.set_default_wire_color(zencad.Color(0,0,0))
#zencad.set_default_border_color(zencad.Color(1,1,1))

class Jacobian:
    def __init__(self, matrix):
        self.matrix = matrix

    def scale(self, a):
        return Jacobian(self.matrix * a)

    def __str__(self):
        return str(self.matrix)

    def solve(self, vector):
        p = numpy.linalg.pinv(self.matrix)
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

def solve_2d_velocity_system(jacobians, velocities, alphas, prepare_q, gamma, projectors):
    qdim = jacobians[0].qdim()
    sdim = len(jacobians)

    b = numpy.zeros((qdim,1), dtype=numpy.float64)
    for i in range(sdim):
        D = jacobians[i].T().dot( projectors[i] @ velocities[i])
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
            SensorPoint(location=zencad.move(0,l*1/8,0)),
            SensorPoint(location=zencad.move(0,l*2/8,0)),
            SensorPoint(location=zencad.move(0,l*3/8,0)),
            SensorPoint(location=zencad.move(0,l*4/8,0)),
            SensorPoint(location=zencad.move(0,l*5/8,0)),
            SensorPoint(location=zencad.move(0,l*6/8,0)),
            SensorPoint(location=zencad.move(0,l*7/8,0)),
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

    def coords(self):
        return [r.coord for r in self.rots]

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
    Point2(1.0+0.2,2.5-0.6),
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

zencad.display(zencad.segment(zencad.point3(P21), zencad.point3(P22)))
zencad.display(zencad.segment(zencad.point3(P22), zencad.point3(P23)))
zencad.display(zencad.segment(zencad.point3(P23), zencad.point3(P24)))
zencad.display(zencad.segment(zencad.point3(P24), zencad.point3(P25)))
zencad.display(zencad.segment(zencad.point3(P25), zencad.point3(P26)))

last_q = numpy.array([0,0,0,0])
start_time = time.time()
def animate(wdg):
    global last_q
    t = time.time() - start_time
    if (t < 1):
        return
    
    current1_pos = manipulator.half_sensor.global_location.translation()
    current1_pos = numpy.array([current1_pos.x, current1_pos.y])

    current2_pos = manipulator.final_sensor.global_location.translation()
    current2_pos = numpy.array([current2_pos.x, current2_pos.y])

#    t = 10

    P = False
    TT = 4
    FT = 6*TT
    if (t%(FT)) < TT*1:
        k = (TT*1 - (t%(FT))) / TT if P else 1
        target2_pos = (1-k)*numpy.array(P21) + k*numpy.array(P26)
    elif (t%(FT)) < TT*2:
        k = (TT*2 - (t%(FT))) / TT if P else 1
        target2_pos = (1-k)*numpy.array(P22) + k*numpy.array(P21)
    elif (t%(FT)) < TT*3:
        k = (TT*3 - (t%(FT))) / TT if P else 1
        target2_pos = (1-k)*numpy.array(P23) + k*numpy.array(P22)
    elif (t%(FT)) < TT*4:
        k = (TT*4 - (t%(FT))) / TT if P else 1
        target2_pos = (1-k)*numpy.array(P24) + k*numpy.array(P23)
    elif (t%(FT)) < TT*5:
        k = (TT*5 - (t%(FT))) / TT if P else 1
        target2_pos = (1-k)*numpy.array(P25) + k*numpy.array(P24)
    else:
        k = (TT*6 - (t%(FT))) / TT if P else 1
        target2_pos = (1-k)*numpy.array(P26) + k*numpy.array(P25)

    pos_error = target2_pos - current2_pos
    abs_pos_error = numpy.linalg.norm(pos_error)
    publisher.publish("pos_error_norm", abs_pos_error)

    publisher.publish("posout", current2_pos)

    tgt2 = (target2_pos - current2_pos)  * 3
    target2_speed = manipulator.final_sensor.global_to_local(tgt2)
    
    III = numpy.diag([1,1])

    sdim = len(manipulator.sensor_points) 
    qdim = manipulator.qdim()   
    
    jacobians = [ 
        manipulator.final_sensor.expanded_jacobi_matrix(qdim),
    ]
    alphas = [
        1
    ]
    barrier_alphas = []
    velocities = [
    #    target1_speed.reshape([2,1]),
        target2_speed.reshape([2,1]),
    ] 
    projectors = [III]

    outJ = manipulator.final_sensor.expanded_jacobi_matrix(qdim).matrix
    outJp = numpy.linalg.pinv(outJ)
    NullProjector = numpy.diag([1,1,1,1]) - outJp@outJ
    AntiNullProjector = outJp@outJ


    for i, s in enumerate(manipulator.sensor_points):
        center = s.center_as_point()
        proj_to_nearest = s.projection_to(world)
        diff = proj_to_nearest - center
        diffnorm = diff.bulk_norm()
        udiff = diff / diffnorm
        L2= 0.4
        #barrier_value = shotki_barrier(b=0.2, l=L)(diffnorm)
        barrier_value2 = shotki_barrier(b=2, l=L2)(diffnorm) * 2
        #alpha = alpha_function(l=L, k=0)(diffnorm) * 0 + 0.0000
        alpha2 = alpha_function(l=L2, k=0)(diffnorm) * 2 + 0.00000
        
#        if i % 4 == 3:
 #           alpha = alpha * 20

        # if alpha != 0:
        #     v = numpy.array([udiff.x,udiff.y], dtype=numpy.float64).reshape((2,1))
        #     v = s.global_to_local(v)
        #     u = v / numpy.linalg.norm(v)
        #     P = numpy.array([
        #         u[0]*u[0], u[0]*u[1],
        #         u[1]*u[0], u[1]*u[1],
        #     ]).reshape((2,2))
        #     J = s.expanded_jacobi_matrix(qdim)
        #     PJ = Jacobian(numpy.matmul(P, J.matrix))
        #     alphas.append(alpha)

        if alpha2 != 0:
            v = numpy.array([udiff.x,udiff.y], dtype=numpy.float64).reshape((2,1))
            v = s.global_to_local(v)
            u = v / numpy.linalg.norm(v)
            P = numpy.array([
                u[0]*u[0], u[0]*u[1],
                u[1]*u[0], u[1]*u[1],
            ]).reshape((2,2))
            J = s.expanded_jacobi_matrix(qdim)
            PJ = Jacobian(numpy.matmul(P, J.matrix))
            PJN = Jacobian(numpy.matmul(PJ.matrix, NullProjector))
            alphas.append(alpha2)
            jacobians.append(PJN)
            projectors.append(P)
            velocities.append(-v*barrier_value2)
        barrier_alphas.append(barrier_value2)

    publisher.publish("barrier", barrier_alphas)
    
    # betta
    prepare_q = numpy.diag([0.5] * qdim)
    prepare_q = NullProjector @ prepare_q
    prepare_q = prepare_q.T @ prepare_q

    prepare_q2 = numpy.diag([0.5] * qdim)
    prepare_q2 = NullProjector @ prepare_q2
    prepare_q2 = prepare_q2.T @ prepare_q2

    prepare_q_zero = numpy.diag([0.5] * qdim)
    prepare_q_zero = AntiNullProjector @ prepare_q_zero
    prepare_q_zero = prepare_q_zero.T @ prepare_q_zero

    gamma1 = prepare_q @ (
        numpy.array([
        0.8 + math.pi/2-manipulator.rots[2].coord,
        0.00,
        -manipulator.rots[2].coord,
        -manipulator.rots[3].coord]).reshape((qdim,1))
        )

    gamma2 = prepare_q2 @ (
        + last_q.reshape((qdim,1))
        )

    gamma3 = prepare_q_zero @ ( #numpy.array([1,1,1,1]).reshape((qdim,1))
        + last_q.reshape((qdim,1))
        )

    for i in range(len(velocities)):
        n = numpy.linalg.norm(velocities[i])
        V = 2
        if n > V:
            velocities[i] = velocities[i] / n * V

    q = solve_2d_velocity_system(jacobians, velocities, alphas, prepare_q + prepare_q2 + prepare_q_zero, 
        gamma1+gamma2+gamma3, projectors)
    q = q.reshape((manipulator.N))

    qn = numpy.linalg.norm(q)
    #q = q / qn
    #print(q)
    manipulator.apply_speed_control(q)

    accels = last_q - q
    last_q = q

    coords = manipulator.coords()
    publisher.publish("vels", q)
    publisher.publish("accels", accels)
    publisher.publish("coords", coords)

    for s in manipulator.sensor_points:
        trans = s.global_location.translation()
        p = Point2(trans.x, trans.y)
        pp = world.point_projection(p)
        s.interactive_projection_point.relocate(zencad.move(pp.x, pp.y))
        #s.line_interactive.set_points(p1=(p.x,p.y), p2=(pp.x, pp.y))
        #s.line_interactive.redisplay()

def preanimate(wdg, anthr):
    print(wdg, anthr)
    wdg.enable_axis_triedron(False)
    wdg.enable_axis_biedron(True, colors=[zencad.black, zencad.black])
    wdg.set_background_color(
        zencad.Color(1,1,1,1))


zencad.show(animate = animate, preanimate = preanimate)
animate(None)
zencad.show()