import numpy as np
from termin.fem.inertia3d import SpatialInertia3D
from termin.geombase.pose3 import Pose3

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

# def test_spatial_inertia3d_transform():
#     # Тело с центром масс не в начале
#     I = SpatialInertia3D(1.0, np.eye(3), [1.0, 2.0, 3.0])
#     # Поворот на 90° вокруг оси Z и сдвиг
#     angle = np.pi/2
#     # Кватернион для поворота на 90° вокруг оси Z: [cos(a/2), 0, 0, sin(a/2)]
#     qw = np.cos(angle/2)
#     qz = np.sin(angle/2)
#     quat = np.array([qw, 0.0, 0.0, qz])
#     pose = Pose3(quat, np.array([3.0, 4.0, 5.0]))
#     I_tr = I.transform_by(pose)
#     # Центр масс должен повернуться и сместиться
#     expected_c = pose.transform_point([1.0, 2.0, 3.0])
#     assert np.allclose(I_tr.c, expected_c)
#     # Тензор инерции должен повернуться
#     Rz = pose.rotation_matrix()
#     expected_I = Rz @ np.eye(3) @ Rz.T + 1.0 * np.array([[0, -expected_c[2], expected_c[1]], [expected_c[2], 0, -expected_c[0]], [-expected_c[1], expected_c[0], 0]]) @ np.array([[0, -expected_c[2], expected_c[1]], [expected_c[2], 0, -expected_c[0]], [-expected_c[1], expected_c[0], 0]]).T
#     assert np.allclose(I_tr.I_com, expected_I)

# def test_spatial_inertia3d_to_matrix():
#     I = SpatialInertia3D(2.0, np.eye(3), [1.0, -2.0, 3.0])
#     mat = I.to_matrix_vw_order()
#     c_skew = np.array([[0, -3.0, -2.0], [3.0, 0, -1.0], [2.0, 1.0, 0]])
#     upper_left = np.eye(3) + 2.0 * (c_skew @ c_skew.T)
#     upper_right = 2.0 * c_skew
#     lower_left = -2.0 * c_skew.T
#     lower_right = 2.0 * np.eye(3)
#     expected = np.block([
#         [upper_left, upper_right],
#         [lower_left, lower_right]
#     ])
#     assert np.allclose(mat, expected)

# def test_spatial_inertia3d_zero_mass():
#     I1 = SpatialInertia3D(0.0, np.zeros((3,3)), [0.0, 0.0, 0.0])
#     I2 = SpatialInertia3D(0.0, np.zeros((3,3)), [1.0, 1.0, 1.0])
#     I_sum = I1 + I2
#     assert np.isclose(I_sum.m, 0.0)
#     assert np.allclose(I_sum.c, [0.0, 0.0, 0.0])
#     assert np.allclose(I_sum.I_com, np.zeros((3,3)))
