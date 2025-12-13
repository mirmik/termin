import numpy as np
from typing import Optional, Callable
from termin.editor.undo_stack import UndoCommand
from termin.editor.editor_commands import TransformEditCommand

from termin.mesh.mesh import CylinderMesh, ConeMesh, RingMesh
from termin.visualization.core.material import Material
from termin.visualization.core.entity import Entity, InputComponent
from termin.visualization.render.components import MeshRenderer
from termin.geombase.pose3 import Pose3
from termin.util import qmul   # <-- вот это добавляем
from termin.visualization.render.renderpass import RenderState


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
    Строит матрицу поворота (3×3) вокруг произвольной оси.
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
    Базовая модель ориентирована вдоль +Y.
    """

    def __init__(self, axis: str, length=1.0, color=(1.0, 0.0, 0.0, 1.0)):
        super().__init__(
            Pose3.identity(),
            name=f"gizmo_axis_{axis}",
            pickable=False,
            selectable=False,
            serializable=False,
        )
        self.axis = axis
        self.length = float(length)

        shaft_len = self.length * 0.75
        head_len = self.length * 0.25

        # основная (видимая) геометрия
        self._create_main_geometry(axis, shaft_len, head_len, color)
        # вспомогательная (утолщённая, невидимая, только для пиккинга)
        self._create_pick_geometry(axis, shaft_len, head_len)

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

    def _create_main_geometry(
        self,
        axis: str,
        shaft_len: float,
        head_len: float,
        color,
    ):
        """Создаёт видимые меши стрелки (тонкий ствол + конус)."""
        shaft_mesh = CylinderMesh(radius=0.03, height=shaft_len, segments=24)
        head_mesh = ConeMesh(radius=0.06, height=head_len, segments=24)

        mat = Material(color=color, phase_mark="editor")

        # цилиндр (ствол)
        shaft_ent = Entity(
            Pose3.translation(0, shaft_len * 0.5, 0),
            name=f"{axis}_shaft",
            pickable=False,
            selectable=False,
        )
        shaft_ent.add_component(MeshRenderer(shaft_mesh, mat, cast_shadow=False))
        self.shaft_ent = shaft_ent
        self.transform.add_child(shaft_ent.transform)

        # конус (наконечник)
        head_ent = Entity(
            Pose3.translation(0, shaft_len + head_len * 0.5, 0),
            name=f"{axis}_head",
            pickable=False,
            selectable=False,
        )
        head_ent.add_component(MeshRenderer(head_mesh, mat, cast_shadow=False))
        self.head_ent = head_ent
        self.transform.add_child(head_ent.transform)

    def _create_pick_geometry(
        self,
        axis: str,
        shaft_len: float,
        head_len: float,
    ):
        """
        Создаёт утолщённую невидимую геометрию для удобного пиккинга.
        Без материала — не рендерится в ColorPass, только в GizmoPass.
        """
        # утолщённый ствол
        pick_shaft_mesh = CylinderMesh(radius=0.08, height=shaft_len, segments=16)
        pick_shaft_ent = Entity(
            Pose3.translation(0, shaft_len * 0.5, 0),
            name=f"{axis}_pick_shaft",
            pickable=False,
            selectable=False,
        )
        pick_shaft_ent.add_component(MeshRenderer(pick_shaft_mesh, cast_shadow=False))
        self.pick_shaft_ent = pick_shaft_ent
        self.transform.add_child(pick_shaft_ent.transform)

        # утолщённый наконечник
        pick_head_mesh = ConeMesh(radius=0.10, height=head_len, segments=16)
        pick_head_ent = Entity(
            Pose3.translation(0, shaft_len + head_len * 0.5, 0),
            name=f"{axis}_pick_head",
            pickable=False,
            selectable=False,
        )
        pick_head_ent.add_component(MeshRenderer(pick_head_mesh, cast_shadow=False))
        self.pick_head_ent = pick_head_ent
        self.transform.add_child(pick_head_ent.transform)



class GizmoRing(Entity):
    """
    Кольцо для гизмо вращения вокруг одной оси.
    Базовый меш лежит в XZ-плоскости, нормаль по +Y.
    Ориентацией transform доводим до нужной оси.
    """

    def __init__(
        self,
        axis: str,
        radius: float = 1.2,
        thickness: float = 0.05,
        color=(1.0, 1.0, 0.0, 1.0),
    ):
        super().__init__(
            Pose3.identity(),
            name=f"gizmo_rot_{axis}",
            pickable=False,
            selectable=False,
            serializable=False,
        )

        self.axis = axis
        self.radius = float(radius)
        self.thickness = float(thickness)

        # основная видимая геометрия
        self._create_main_geometry(axis, self.radius, self.thickness, color)
        # вспомогательная утолщённая геометрия для пиккинга
        self._create_pick_geometry(axis, self.radius, self.thickness)

        # базовый RingMesh имеет нормаль (ось) вдоль +Y,
        # поворачиваем так же, как стрелки:
        if axis == "x":
            # нормаль Y → X
            self.transform.relocate(Pose3.rotateZ(-np.pi / 2.0))
        elif axis == "z":
            # нормаль Y → Z
            self.transform.relocate(Pose3.rotateX(np.pi / 2.0))
        # для оси Y поворот не нужен

    def _create_main_geometry(
        self,
        axis: str,
        radius: float,
        thickness: float,
        color,
    ):
        """Создаёт видимое кольцо гизмо."""
        ring_mesh = RingMesh(radius=radius, thickness=thickness, segments=48)
        # cull=False для двустороннего рендеринга, phase_mark="editor"
        mat = Material(color=color, render_state=RenderState(cull=False), phase_mark="editor")

        ring_ent = Entity(
            Pose3.identity(),
            name=f"{axis}_ring",
            pickable=False,
            selectable=False,
        )
        ring_ent.add_component(MeshRenderer(ring_mesh, material=mat, cast_shadow=False))
        self.ring_ent = ring_ent
        self.transform.add_child(ring_ent.transform)

    def _create_pick_geometry(
        self,
        axis: str,
        radius: float,
        thickness: float,
    ):
        """
        Создаёт утолщённое невидимое кольцо для удобного пиккинга.
        Без материала — не рендерится в ColorPass, только в GizmoPass.
        """
        pick_ring_mesh = RingMesh(
            radius=radius,
            thickness=thickness * 2.0,
            segments=32,
        )
        pick_ring_ent = Entity(
            Pose3.identity(),
            name=f"{axis}_pick_ring",
            pickable=False,
            selectable=False,
        )
        pick_ring_ent.add_component(MeshRenderer(pick_ring_mesh, cast_shadow=False))
        self.pick_ring_ent = pick_ring_ent
        self.transform.add_child(pick_ring_ent.transform)



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
            pickable=False,
            selectable=False,
            serializable=False,
        )

        # стрелки перемещения
        self.x = GizmoArrow("x", length=size, color=(1, 0, 0, 1))
        self.y = GizmoArrow("y", length=size, color=(0, 1, 0, 1))
        self.z = GizmoArrow("z", length=size, color=(0, 0, 1, 1))

        self.transform.add_child(self.x.transform)
        self.transform.add_child(self.y.transform)
        self.transform.add_child(self.z.transform)

        # кольца вращения (слегка больше по радиусу)
        ring_radius = size * 1.25
        ring_thickness = size * 0.05

        self.rx = GizmoRing("x", radius=ring_radius, thickness=ring_thickness, color=(1, 0.3, 0.3, 1))
        self.ry = GizmoRing("y", radius=ring_radius, thickness=ring_thickness, color=(0.3, 1, 0.3, 1))
        self.rz = GizmoRing("z", radius=ring_radius, thickness=ring_thickness, color=(0.3, 0.3, 1, 1))

        self.transform.add_child(self.rx.transform)
        self.transform.add_child(self.ry.transform)
        self.transform.add_child(self.rz.transform)

    def helper_geometry_entities(self) -> list[Entity]:
        """Возвращает список всех вспомогательных (pick) сущностей гизмо."""
        return [
            self.x.pick_shaft_ent,
            self.x.pick_head_ent,
            self.y.pick_shaft_ent,
            self.y.pick_head_ent,
            self.z.pick_shaft_ent,
            self.z.pick_head_ent,
            self.rx.pick_ring_ent,
            self.ry.pick_ring_ent,
            self.rz.pick_ring_ent,
        ]
# ---------- ЕДИНЫЙ КОНТРОЛЛЕР ПЕРЕМЕЩЕНИЯ+ВРАЩЕНИЯ ----------

class GizmoMoveController(InputComponent):
    """
    Единый контроллер:
    - перемещение по стрелкам (gizmo_axis_x / y / z)
    - вращение по кольцам   (gizmo_rot_x / y / z)

    ВАЖНО:
    - пиккинг делает EditorWindow через pick_entity_at
    - сюда прилетает только "ось и режим" через start_*_from_pick
    """

    def __init__(self, gizmo_entity: GizmoEntity, scene, rotate_sensitivity: float = 1.0):
        super().__init__()
        self.gizmo = gizmo_entity
        self.scene = scene  # сейчас почти не используется, но оставим

        self.enabled = False
        self.target: Entity | None = None

        # обработчик undo-команд редактора
        self._undo_handler: Optional[Callable[[UndoCommand, bool], None]] = None

        # колбэк, вызываемый при изменении трансформа во время перетаскивания
        self._on_transform_dragging: Optional[Callable[[], None]] = None

        # состояние для фиксации трансформа в undo-стек
        self._drag_transform = None
        self._start_pose: Pose3 | None = None
        self._start_scale: np.ndarray | None = None

        # общее состояние драга
        self.dragging: bool = False
        self.drag_mode: str | None = None  # "move" или "rotate"
        self.active_axis: str | None = None

        # --- состояние для перемещения ---
        self.axis_vec: np.ndarray | None = None       # направление оси (мир)
        self.axis_point: np.ndarray | None = None     # точка на оси
        self.grab_offset: np.ndarray | None = None    # сдвиг от оси до центра объекта
        self.start_target_pos: np.ndarray | None = None

        # --- состояние для вращения (циркулярный драг) ---
        self.start_target_ang: np.ndarray | None = None  # кватернион (x, y, z, w)
        self.rot_axis: np.ndarray | None = None          # нормаль плоскости (ось вращения, мир)
        self.rot_plane_origin: np.ndarray | None = None  # O – центр вращения
        self.rot_vec0: np.ndarray | None = None          # нормализованный вектор OA в плоскости

        # координаты мыши на старте – больше для дебага, но пусть остаются
        self.start_mouse_x: float = 0.0
        self.start_mouse_y: float = 0.0

        # чувствительность по факту теперь задаётся длиной дуги, так что фактор можно держать =1
        self.rotate_sensitivity: float = rotate_sensitivity

        self.set_enabled(False)

    def set_undo_command_handler(self, handler: Optional[Callable[[UndoCommand, bool], None]]):
        """
        Регистрирует обработчик undo-команд (обычно EditorWindow.push_undo_command).
        """
        self._undo_handler = handler

    def set_on_transform_dragging(self, callback: Optional[Callable[[], None]]):
        """
        Регистрирует колбэк, вызываемый при изменении трансформа во время drag.

        Используется для обновления инспектора в реальном времени.
        """
        self._on_transform_dragging = callback

    # ---------- утилита: пересечение луча с плоскостью ----------

    @staticmethod
    def _ray_plane_intersection(ray, plane_origin: np.ndarray, plane_normal: np.ndarray):
        """
        Возвращает точку пересечения луча с плоскостью (origin, normal),
        либо None, если луч почти параллелен плоскости.
        """
        n = np.asarray(plane_normal, dtype=float)
        n_norm = np.linalg.norm(n)
        if n_norm == 0.0:
            return None
        n /= n_norm

        ro = np.asarray(ray.origin, dtype=float)
        rd = np.asarray(ray.direction, dtype=float)

        denom = float(np.dot(rd, n))
        if abs(denom) < 1e-6:
            return None  # почти параллелен

        t = float(np.dot(plane_origin - ro, n) / denom)
        # можно не проверять знак t – это бесконечная плоскость, а не физический объект
        return ro + rd * t

    # ---------- привязка к целевому объекту ----------

    def set_target(self, target_entity: Entity | None):
        if target_entity is not None and target_entity.pickable is False:
            target_entity = None

        self._end_drag()

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

    # ---------- публичные вызовы из EditorWindow ----------

    def start_translate_from_pick(self, axis: str, viewport, x: float, y: float):
        """
        Вызывается EditorWindow из _after_render,
        когда пик показал, что кликнули по стрелке гизмо.
        """
        if not self.enabled or self.target is None:
            return
        self._start_move(axis, viewport, x, y)

    def start_rotate_from_pick(self, axis: str, viewport, x: float, y: float):
        """
        Аналогично, но для кольца вращения.
        """
        if not self.enabled or self.target is None:
            return
        self._start_rotate(axis, viewport, x, y)

    # ---------- события мыши от движка ----------

    def on_mouse_button(self, viewport, button, action, mods):
        if not self.enabled:
            return
        if button != 0:
            return

        # action == 0 -> release
        if action == 0:
            self._end_drag()

    def on_mouse_move(self, viewport, x: float, y: float, dx: float, dy: float):
        if not self.enabled or not self.dragging or self.target is None:
            return

        if self.drag_mode == "move":
            self._update_move(viewport, x, y)
        elif self.drag_mode == "rotate":
            self._update_rotate(viewport, x, y)

    # ---------- внутренняя логика начала / конца драга ----------

    def _commit_drag_to_undo(self):
        """
        Если трансформ объекта изменился во время текущего драга,
        отправляет соответствующую TransformEditCommand в undo-стек.
        """
        if self._undo_handler is None:
            return
        if self._drag_transform is None or self._start_pose is None:
            return

        tf = self._drag_transform
        end_pose = tf.global_pose()

        ent = tf.entity
        end_scale = None
        if ent is not None:
            try:
                end_scale = np.asarray(ent.scale, dtype=float)
            except Exception:
                end_scale = None

        start_scale = self._start_scale
        if start_scale is None and end_scale is not None:
            start_scale = end_scale.copy()

        # если вообще ничего не поменялось — команду не создаём
        if (
            np.allclose(end_pose.lin, self._start_pose.lin)
            and np.allclose(end_pose.ang, self._start_pose.ang)
            and (
                start_scale is None
                or end_scale is None
                or np.allclose(end_scale, start_scale)
            )
        ):
            return

        if start_scale is None:
            start_scale = np.ones(3, dtype=float)
        if end_scale is None:
            end_scale = start_scale.copy()

        cmd = TransformEditCommand(
            transform=tf,
            old_pose=self._start_pose,
            old_scale=start_scale,
            new_pose=end_pose,
            new_scale=end_scale,
        )
        self._undo_handler(cmd, False)

    def _end_drag(self):
        if self.dragging:
            self._commit_drag_to_undo()

        self.dragging = False
        self.drag_mode = None
        self.active_axis = None

        self.axis_vec = None
        self.axis_point = None
        self.grab_offset = None
        self.start_target_pos = None

        self.start_target_ang = None
        self.rot_axis = None
        self.rot_plane_origin = None
        self.rot_vec0 = None

        self.start_mouse_x = 0.0
        self.start_mouse_y = 0.0

        self._drag_transform = None
        self._start_pose = None
        self._start_scale = None

    # ---------- ПЕРЕМЕЩЕНИЕ ----------

    def _start_move(self, axis: str, viewport, x: float, y: float):
        self.dragging = True
        self.drag_mode = "move"
        self.active_axis = axis

        pose = self.target.transform.global_pose()
        self.start_target_pos = pose.lin.copy()

        self._drag_transform = self.target.transform
        self._start_pose = pose
        ent = self.target
        try:
            self._start_scale = np.asarray(ent.scale, dtype=float).copy()
        except Exception:
            self._start_scale = None

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

        old_pose = self.target.transform.global_pose()
        new_pose = Pose3(
            lin=new_pos,
            ang=old_pose.ang
        )
        self.target.transform.relocate_global(new_pose)

        self.gizmo.transform.relocate_global(
            self.target.transform.global_pose()
        )

        # Уведомляем инспектор об изменении трансформа
        if self._on_transform_dragging is not None:
            self._on_transform_dragging()

    def _get_axis_vector(self, axis: str) -> np.ndarray:
        t = self.gizmo.transform

        if axis == "x":
            v = t.right(1.0)
        elif axis == "y":
            v = t.up(1.0)
        else:
            v = t.forward(1.0)

        v = np.asarray(v, dtype=np.float32)
        n = np.linalg.norm(v)
        return v if n == 0.0 else (v / n)

    # ---------- ВРАЩЕНИЕ (циркулярный драг) ----------

    def _start_rotate(self, axis: str, viewport, x: float, y: float):
        self.dragging = True
        self.drag_mode = "rotate"
        self.active_axis = axis

        self.start_mouse_x = x
        self.start_mouse_y = y

        pose = self.target.transform.global_pose()
        self.start_target_pos = pose.lin.copy()
        self.start_target_ang = pose.ang.copy()

        self._drag_transform = self.target.transform
        self._start_pose = pose
        ent = self.target
        try:
            self._start_scale = np.asarray(ent.scale, dtype=float).copy()
        except Exception:
            self._start_scale = None

        # мировая ось вращения – та же, что и направление стрелки/кольца
        self.rot_axis = self._get_axis_vector(axis)
        if self.rot_axis is None:
            self._end_drag()
            return

        # O – центр вращения (центр гизмо / объекта)
        self.rot_plane_origin = self.start_target_pos.copy()

        ray = viewport.screen_point_to_ray(x, y)
        if ray is None:
            self._end_drag()
            return

        hit = self._ray_plane_intersection(ray, self.rot_plane_origin, self.rot_axis)
        if hit is None:
            self._end_drag()
            return

        v0 = hit - self.rot_plane_origin
        norm_v0 = np.linalg.norm(v0)
        if norm_v0 < 1e-6:
            # если вдруг попали почти в центр – зафиксируем какой-нибудь базовый вектор в плоскости
            # берём любое, не параллельное оси, и ортогонализуем
            tmp = np.array([1.0, 0.0, 0.0], dtype=float)
            if abs(np.dot(tmp, self.rot_axis)) > 0.9:
                tmp = np.array([0.0, 1.0, 0.0], dtype=float)
            v0 = tmp - self.rot_axis * np.dot(tmp, self.rot_axis)
            norm_v0 = np.linalg.norm(v0)
            if norm_v0 < 1e-6:
                self._end_drag()
                return

        self.rot_vec0 = v0 / norm_v0

    def _update_rotate(self, viewport, x: float, y: float):
        if (
            self.start_target_ang is None or
            self.start_target_pos is None or
            self.rot_axis is None or
            self.rot_plane_origin is None or
            self.rot_vec0 is None
        ):
            return

        ray = viewport.screen_point_to_ray(x, y)
        if ray is None:
            return

        hit = self._ray_plane_intersection(ray, self.rot_plane_origin, self.rot_axis)
        if hit is None:
            return

        v1 = hit - self.rot_plane_origin
        norm_v1 = np.linalg.norm(v1)
        if norm_v1 < 1e-6:
            return
        v1 /= norm_v1

        # угол между v0 и v1
        dot = float(np.clip(np.dot(self.rot_vec0, v1), -1.0, 1.0))
        cross = np.cross(self.rot_vec0, v1)

        # модуль креста даёт sin, скалярное произведение – cos
        sin_angle = np.linalg.norm(cross)
        cos_angle = dot

        # знак через ориентацию относительно оси вращения
        sign = np.sign(np.dot(cross, self.rot_axis))
        if sign == 0.0:
            sign = 1.0  # если почти ноль – считаем положительным

        angle = float(np.arctan2(sin_angle, cos_angle)) * sign

        # если хочешь ослабить/усилить чувствительность — домножь на self.rotate_sensitivity
        angle *= self.rotate_sensitivity

        # кватернион инкрементального поворота вокруг rot_axis
        axis = self.rot_axis / np.linalg.norm(self.rot_axis)
        half = angle * 0.5
        s = np.sin(half)
        c = np.cos(half)
        dq = np.array([axis[0] * s, axis[1] * s, axis[2] * s, c], dtype=float)

        new_ang = qmul(dq, self.start_target_ang)

        norm_q = np.linalg.norm(new_ang)
        if norm_q > 0.0:
            new_ang /= norm_q

        new_pose = Pose3(
            lin=self.start_target_pos,
            ang=new_ang
        )

        self.target.transform.relocate_global(new_pose)

        self.gizmo.transform.relocate_global(
            self.target.transform.global_pose()
        )

        # Уведомляем инспектор об изменении трансформа
        if self._on_transform_dragging is not None:
            self._on_transform_dragging()


class GizmoController:
    """
    Обёртка над GizmoEntity и GizmoMoveController:
    - ищет/создаёт гизмо в сцене;
    - назначает обработчик undo-команд;
    - умеет запускать drag по цвету из pick-буфера;
    - даёт список вспомогательной геометрии для GizmoPass.
    """

    def __init__(self, scene, editor_entities=None, undo_handler: Optional[Callable[[UndoCommand, bool], None]] = None):
        self.scene = scene
        self.editor_entities = editor_entities
        self._undo_handler = undo_handler

        self.gizmo: GizmoEntity | None = None
        self._ensure_gizmo()

    def _ensure_gizmo(self):
        for ent in self.scene.entities:
            if isinstance(ent, GizmoEntity) or ent.name == "gizmo":
                self.gizmo = ent
                gizmo_ctrl = ent.find_component(GizmoMoveController)
                if gizmo_ctrl is not None:
                    gizmo_ctrl.set_undo_command_handler(self._undo_handler)
                return

        gizmo = GizmoEntity(size=1.5)
        gizmo_controller = GizmoMoveController(gizmo, self.scene)
        gizmo_controller.set_undo_command_handler(self._undo_handler)
        gizmo.add_component(gizmo_controller)

        if self.editor_entities is not None:
            self.editor_entities.transform.add_child(gizmo.transform)

        self.scene.add(gizmo)
        self.gizmo = gizmo

    def recreate_gizmo(self, scene, editor_entities=None) -> None:
        """Пересоздаёт гизмо в новой сцене."""
        self.scene = scene
        self.editor_entities = editor_entities
        self.gizmo = None
        self._ensure_gizmo()

    def set_target(self, target_entity: Entity | None) -> None:
        if self.gizmo is None:
            return
        gizmo_ctrl = self.gizmo.find_component(GizmoMoveController)
        if gizmo_ctrl is None:
            return
        gizmo_ctrl.set_target(target_entity)

    def set_on_transform_dragging(self, callback: Optional[Callable[[], None]]) -> None:
        """
        Устанавливает колбэк для уведомления об изменении трансформа во время drag.

        Используется для обновления инспектора в реальном времени.
        """
        if self.gizmo is None:
            return
        gizmo_ctrl = self.gizmo.find_component(GizmoMoveController)
        if gizmo_ctrl is None:
            return
        gizmo_ctrl.set_on_transform_dragging(callback)

    def set_visible(self, visible: bool) -> None:
        """Показывает или скрывает гизмо."""
        if self.gizmo is not None:
            self.gizmo.set_visible(visible)

    def helper_geometry_entities(self) -> list[Entity]:
        if self.gizmo is None:
            return []
        return self.gizmo.helper_geometry_entities()

    def is_dragging(self) -> bool:
        """Возвращает True, если гизмо находится в режиме drag."""
        if self.gizmo is None:
            return False
        gizmo_ctrl = self.gizmo.find_component(GizmoMoveController)
        if gizmo_ctrl is None:
            return False
        return gizmo_ctrl.dragging

    def handle_pick_press_with_color(self, x: float, y: float, viewport, picked_color) -> bool:
        """
        Возвращает True, если клик по pick-буферу был обработан гизмо
        (начата операция перемещения или вращения).
        
        Гизмо рендерится в id-буфер с alpha < 1.0, где alpha кодирует индекс элемента:
            alpha = index / (maxindex + 1)
        Обычные объекты рендерятся с alpha = 1.0.
        """
        if self.gizmo is None:
            return False

        if picked_color is None:
            return False

        alpha = picked_color[3]
        
        # alpha = 0 — пустое пространство
        # alpha = 1.0 — обычный объект (не гизмо)
        # 0 < alpha < 1 — элемент гизмо
        if alpha == 0 or alpha >= 1.0:
            return False

        helpers = self.gizmo.helper_geometry_entities()
        maxindex = len(helpers)
        # Обратная формула: index = round(alpha * (maxindex + 1))
        index = int(round(alpha * float(maxindex + 1))) - 1
        if index < 0 or index >= maxindex:
            return False

        picked_ent = helpers[index]
        axis = picked_ent.name[0]

        gizmo_ctrl = self.gizmo.find_component(GizmoMoveController)
        if gizmo_ctrl is None:
            return False

        if picked_ent.name.endswith("head") or picked_ent.name.endswith("shaft"):
            gizmo_ctrl.start_translate_from_pick(axis, viewport, x, y)
            return True

        if picked_ent.name.endswith("ring"):
            gizmo_ctrl.start_rotate_from_pick(axis, viewport, x, y)
            return True

        return False
