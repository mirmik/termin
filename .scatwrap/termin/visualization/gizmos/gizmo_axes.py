<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/gizmos/gizmo_axes.py</title>
</head>
<body>
<pre><code>
import numpy as np

from termin.mesh.mesh import CylinderMesh, ConeMesh, RingMesh
from termin.visualization.material import Material
from termin.visualization.entity import Entity, InputComponent
from termin.visualization.components import MeshRenderer
from termin.geombase.pose3 import Pose3
from termin.util import qmul   # &lt;-- вот это добавляем


# ---------- ВСПОМОГАТЕЛЬНАЯ МАТЕМАТИКА ----------

def closest_point_on_axis_from_ray(axis_point, axis_dir, ray_origin, ray_dir):
    &quot;&quot;&quot;
    Находит ближайшую точку на прямой (axis_point + t * axis_dir) к лучу (ray_origin + s * ray_dir),
    возвращает параметр t и саму точку.
    &quot;&quot;&quot;
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

    if float(np.abs(denom)) &lt; 1e-6:
        t = -np.dot(w0, a)
        return t, p + a * t

    w0_dot_d = np.dot(w0, d)
    w0_dot_a = np.dot(w0, a)

    t = (a_dot_d * w0_dot_d - w0_dot_a) / denom
    point_on_axis = p + a * t
    return t, point_on_axis


def rotation_matrix_from_axis_angle(axis_vec: np.ndarray, angle: float) -&gt; np.ndarray:
    &quot;&quot;&quot;
    Строит матрицу поворота (3×3) вокруг произвольной оси.
    Ось задаётся в мировых координатах.
    &quot;&quot;&quot;
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
    &quot;&quot;&quot;
    Стрелка гизмо для перемещения вдоль одной оси.
    Состоит из цилиндра (ствол) и конуса (наконечник).
    Базовая модель ориентирована вдоль +Y.
    &quot;&quot;&quot;

    def __init__(self, axis: str, length=1.0, color=(1.0, 0.0, 0.0, 1.0)):
        super().__init__(
            Pose3.identity(),
            name=f&quot;gizmo_axis_{axis}&quot;,
            pickable=True,
            selectable=False
        )

        self.axis = axis
        shaft_len = length * 0.75
        head_len = length * 0.25

        # тут же можно &quot;утолщать&quot; геометрию, чтобы легче было попадать мышкой
        shaft = CylinderMesh(radius=0.03, height=shaft_len, segments=24)
        head = ConeMesh(radius=0.06, height=head_len, segments=24)

        mat = Material(color=color)

        # цилиндр (ствол)
        shaft_ent = Entity(
            Pose3.translation(0, shaft_len * 0.5, 0),
            name=f&quot;{axis}_shaft&quot;,
            pickable=True,
            selectable=False
        )
        shaft_ent.add_component(MeshRenderer(shaft, mat))
        self.shaft_ent = shaft_ent
        self.transform.add_child(shaft_ent.transform)

        # конус (наконечник)
        head_ent = Entity(
            Pose3.translation(0, shaft_len + head_len * 0.5, 0),
            name=f&quot;{axis}_head&quot;,
            pickable=True,
            selectable=False
        )
        head_ent.add_component(MeshRenderer(head, mat))
        self.head_ent = head_ent
        self.transform.add_child(head_ent.transform)

        # ориентация оси:
        # базовая модель ориентирована вдоль +Y,
        # поворачиваем, чтобы она смотрела вдоль нужной мировой оси
        if axis == &quot;x&quot;:
            # местная ось Y → мировая X
            self.transform.relocate(Pose3.rotateZ(-np.pi / 2.0))
        elif axis == &quot;z&quot;:
            # местная ось Y → мировая Z
            self.transform.relocate(Pose3.rotateX(np.pi / 2.0))
        # для оси Y поворот не нужен


class GizmoRing(Entity):
    &quot;&quot;&quot;
    Кольцо для гизмо вращения вокруг одной оси.
    Базовый меш лежит в XZ-плоскости, нормаль по +Y.
    Ориентацией transform доводим до нужной оси.
    &quot;&quot;&quot;

    def __init__(self, axis: str, radius=1.2, thickness=0.05, color=(1.0, 1.0, 0.0, 1.0)):
        super().__init__(
            Pose3.identity(),
            name=f&quot;gizmo_rot_{axis}&quot;,
            pickable=True,
            selectable=False
        )

        self.axis = axis

        # здесь толщина кольца и радиус — естественное место для &quot;утолщённой&quot; геометрии
        ring_mesh = RingMesh(radius=radius, thickness=thickness, segments=48)
        mat = Material(color=color)

        ring_ent = Entity(
            Pose3.identity(),
            name=f&quot;{axis}_ring&quot;,
            pickable=True,
            selectable=False
        )
        ring_ent.add_component(MeshRenderer(ring_mesh, mat))
        self.ring_ent = ring_ent
        self.transform.add_child(ring_ent.transform)

        # базовый RingMesh имеет нормаль (ось) вдоль +Y,
        # поворачиваем так же, как стрелки:
        if axis == &quot;x&quot;:
            # нормаль Y → X
            self.transform.relocate(Pose3.rotateZ(-np.pi / 2.0))
        elif axis == &quot;z&quot;:
            # нормаль Y → Z
            self.transform.relocate(Pose3.rotateX(np.pi / 2.0))
        # для оси Y поворот не нужен


class GizmoEntity(Entity):
    &quot;&quot;&quot;
    Общая сущность гизмо, которая содержит:
    - стрелки для перемещения
    - кольца для вращения
    &quot;&quot;&quot;

    def __init__(self, size=1.0):
        super().__init__(
            Pose3.identity(),
            name=&quot;gizmo&quot;,
            pickable=True,
            selectable=False
        )

        # стрелки перемещения
        self.x = GizmoArrow(&quot;x&quot;, length=size, color=(1, 0, 0, 1))
        self.y = GizmoArrow(&quot;y&quot;, length=size, color=(0, 1, 0, 1))
        self.z = GizmoArrow(&quot;z&quot;, length=size, color=(0, 0, 1, 1))

        self.transform.add_child(self.x.transform)
        self.transform.add_child(self.y.transform)
        self.transform.add_child(self.z.transform)

        # кольца вращения (слегка больше по радиусу)
        ring_radius = size * 1.25
        ring_thickness = size * 0.05

        self.rx = GizmoRing(&quot;x&quot;, radius=ring_radius, thickness=ring_thickness, color=(1, 0.3, 0.3, 1))
        self.ry = GizmoRing(&quot;y&quot;, radius=ring_radius, thickness=ring_thickness, color=(0.3, 1, 0.3, 1))
        self.rz = GizmoRing(&quot;z&quot;, radius=ring_radius, thickness=ring_thickness, color=(0.3, 0.3, 1, 1))

        self.transform.add_child(self.rx.transform)
        self.transform.add_child(self.ry.transform)
        self.transform.add_child(self.rz.transform)


# ---------- ЕДИНЫЙ КОНТРОЛЛЕР ПЕРЕМЕЩЕНИЯ+ВРАЩЕНИЯ ----------

class GizmoMoveController(InputComponent):
    &quot;&quot;&quot;
    Единый контроллер:
    - перемещение по стрелкам (gizmo_axis_x / y / z)
    - вращение по кольцам   (gizmo_rot_x / y / z)

    ВАЖНО:
    - пиккинг (кто под мышью) делает EditorWindow через pick_entity_at
    - сюда прилетает только &quot;ось и режим&quot; через start_*_from_pick
    - никаких scene.closest_to_ray и коллайдеров
    &quot;&quot;&quot;

    def __init__(self, gizmo_entity: GizmoEntity, scene, rotate_sensitivity: float = 0.01):
        super().__init__()
        self.gizmo = gizmo_entity
        self.scene = scene  # сейчас не используем, но оставим про запас

        self.enabled = False
        self.target: Entity | None = None

        # общее состояние драга
        self.dragging: bool = False
        self.drag_mode: str | None = None  # &quot;move&quot; или &quot;rotate&quot;
        self.active_axis: str | None = None

        # --- состояние для перемещения ---
        self.axis_vec: np.ndarray | None = None
        self.axis_point: np.ndarray | None = None
        self.grab_offset: np.ndarray | None = None
        self.start_target_pos: np.ndarray | None = None

        # --- состояние для вращения ---
        self.rotate_sensitivity: float = rotate_sensitivity
        self.start_target_ang: np.ndarray | None = None  # кватернион (x, y, z, w)
        self.start_mouse_x: float = 0.0
        self.start_mouse_y: float = 0.0

        self.set_enabled(False)

    # ---------- привязка к целевому объекту ----------

    def set_target(self, target_entity: Entity | None):
        # нельзя двигать/крутить то, что не пикэбл
        if target_entity is not None and target_entity.pickable is False:
            target_entity = None

        # на всякий случай завершить текущий драг
        self._end_drag()

        self.target = target_entity
        if self.target is None:
            self.set_enabled(False)
            return

        self.set_enabled(True)

        # ставим гизмо в позицию объекта
        self.gizmo.transform.relocate_global(
            self.target.transform.global_pose()
        )

    def set_enabled(self, flag: bool):
        self.enabled = flag
        self.gizmo.set_visible(flag)

    # ---------- публичные вызовы из EditorWindow ----------

    def start_translate_from_pick(self, axis: str, viewport, x: float, y: float):
        &quot;&quot;&quot;
        Вызывается EditorWindow из _after_render,
        когда пик показал, что кликнули по стрелке гизмо.
        &quot;&quot;&quot;
        print (f&quot;start_translate_from_pick axis={axis} x={x} y={y}&quot;)
        if not self.enabled or self.target is None:
            return
        self._start_move(axis, viewport, x, y)

    def start_rotate_from_pick(self, axis: str, viewport, x: float, y: float):
        &quot;&quot;&quot;
        Аналогично, но для кольца вращения.
        &quot;&quot;&quot;
        if not self.enabled or self.target is None:
            return
        self._start_rotate(axis, x, y)

    # ---------- события мыши от движка ----------

    def on_mouse_button(self, viewport, button, action, mods):
        &quot;&quot;&quot;
        Сюда приходят press/release от движка для всех InputComponent.
        Мы используем их только чтобы завершить драг по release.
        Начало драга даёт EditorWindow через start_*_from_pick.
        &quot;&quot;&quot;
        if not self.enabled:
            return
        if button != 0:
            return

        # action == 1 -&gt; press, action == 0 -&gt; release (по твоему коду)
        if action == 0:  # release
            self._end_drag()

    def on_mouse_move(self, viewport, x, y, dx, dy):
        if not self.enabled or not self.dragging or self.target is None:
            return

        if self.drag_mode == &quot;move&quot;:
            self._update_move(viewport, x, y)
        elif self.drag_mode == &quot;rotate&quot;:
            self._update_rotate(x, y)

    # ---------- внутренняя логика начала / конца драга ----------

    def _end_drag(self):
        self.dragging = False
        self.drag_mode = None
        self.active_axis = None

        self.axis_vec = None
        self.axis_point = None
        self.grab_offset = None
        self.start_target_pos = None

        self.start_target_ang = None
        self.start_mouse_x = 0.0
        self.start_mouse_y = 0.0

    # ---------- ПЕРЕМЕЩЕНИЕ ----------

    def _start_move(self, axis: str, viewport, x: float, y: float):
        self.dragging = True
        self.drag_mode = &quot;move&quot;
        self.active_axis = axis

        pose = self.target.transform.global_pose()
        self.start_target_pos = pose.lin.copy()

        # направление оси берём из transform гизмо (локальная ось в мировых координатах)
        self.axis_vec = self._get_axis_vector(axis)
        self.axis_point = self.start_target_pos.copy()

        ray = viewport.screen_point_to_ray(x, y)
        if ray is None or self.axis_vec is None:
            self._end_drag()
            return

        _, axis_hit_point = closest_point_on_axis_from_ray(
            axis_point=self.axis_point,
            axis_dir=self.axis_vec,
            ray_origin=ray.origin,
            ray_dir=ray.direction
        )

        # хватание может быть не в origin — запоминаем смещение
        self.grab_offset = self.start_target_pos - axis_hit_point

    def _update_move(self, viewport, x: float, y: float):
        if (
            self.axis_vec is None or
            self.axis_point is None or
            self.grab_offset is None or
            self.start_target_pos is None
        ):
            return

        ray = viewport.screen_point_to_ray(x, y)
        if ray is None:
            return

        _, axis_point_now = closest_point_on_axis_from_ray(
            axis_point=self.axis_point,
            axis_dir=self.axis_vec,
            ray_origin=ray.origin,
            ray_dir=ray.direction
        )

        new_pos = axis_point_now + self.grab_offset

        # двигаем объект
        old_pose = self.target.transform.global_pose()
        new_pose = Pose3(
            lin=new_pos,
            ang=old_pose.ang
        )
        self.target.transform.relocate_global(new_pose)

        # и гизмо за ним
        self.gizmo.transform.relocate_global(
            self.target.transform.global_pose()
        )

    def _get_axis_vector(self, axis: str) -&gt; np.ndarray:
        &quot;&quot;&quot;
        Берём мировое направление нужной оси гизмо (нормализованный вектор).
        То есть вращение/движение идёт по ЛОКАЛЬНЫМ осям объекта,
        потому что гизмо притянуто к его Pose3.
        &quot;&quot;&quot;
        t = self.gizmo.transform

        if axis == &quot;x&quot;:
            v = t.right(1.0)
        elif axis == &quot;y&quot;:
            v = t.up(1.0)
        else:
            v = t.forward(1.0)

        v = np.asarray(v, dtype=np.float32)
        n = np.linalg.norm(v)
        return v if n == 0.0 else (v / n)

    # ---------- ВРАЩЕНИЕ ----------

    def _start_rotate(self, axis: str, x: float, y: float):
        self.dragging = True
        self.drag_mode = &quot;rotate&quot;
        self.active_axis = axis

        self.start_mouse_x = x
        self.start_mouse_y = y

        pose = self.target.transform.global_pose()
        self.start_target_pos = pose.lin.copy()
        # здесь кватернион (x, y, z, w)
        self.start_target_ang = pose.ang.copy()

    def _update_rotate(self, x: float, y: float):
        if (
            self.start_target_ang is None or
            self.start_target_pos is None or
            self.active_axis is None
        ):
            return

        # дельта мыши от начала драга
        delta_x = x - self.start_mouse_x
        delta_y = y - self.start_mouse_y

        # простая эвристика: движение мыши -&gt; угол
        delta_pixels = delta_x - delta_y
        angle = float(delta_pixels) * self.rotate_sensitivity  # радианы

        # ось вращения в МИРОВЫХ координатах, но взята из локальных осей гизмо
        axis_vec = self._get_axis_vector(self.active_axis)

        # инкрементальный поворот вокруг этой оси (кватернион)
        dq = Pose3.rotation(axis_vec, angle).ang

        # new = dq * start -&gt; вращение вокруг той самой мировой оси (локально ориентированной)
        new_ang = qmul(dq, self.start_target_ang)

        # нормализуем
        norm = np.linalg.norm(new_ang)
        if norm &gt; 0.0:
            new_ang = new_ang / norm

        new_pose = Pose3(
            lin=self.start_target_pos,
            ang=new_ang
        )

        # ставим объект
        self.target.transform.relocate_global(new_pose)

        # и гизмо за ним
        self.gizmo.transform.relocate_global(
            self.target.transform.global_pose()
        )

</code></pre>
</body>
</html>
