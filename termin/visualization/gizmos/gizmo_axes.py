import numpy as np

from termin.mesh.mesh import CylinderMesh, ConeMesh, RingMesh
from termin.visualization.material import Material
from termin.visualization.entity import Entity
from termin.visualization.components import MeshRenderer
from termin.geombase.pose3 import Pose3
from termin.colliders import CapsuleCollider
from termin.colliders.collider_component import ColliderComponent
from termin.visualization.entity import InputComponent


# ---------- ВСПОМОГАТЕЛЬНАЯ МАТЕМАТИКА ----------

def closest_point_on_axis_from_ray(axis_point, axis_dir, ray_origin, ray_dir):
    """
    Находит ближайшую точку на прямой (axis_point + t * axis_dir) к лучу (ray_origin + s * ray_dir),
    возвращает параметр t и саму точку.
    """
    p = np.asarray(axis_point, dtype=np.float32)
    a = np.asarray(axis_dir, dtype=np.float32)
    o = np.asarray(ray_origin, dtype=np.float32)
    d = np.asarray(ray_dir, dtype=np.float32)

    a_norm = np.linalg.norm(a)
    if a_norm == 0:
        return 0.0, p.copy()
    a /= a_norm

    d_norm = np.linalg.norm(d)
    if d_norm == 0:
        return 0.0, p.copy()
    d /= d_norm

    w0 = p - o
    a_dot_d = np.dot(a, d)
    denom = 1.0 - a_dot_d * a_dot_d

    if float(np.abs(denom)) < 1e-6:
        t = -np.dot(w0, a)
        return t, p + a * t

    w0_dot_d = np.dot(w0, d)
    w0_dot_a = np.dot(w0, a)

    t = (a_dot_d * w0_dot_d - w0_dot_a) / denom
    point_on_axis = p + a * t
    return t, point_on_axis


def rotation_matrix_from_axis_angle(axis_vec: np.ndarray, angle: float) -> np.ndarray:
    """
    Строит матрицу поворота (три на три) вокруг произвольной оси.
    Ось задаётся в мировых координатах.
    """
    axis = np.asarray(axis_vec, dtype=float)
    n = np.linalg.norm(axis)
    if n == 0.0:
        return np.eye(3, dtype=float)
    axis /= n

    x, y, z = axis
    c = float(np.cos(angle))
    s = float(np.sin(angle))
    C = 1.0 - c

    return np.array(
        [
            [x * x * C + c,     x * y * C - z * s, x * z * C + y * s],
            [y * x * C + z * s, y * y * C + c,     y * z * C - x * s],
            [z * x * C - y * s, z * y * C + x * s, z * z * C + c],
        ],
        dtype=float,
    )


# ---------- ГРАФИЧЕСКИЕ ОБЪЕКТЫ ГИЗМО ----------

class GizmoArrow(Entity):
    """
    Стрелка гизмо для перемещения вдоль одной оси.
    Состоит из цилиндра (ствол) и конуса (наконечник).
    """

    def __init__(self, axis: str, length=1.0, color=(1.0, 0.0, 0.0, 1.0)):
        super().__init__(
            Pose3.identity(),
            name=f"gizmo_axis_{axis}",
            pickable=True,
            selectable=False
        )

        self.axis = axis
        shaft_len = length * 0.75
        head_len = length * 0.25

        shaft = CylinderMesh(radius=0.03, height=shaft_len, segments=24)
        head = ConeMesh(radius=0.06, height=head_len, segments=24)

        mat = Material(color=color)

        # цилиндр (ствол)
        shaft_ent = Entity(
            Pose3.translation(0, shaft_len * 0.5, 0),
            name=f"{axis}_shaft",
            pickable=True,
            selectable=False
        )
        shaft_ent.add_component(MeshRenderer(shaft, mat))
        self.shaft_ent = shaft_ent
        self.transform.add_child(shaft_ent.transform)

        # конус (наконечник)
        head_ent = Entity(
            Pose3.translation(0, shaft_len + head_len * 0.5, 0),
            name=f"{axis}_head",
            pickable=True,
            selectable=False
        )
        head_ent.add_component(MeshRenderer(head, mat))
        self.head_ent = head_ent
        self.transform.add_child(head_ent.transform)

        # ориентация оси:
        # базовая модель ориентирована вдоль +Y,
        # поворачиваем, чтобы она смотрела вдоль нужной мировой оси
        if axis == "x":
            # местная ось Y → мировая X
            self.transform.relocate(Pose3.rotateZ(-np.pi / 2.0))
        elif axis == "z":
            # местная ось Y → мировая Z
            self.transform.relocate(Pose3.rotateX(np.pi / 2.0))
        # для оси Y поворот не нужен


class GizmoRing(Entity):
    """
    Кольцо для гизмо вращения вокруг одной оси.
    Базовый меш лежит в XZ-плоскости, нормаль по +Y.
    Ориентацией transform доводим до нужной оси.
    """

    def __init__(self, axis: str, radius=1.2, thickness=0.05, color=(1.0, 1.0, 0.0, 1.0)):
        super().__init__(
            Pose3.identity(),
            name=f"gizmo_rot_{axis}",
            pickable=True,
            selectable=False
        )

        self.axis = axis

        ring_mesh = RingMesh(radius=radius, thickness=thickness, segments=48)
        mat = Material(color=color)

        ring_ent = Entity(
            Pose3.identity(),
            name=f"{axis}_ring",
            pickable=True,
            selectable=False
        )
        ring_ent.add_component(MeshRenderer(ring_mesh, mat))
        self.ring_ent = ring_ent
        self.transform.add_child(ring_ent.transform)

        # базовый RingMesh имеет нормаль (ось) вдоль +Y,
        # поворачиваем так же, как стрелки:
        if axis == "x":
            # нормаль Y → X
            self.transform.relocate(Pose3.rotateZ(-np.pi / 2.0))
        elif axis == "z":
            # нормаль Y → Z
            self.transform.relocate(Pose3.rotateX(np.pi / 2.0))
        # для оси Y поворот не нужен

        # коллайдер можно потом добавить более точный (тор)
        # пока оставим только меш для визуального пика


class GizmoEntity(Entity):
    """
    Общая сущность гизмо, которая содержит:
    - стрелки для перемещения
    - кольца для вращения
    """

    def __init__(self, size=1.0):
        super().__init__(
            Pose3.identity(),
            name="gizmo",
            pickable=True,
            selectable=False
        )

        # стрелки перемещения
        self.x = GizmoArrow("x", length=size, color=(1, 0, 0, 1))
        self.y = GizmoArrow("y", length=size, color=(0, 1, 0, 1))
        self.z = GizmoArrow("z", length=size, color=(0, 0, 1, 1))

        self.transform.add_child(self.x.transform)
        self.transform.add_child(self.y.transform)
        self.transform.add_child(self.z.transform)

        # кольца вращения (слегка больше по радиусу)
        ring_radius = size * 1.1
        ring_thickness = size * 0.03

        self.rx = GizmoRing("x", radius=ring_radius, thickness=ring_thickness, color=(1, 0.3, 0.3, 1))
        self.ry = GizmoRing("y", radius=ring_radius, thickness=ring_thickness, color=(0.3, 1, 0.3, 1))
        self.rz = GizmoRing("z", radius=ring_radius, thickness=ring_thickness, color=(0.3, 0.3, 1, 1))

        self.transform.add_child(self.rx.transform)
        self.transform.add_child(self.ry.transform)
        self.transform.add_child(self.rz.transform)


# ---------- КОНТРОЛЛЕР ПЕРЕМЕЩЕНИЯ ----------

class GizmoMoveController(InputComponent):
    """
    Контроллер перемещения объекта вдоль осей гизмо.
    Учитывает локальные оси гизмо, ближайшую точку на оси
    и смещение хватания.
    """

    def __init__(self, gizmo_entity: GizmoEntity, scene):
        super().__init__()
        self.gizmo = gizmo_entity
        self.scene = scene

        self.dragging = False
        self.active_axis = None

        self.axis_vec = None
        self.axis_point = None
        self.grab_offset = None

        self.start_target_pos = None

        self.target = None
        self.set_enabled(False)

    def set_target(self, target_entity: Entity | None):
        if target_entity is not None and target_entity.pickable is False:
            target_entity = None

        self.target = target_entity
        if self.target is None:
            self.set_enabled(False)
            return

        self.set_enabled(True)

        self.gizmo.transform.relocate_global(
            self.target.transform.global_pose()
        )

    def set_enabled(self, flag: bool):
        self.enabled = flag
        self.gizmo.set_visible(flag)

    def on_mouse_button(self, viewport, button, action, mods):
        print("GizmoMoveController.on_mouse_button", button, action)
        if button != 0:
            return

        x, y = viewport.window.handle.get_cursor_pos()

        if action == 1:  # нажали
            ray = viewport.screen_point_to_ray(x, y)
            if ray is None:
                return

            hit = self.scene.closest_to_ray(ray)
            if not hit:
                return

            name = hit.entity.name
            if name.startswith("gizmo_axis_"):
                axis = name.removeprefix("gizmo_axis_")
                self.start_drag(axis, viewport, x, y)
        else:
            # отпустили
            self.dragging = False
            self.active_axis = None
            self.axis_vec = None
            self.grab_offset = None
            self.start_target_pos = None

    def start_drag(self, axis: str, viewport, x: float, y: float):
        self.dragging = True
        self.active_axis = axis

        if self.target is None:
            return

        pose = self.target.transform.global_pose()
        self.start_target_pos = pose.lin.copy()

        # направление оси берём из transform гизмо
        self.axis_vec = self.get_axis_vector(axis)

        # ось проходит через стартовую позицию объекта
        self.axis_point = self.start_target_pos.copy()

        # вычисляем точку оси под курсором — здесь мы "схватились"
        ray = viewport.screen_point_to_ray(x, y)
        if ray is None or self.axis_vec is None:
            return

        _, axis_hit_point = closest_point_on_axis_from_ray(
            axis_point=self.axis_point,
            axis_dir=self.axis_vec,
            ray_origin=ray.origin,
            ray_dir=ray.direction
        )

        # пользователь мог схватиться не за origin, учитываем смещение
        self.grab_offset = self.start_target_pos - axis_hit_point

    def on_mouse_move(self, viewport, x, y, dx, dy):
        if not self.dragging or self.target is None:
            return

        ray = viewport.screen_point_to_ray(x, y)
        if ray is None or self.axis_vec is None or self.axis_point is None:
            return

        _, axis_point_now = closest_point_on_axis_from_ray(
            axis_point=self.axis_point,
            axis_dir=self.axis_vec,
            ray_origin=ray.origin,
            ray_dir=ray.direction
        )

        # возвращаем смещение хватания
        new_pos = axis_point_now + self.grab_offset

        self.target.transform.relocate_global(
            Pose3(
                lin=new_pos,
                ang=self.target.transform.global_pose().ang
            )
        )

        # гизмо держим на объекте
        self.gizmo.transform.relocate_global(
            self.target.transform.global_pose()
        )

    def get_axis_vector(self, axis: str) -> np.ndarray:
        """
        Берёт мировое направление нужной оси гизмо (нормализованный вектор).
        """
        t = self.gizmo.transform

        if axis == "x":
            v = t.right(1.0)
        elif axis == "y":
            v = t.up(1.0)
        else:
            v = t.forward(1.0)

        v = np.asarray(v, dtype=np.float32)
        n = np.linalg.norm(v)
        return v if n == 0 else v / n


# ---------- КОНТРОЛЛЕР ВРАЩЕНИЯ ----------

class GizmoRotateController(InputComponent):
    """
    Простейший контроллер вращения объекта вокруг мировых осей гизмо.
    Для упрощения угол берётся из движения мыши (экранное пространство),
    а не из точного пересечения луча с плоскостью кольца.

    Это даёт достаточно предсказуемое управление и при этом не требует
    знать внутренности класса Pose3 (матрица, кватернион и так далее).
    """

    def __init__(self, gizmo_entity: GizmoEntity, scene, sensitivity: float = 0.01):
        super().__init__()
        self.gizmo = gizmo_entity
        self.scene = scene

        self.sensitivity = sensitivity  # коэффициент перевода пикселей в радианы

        self.dragging = False
        self.active_axis = None

        self.target = None

        self.start_target_pos = None
        self.start_target_ang = None

        self.start_mouse_x = 0.0
        self.start_mouse_y = 0.0

        self.set_enabled(False)

    def set_target(self, target_entity: Entity | None):
        if target_entity is not None and target_entity.pickable is False:
            target_entity = None

        self.target = target_entity
        if self.target is None:
            self.set_enabled(False)
            return

        self.set_enabled(True)

        self.gizmo.transform.relocate_global(
            self.target.transform.global_pose()
        )

    def set_enabled(self, flag: bool):
        self.enabled = flag
        self.gizmo.set_visible(flag)

    def on_mouse_button(self, viewport, button, action, mods):
        if button != 0:
            return

        x, y = viewport.window.handle.get_cursor_pos()

        if action == 1:  # нажали
            ray = viewport.screen_point_to_ray(x, y)
            if ray is None:
                return

            hit = self.scene.closest_to_ray(ray)
            if not hit:
                return

            name = hit.entity.name
            if name.startswith("gizmo_rot_"):
                axis = name.removeprefix("gizmo_rot_")
                self.start_drag(axis, x, y)
        else:
            # отпустили
            self.dragging = False
            self.active_axis = None
            self.start_target_pos = None
            self.start_target_ang = None

    def start_drag(self, axis: str, x: float, y: float):
        if self.target is None:
            return

        self.dragging = True
        self.active_axis = axis
        self.start_mouse_x = x
        self.start_mouse_y = y

        pose = self.target.transform.global_pose()
        self.start_target_pos = pose.lin.copy()
        # предполагаем, что pose.ang — это матрица три на три
        self.start_target_ang = pose.ang.copy()

    def on_mouse_move(self, viewport, x, y, dx, dy):
        if not self.dragging or self.target is None or self.start_target_ang is None:
            return

        # относительно начального положения мыши считаем дельту
        delta_x = x - self.start_mouse_x
        delta_y = y - self.start_mouse_y

        # простая эвристика: чем дальше увели мышь, тем больше угол
        delta_pixels = delta_x - delta_y  # чуть "косая" комбинация, чтобы было приятнее крутить
        angle = float(delta_pixels) * self.sensitivity  # в радианах

        # выбираем мировую ось вращения
        if self.active_axis == "x":
            axis_vec = np.array([1.0, 0.0, 0.0], dtype=float)
        elif self.active_axis == "y":
            axis_vec = np.array([0.0, 1.0, 0.0], dtype=float)
        else:
            axis_vec = np.array([0.0, 0.0, 1.0], dtype=float)

        R = rotation_matrix_from_axis_angle(axis_vec, angle)

        # применяем к исходной ориентации
        new_ang = R @ self.start_target_ang

        new_pose = Pose3(
            lin=self.start_target_pos,
            ang=new_ang
        )

        # ставим объект
        self.target.transform.relocate_global(new_pose)

        # и гизмо вместе с ним
        self.gizmo.transform.relocate_global(
            self.target.transform.global_pose()
        )
