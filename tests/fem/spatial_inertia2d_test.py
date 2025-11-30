import numpy as np
from termin.fem.inertia2d import SpatialInertia2D
from termin.geombase.pose2 import Pose2

def test_spatial_inertia2d_add():
    # Два тела с разными центрами масс
    I1 = SpatialInertia2D(2.0, 1.0, [0.0, 0.0])
    I2 = SpatialInertia2D(3.0, 2.0, [1.0, 0.0])
    I_sum = I1 + I2
    # Проверяем массу
    assert np.isclose(I_sum.m, 5.0)
    # Проверяем центр масс
    assert np.allclose(I_sum.c, [0.6, 0.0])
    # Проверяем момент инерции с учетом Штейнера
    # I = 1 + 2 + 2*0^2 + 3*0.4^2 = 3 + 0.48 = 3.48
    d1 = np.array([0.0, 0.0]) - np.array([0.6, 0.0])
    d2 = np.array([1.0, 0.0]) - np.array([0.6, 0.0])
    expected_I = 1.0 + 2.0 + 2.0 * np.dot(d1, d1) + 3.0 * np.dot(d2, d2)
    assert np.isclose(I_sum.I_com, expected_I)

def test_spatial_inertia2d_transform():
    # Тело с центром масс не в начале
    I = SpatialInertia2D(1.0, 2.0, [1.0, 2.0])
    pose = Pose2(ang=np.pi/2, lin=np.array([3.0, 4.0]))  # Поворот на 90° и сдвиг
    I_tr = I.transform_by(pose)
    # Центр масс должен повернуться и сместиться
    expected_c = pose.transform_point([1.0, 2.0])
    assert np.allclose(I_tr.c, expected_c)
    # Момент инерции не меняется
    assert np.isclose(I_tr.I_com, 2.0)

def test_spatial_inertia2d_zero_mass():
    # Сумма двух нулевых масс
    I1 = SpatialInertia2D(0.0, 0.0, [0.0, 0.0])
    I2 = SpatialInertia2D(0.0, 0.0, [1.0, 1.0])
    I_sum = I1 + I2
    assert np.isclose(I_sum.m, 0.0)
    assert np.allclose(I_sum.c, [0.0, 0.0])
    assert np.isclose(I_sum.I_com, 0.0)
