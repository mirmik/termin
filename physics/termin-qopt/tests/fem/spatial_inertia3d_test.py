import numpy as np
from termin.fem.inertia3d import SpatialInertia3D


def test_spatial_inertia3d_add():
    # Два тела с разными центрами масс и тензорами
    I1 = SpatialInertia3D.from_matrix(mass=2.0, inertia=np.eye(3), com=[0.0, 0.0, 0.0])
    I2 = SpatialInertia3D.from_matrix(mass=3.0, inertia=2*np.eye(3), com=[1.0, 0.0, 0.0])
    I_sum = I1 + I2
    # Проверяем массу
    assert np.isclose(I_sum.m, 5.0)
    # Проверяем центр масс
    assert np.allclose(I_sum.c, [0.6, 0.0, 0.0])
    # Проверяем тензор инерции с учетом Штейнера
    d1 = np.array([0.0, 0.0, 0.0]) - np.array([0.6, 0.0, 0.0])
    d2 = np.array([1.0, 0.0, 0.0]) - np.array([0.6, 0.0, 0.0])
    skew1 = np.array([[0, -d1[2], d1[1]], [d1[2], 0, -d1[0]], [-d1[1], d1[0], 0]])
    skew2 = np.array([[0, -d2[2], d2[1]], [d2[2], 0, -d2[0]], [-d2[1], d2[0], 0]])
    expected_I = np.eye(3) + 2*np.eye(3) + 2.0 * skew1 @ skew1.T + 3.0 * skew2 @ skew2.T
    assert np.allclose(I_sum.Ic, expected_I)
