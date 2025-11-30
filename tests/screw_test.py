import unittest
from termin.ga201.motor import Motor2
from termin.ga201.screw import Screw2 as GA201_Screw2
from termin.geombase.screw import Screw2, Screw3
from termin.geombase.pose2 import Pose2
from termin.geombase.pose3 import Pose3
import math
import numpy


def early(a, b):
    if abs(a.x - b.x) > 0.0001:
        return False
    if abs(a.y - b.y) > 0.0001:
        return False
    if abs(a.z - b.z) > 0.0001:
        return False
    return True

def screw_equal(a, b):
    if abs(a.moment() - b.moment()) > 0.0001:
        return False
    if abs(a.vector()[0] - b.vector()[0]) > 0.0001:
        return False
    if abs(a.vector()[1] - b.vector()[1]) > 0.0001:
        return False
    return True

class TransformationProbe(unittest.TestCase):
    def test_moment_carry(self):
        motor = Motor2.translation(1, 0)
        screw = GA201_Screw2(m=1, v=[0,0])
        carried = screw.kinematic_carry(motor)
        invcarried = carried.kinematic_carry(motor.inverse())
        invcarried2 = carried.inverse_kinematic_carry(motor)
        self.assertEqual(carried.moment(), 1)
        self.assertTrue((carried.vector() == numpy.array([0,-1])).all())
        self.assertTrue(screw_equal(invcarried, screw))
        self.assertTrue(screw_equal(invcarried2, screw))

    def test_vectory_carry(self):
        motor = Motor2.translation(1, 0)
        screw = GA201_Screw2(m=0, v=[0,1])
        carried = screw.kinematic_carry(motor)
        self.assertEqual(carried.moment(), 0)
        self.assertTrue((carried.vector() == numpy.array([0,1])).all())

    def test_vectorx_carry(self):
        motor = Motor2.translation(1, 0)
        screw = GA201_Screw2(m=0, v=[1,0])
        carried = screw.kinematic_carry(motor)
        self.assertEqual(carried.moment(), 0)
        self.assertTrue((carried.vector() == numpy.array([1,0])).all())

    def test_moment_carry_with_rotation(self):
        motor = Motor2.translation(1, 0) * Motor2.rotation(math.pi/2)
        screw = GA201_Screw2(m=1, v=[0,0])
        carried = screw.kinematic_carry(motor)
        invcarried = carried.kinematic_carry(motor.inverse())
        invcarried2 = carried.inverse_kinematic_carry(motor)
        self.assertEqual(carried.moment(), 1)
        self.assertTrue((carried.vector() == numpy.array([0,-1])).all())
        self.assertTrue(screw_equal(invcarried, screw))
        self.assertTrue(screw_equal(invcarried2, screw))

    def test_vectory_carry_with_rotation(self):
        motor = Motor2.translation(1, 0) * Motor2.rotation(math.pi/2)
        screw = GA201_Screw2(m=0, v=[0,1])
        carried = screw.kinematic_carry(motor)
        self.assertEqual(carried.moment(), 0)
        self.assertTrue(screw_equal(carried, GA201_Screw2(m=0, v=[-1,0])))

    def test_vectorx_carry_with_rotation(self):
        motor = Motor2.translation(1, 0) * Motor2.rotation(math.pi/2)
        screw = GA201_Screw2(m=0, v=[1,0])
        carried = screw.kinematic_carry(motor)
        self.assertEqual(carried.moment(), 0)
        self.assertTrue(screw_equal(carried, GA201_Screw2(m=0, v=[0,1])))


class Screw2Tests(unittest.TestCase):
    """Tests for geombase.Screw2"""
    
    def test_screw2_creation(self):
        screw = Screw2(ang=numpy.array([1.0]), lin=numpy.array([2.0, 3.0]))
        self.assertEqual(screw.moment(), 1.0)
        self.assertTrue((screw.vector() == numpy.array([2.0, 3.0])).all())

    def test_screw2_kinematic_carry(self):
        screw = Screw2(ang=numpy.array([1.0]), lin=numpy.array([0.0, 0.0]))
        arm = numpy.array([1.0, 0.0])
        carried = screw.kinematic_carry(arm)
        self.assertAlmostEqual(carried.moment(), 1.0)
        self.assertAlmostEqual(carried.vector()[0], 0.0, places=5)
        self.assertAlmostEqual(carried.vector()[1], -1.0, places=5)

    def test_screw2_force_carry(self):
        screw = Screw2(ang=numpy.array([1.0]), lin=numpy.array([1.0, 0.0]))
        arm = numpy.array([1.0, 0.0])
        carried = screw.force_carry(arm)
        self.assertAlmostEqual(carried.moment(), 1.0, places=5)
        self.assertTrue((carried.vector() == numpy.array([1.0, 0.0])).all())

    def test_screw2_scalar_multiplication(self):
        screw = Screw2(ang=numpy.array([2.0]), lin=numpy.array([1.0, 2.0]))
        scaled = screw * 3.0
        self.assertAlmostEqual(scaled.moment(), 6.0)
        self.assertTrue((scaled.vector() == numpy.array([3.0, 6.0])).all())

    def test_screw2_addition(self):
        screw1 = Screw2(ang=numpy.array([1.0]), lin=numpy.array([1.0, 2.0]))
        screw2 = Screw2(ang=numpy.array([2.0]), lin=numpy.array([3.0, 4.0]))
        result = screw1 + screw2
        self.assertAlmostEqual(result.moment(), 3.0)
        self.assertTrue((result.vector() == numpy.array([4.0, 6.0])).all())

    def test_screw2_subtraction(self):
        screw1 = Screw2(ang=numpy.array([5.0]), lin=numpy.array([10.0, 8.0]))
        screw2 = Screw2(ang=numpy.array([2.0]), lin=numpy.array([3.0, 2.0]))
        result = screw1 - screw2
        self.assertAlmostEqual(result.moment(), 3.0)
        self.assertTrue((result.vector() == numpy.array([7.0, 6.0])).all())

    def test_screw2_transform_by_pose(self):
        screw = Screw2(ang=numpy.array([1.0]), lin=numpy.array([1.0, 0.0]))
        pose = Pose2(ang=math.pi/2, lin=numpy.array([0.0, 0.0]))
        transformed = screw.transform_by(pose)
        self.assertAlmostEqual(transformed.moment(), 1.0)
        self.assertAlmostEqual(transformed.vector()[0], 0.0, places=5)
        self.assertAlmostEqual(transformed.vector()[1], 1.0, places=5)

    def test_screw2_transform_as_twist(self):
        # Твист с угловой скоростью 1 и линейной скоростью [1, 0]
        screw = Screw2(ang=numpy.array([1.0]), lin=numpy.array([1.0, 0.0]))
        pose = Pose2(ang=0.0, lin=numpy.array([1.0, 0.0]))
        transformed = screw.transform_as_twist_by(pose)
        self.assertAlmostEqual(transformed.moment(), 1.0)
        # v' = R*v + p × ω = [1,0] + [1,0] × 1 = [1,0] + [0,1] = [1, 1]
        self.assertAlmostEqual(transformed.vector()[0], 1.0, places=5)
        self.assertAlmostEqual(transformed.vector()[1], 1.0, places=5)

    def test_screw2_transform_as_wrench(self):
        # Ренч с моментом 1 и силой [1, 0]
        screw = Screw2(ang=numpy.array([1.0]), lin=numpy.array([1.0, 0.0]))
        pose = Pose2(ang=0.0, lin=numpy.array([1.0, 0.0]))
        transformed = screw.transform_as_wrench_by(pose)
        # M' = M + p × F = 1 + 1*0 - 0*1 = 1
        self.assertAlmostEqual(transformed.moment(), 1.0, places=5)
        self.assertAlmostEqual(transformed.vector()[0], 1.0, places=5)
        self.assertAlmostEqual(transformed.vector()[1], 0.0, places=5)

    def test_screw2_twist_local_to_global(self):
        """Проверка преобразования твиста из локальной системы в глобальную.
        
        Пусть тело расположено в точке (1, 0) с поворотом 90° (π/2).
        В локальной системе тела твист: ω=1, v=[1, 0] (движется вдоль локальной оси X).
        В глобальной системе:
        - угловая скорость остается ω=1
        - линейная скорость: v_global = R*v_local + p × ω
          где p = [1, 0], v_local = [1, 0], R - поворот на 90°
        - R*[1,0] = [0, 1]
        - p × ω = [1, 0] × 1 = [0, 1]
        - v_global = [0, 1] + [0, 1] = [0, 2]
        """
        # Локальный твист: вращение ω=1, движение вдоль локальной X
        local_twist = Screw2(ang=numpy.array([1.0]), lin=numpy.array([1.0, 0.0]))
        # Поза тела: смещение на (1, 0) и поворот на 90°
        body_pose = Pose2(ang=math.pi/2, lin=numpy.array([1.0, 0.0]))
        # Преобразуем в глобальную систему
        global_twist = local_twist.transform_as_twist_by(body_pose)
        
        # Угловая скорость не меняется
        self.assertAlmostEqual(global_twist.moment(), 1.0, places=5)
        # Линейная скорость в глобальной системе
        self.assertAlmostEqual(global_twist.vector()[0], 0.0, places=5)
        self.assertAlmostEqual(global_twist.vector()[1], 2.0, places=5)

    def test_screw2_twist_local_to_global_2(self):
        
        local_twist = Screw2(ang=numpy.array([1.0]), lin=numpy.array([0.0, 0.0]))
        body_pose = Pose2(ang=0, lin=numpy.array([1.0, 0.0]))
        global_twist = local_twist.transform_as_twist_by(body_pose)

        self.assertAlmostEqual(global_twist.moment(), 1.0, places=5)
        self.assertAlmostEqual(global_twist.vector()[0], 0.0, places=5)
        self.assertAlmostEqual(global_twist.vector()[1], 1.0, places=5)

    def test_screw2_twist_pure_rotation_at_origin(self):
        """Твист чистого вращения в начале координат не меняется при трансформации."""
        local_twist = Screw2(ang=numpy.array([2.0]), lin=numpy.array([0.0, 0.0]))
        body_pose = Pose2(ang=math.pi/4, lin=numpy.array([0.0, 0.0]))
        global_twist = local_twist.transform_as_twist_by(body_pose)
        
        self.assertAlmostEqual(global_twist.moment(), 2.0, places=5)
        self.assertAlmostEqual(global_twist.vector()[0], 0.0, places=5)
        self.assertAlmostEqual(global_twist.vector()[1], 0.0, places=5)


class Screw3Tests(unittest.TestCase):
    """Tests for geombase.Screw3"""
    
    def test_screw3_creation(self):
        screw = Screw3(ang=numpy.array([1.0, 0.0, 0.0]), lin=numpy.array([0.0, 1.0, 0.0]))
        self.assertTrue((screw.moment() == numpy.array([1.0, 0.0, 0.0])).all())
        self.assertTrue((screw.vector() == numpy.array([0.0, 1.0, 0.0])).all())

    def test_screw3_kinematic_carry(self):
        # Твист с чистой угловой скоростью вокруг Z
        screw = Screw3(ang=numpy.array([0.0, 0.0, 1.0]), lin=numpy.array([0.0, 0.0, 0.0]))
        arm = numpy.array([1.0, 0.0, 0.0])
        carried = screw.kinematic_carry(arm)
        # v' = v + ω × r = [0,0,0] + [0,0,1] × [1,0,0] = [0, 1, 0]
        self.assertTrue((carried.moment() == numpy.array([0.0, 0.0, 1.0])).all())
        self.assertAlmostEqual(carried.vector()[0], 0.0, places=5)
        self.assertAlmostEqual(carried.vector()[1], 1.0, places=5)
        self.assertAlmostEqual(carried.vector()[2], 0.0, places=5)

    def test_screw3_force_carry(self):
        # Ренч с чистой силой
        screw = Screw3(ang=numpy.array([0.0, 0.0, 0.0]), lin=numpy.array([0.0, 0.0, 1.0]))
        arm = numpy.array([1.0, 0.0, 0.0])
        carried = screw.force_carry(arm)
        # M' = M - r × F = [0,0,0] - [1,0,0] × [0,0,1] = [0, 1, 0]
        self.assertAlmostEqual(carried.moment()[0], 0.0, places=5)
        self.assertAlmostEqual(carried.moment()[1], 1.0, places=5)
        self.assertAlmostEqual(carried.moment()[2], 0.0, places=5)
        self.assertTrue((carried.vector() == numpy.array([0.0, 0.0, 1.0])).all())

    def test_screw3_scalar_multiplication(self):
        screw = Screw3(ang=numpy.array([1.0, 2.0, 3.0]), lin=numpy.array([4.0, 5.0, 6.0]))
        scaled = screw * 2.0
        self.assertTrue((scaled.moment() == numpy.array([2.0, 4.0, 6.0])).all())
        self.assertTrue((scaled.vector() == numpy.array([8.0, 10.0, 12.0])).all())

    def test_screw3_transform_by_pose(self):
        # Поворот вокруг Z на 90 градусов
        screw = Screw3(ang=numpy.array([1.0, 0.0, 0.0]), lin=numpy.array([1.0, 0.0, 0.0]))
        pose = Pose3.rotateZ(math.pi/2)
        transformed = screw.transform_by(pose)
        self.assertAlmostEqual(transformed.moment()[0], 0.0, places=5)
        self.assertAlmostEqual(transformed.moment()[1], 1.0, places=5)
        self.assertAlmostEqual(transformed.moment()[2], 0.0, places=5)
        self.assertAlmostEqual(transformed.vector()[0], 0.0, places=5)
        self.assertAlmostEqual(transformed.vector()[1], 1.0, places=5)
        self.assertAlmostEqual(transformed.vector()[2], 0.0, places=5)

    def test_screw3_transform_as_twist(self):
        # Твист с угловой скоростью вокруг Z
        screw = Screw3(ang=numpy.array([0.0, 0.0, 1.0]), lin=numpy.array([0.0, 0.0, 0.0]))
        pose = Pose3.translation(1.0, 0.0, 0.0)
        transformed = screw.transform_as_twist_by(pose)
        # v' = v + p × ω = [0,0,0] + [1,0,0] × [0,0,1] = [0, -1, 0]
        self.assertTrue((transformed.moment() == numpy.array([0.0, 0.0, 1.0])).all())
        self.assertAlmostEqual(transformed.vector()[0], 0.0, places=5)
        self.assertAlmostEqual(transformed.vector()[1], -1.0, places=5)
        self.assertAlmostEqual(transformed.vector()[2], 0.0, places=5)

    def test_screw3_transform_as_wrench(self):
        # Ренч с чистой силой по Z
        screw = Screw3(ang=numpy.array([0.0, 0.0, 0.0]), lin=numpy.array([0.0, 0.0, 1.0]))
        pose = Pose3.translation(1.0, 0.0, 0.0)
        transformed = screw.transform_as_wrench_by(pose)
        # M' = M + p × F = [0,0,0] + [1,0,0] × [0,0,1] = [0, -1, 0]
        self.assertAlmostEqual(transformed.moment()[0], 0.0, places=5)
        self.assertAlmostEqual(transformed.moment()[1], -1.0, places=5)
        self.assertAlmostEqual(transformed.moment()[2], 0.0, places=5)
        self.assertTrue((transformed.vector() == numpy.array([0.0, 0.0, 1.0])).all())

    def test_screw3_as_pose3(self):
        # Малый твист -> Pose3
        screw = Screw3(ang=numpy.array([0.0, 0.0, 0.1]), lin=numpy.array([1.0, 0.0, 0.0]))
        pose = screw.as_pose3()
        self.assertIsInstance(pose, Pose3)
        # Проверяем, что линейная часть сохранилась
        self.assertAlmostEqual(pose.lin[0], 1.0, places=5)
        self.assertAlmostEqual(pose.lin[1], 0.0, places=5)
        self.assertAlmostEqual(pose.lin[2], 0.0, places=5)

    def test_screw3_inverse_transform(self):
        screw = Screw3(ang=numpy.array([1.0, 0.0, 0.0]), lin=numpy.array([0.0, 1.0, 0.0]))
        pose = Pose3.rotateZ(math.pi/2)
        transformed = screw.transform_by(pose)
        back = transformed.inverse_transform_by(pose)
        # Должны вернуться к исходному винту
        self.assertAlmostEqual(back.moment()[0], 1.0, places=5)
        self.assertAlmostEqual(back.moment()[1], 0.0, places=5)
        self.assertAlmostEqual(back.moment()[2], 0.0, places=5)
        self.assertAlmostEqual(back.vector()[0], 0.0, places=5)
        self.assertAlmostEqual(back.vector()[1], 1.0, places=5)
        self.assertAlmostEqual(back.vector()[2], 0.0, places=5)

    def test_screw3_twist_local_to_global(self):
        """Проверка преобразования твиста из локальной системы в глобальную для Screw3.
        
        Пусть тело расположено в точке (1, 0, 0) без поворота.
        В локальной системе твист: ω=[0,0,1], v=[0,0,0] (чистое вращение вокруг Z).
        В глобальной системе:
        - угловая скорость: ω_global = R*ω = [0,0,1] (без поворота)
        - линейная скорость: v_global = R*v + p × ω = [0,0,0] + [1,0,0] × [0,0,1]
          = [0,-1,0]
        """
        local_twist = Screw3(ang=numpy.array([0.0, 0.0, 1.0]), lin=numpy.array([0.0, 0.0, 0.0]))
        body_pose = Pose3.translation(1.0, 0.0, 0.0)
        global_twist = local_twist.transform_as_twist_by(body_pose)
        
        # Угловая скорость не изменилась
        self.assertAlmostEqual(global_twist.moment()[0], 0.0, places=5)
        self.assertAlmostEqual(global_twist.moment()[1], 0.0, places=5)
        self.assertAlmostEqual(global_twist.moment()[2], 1.0, places=5)
        # Линейная скорость из-за вращения вокруг смещенной точки
        self.assertAlmostEqual(global_twist.vector()[0], 0.0, places=5)
        self.assertAlmostEqual(global_twist.vector()[1], -1.0, places=5)
        self.assertAlmostEqual(global_twist.vector()[2], 0.0, places=5)

    def test_screw3_twist_with_rotation(self):
        """Твист с поворотом тела: проверяем, что угловая скорость поворачивается."""
        # Локальный твист: вращение вокруг локальной оси X
        local_twist = Screw3(ang=numpy.array([1.0, 0.0, 0.0]), lin=numpy.array([0.0, 0.0, 0.0]))
        # Тело повернуто на 90° вокруг Z
        body_pose = Pose3.rotateZ(math.pi/2)
        global_twist = local_twist.transform_as_twist_by(body_pose)
        
        # Локальная ось X → глобальная ось Y
        self.assertAlmostEqual(global_twist.moment()[0], 0.0, places=5)
        self.assertAlmostEqual(global_twist.moment()[1], 1.0, places=5)
        self.assertAlmostEqual(global_twist.moment()[2], 0.0, places=5)