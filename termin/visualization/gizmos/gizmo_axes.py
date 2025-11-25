from termin.mesh.mesh import CylinderMesh, ConeMesh
from termin.visualization.material import Material
from termin.visualization.entity import Entity
from termin.visualization.components import MeshRenderer
from termin.geombase.pose3 import Pose3
from termin.colliders import CapsuleCollider
from termin.colliders.collider_component import ColliderComponent
from termin.visualization.entity import InputComponent
import numpy as np

class GizmoArrow(Entity):
    def __init__(self, axis: str, length=1.0, color=(1.0, 0.0, 0.0, 1.0)):
        super().__init__(Pose3.identity(), name=f"gizmo_axis_{axis}", pickable=True, selectable=False)

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

        # ориентация оси
        if axis == "x":
            # повернуть местную ось Y → мировую X
            self.transform.relocate(Pose3.rotateZ(-np.pi/2))
        elif axis == "z":
            # повернуть местную ось Y → мировую Z
            self.transform.relocate(Pose3.rotateX(np.pi/2))

        # Y остаётся как есть

        # коллайдер вдоль оси
        self.add_component(
            ColliderComponent(
                collider=
                CapsuleCollider(
                    a =(0, 0, 0),
                    b =(0, length, 0),
                    radius=0.07,
                )
            )
        )

class GizmoEntity(Entity):
    def __init__(self, size=1.0):
        super().__init__(Pose3.identity(), name="gizmo", pickable=True, selectable=False)

        self.x = GizmoArrow("x", length=size, color=(1,0,0,1))
        self.y = GizmoArrow("y", length=size, color=(0,1,0,1))
        self.z = GizmoArrow("z", length=size, color=(0,0,1,1))

        self.transform.add_child(self.x.transform)
        self.transform.add_child(self.y.transform)
        self.transform.add_child(self.z.transform)


def closest_point_on_axis_from_ray(axis_point, axis_dir, ray_origin, ray_dir):
    p = np.asarray(axis_point, dtype=np.float32)
    a = np.asarray(axis_dir,   dtype=np.float32)
    o = np.asarray(ray_origin, dtype=np.float32)
    d = np.asarray(ray_dir,    dtype=np.float32)

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



class GizmoMoveController(InputComponent):
    """
    Контроллер перемещения объекта вдоль осей гизмо.
    Учитывает локальные оси гизмо, closest-point на оси
    и offset хватания.
    """

    def __init__(self, gizmo_entity, scene):
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

    # def update(self, dt):
    #     print("GizmoMoveController update")  # --- DEBUG --- --- IGNORE ---
    #     if self.target is None:
    #         # можно скрывать гизмо
    #         self.set_enabled(False)
    #         return

    #     self.set_enabled(True)

    #     pose = self.target.transform.global_pose()
    #     self.transform.relocate_global(Pose3(lin=pose.lin.copy()))

    def set_target(self, target_entity):
        print(f"GizmoMoveController set_target: {target_entity}")  # --- DEBUG ---

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
        print(f"GizmoMoveController set_enabled: {flag}")  # --- DEBUG ---
        self.enabled = flag
        self.gizmo.set_visible(flag)

    def on_mouse_button(self, viewport, button, action, mods):
        if button != 0:
            return

        x, y = viewport.window.handle.get_cursor_pos()

        if action == 1:  # press
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
            self.dragging = False
            self.active_axis = None
            self.axis_vec = None
            self.grab_offset = None


    def start_drag(self, axis, viewport, x, y):
        print(f"GizmoMoveController start_drag on axis: {axis}")  # --- DEBUG ---
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

        # вычисляем точку оси под курсором — здeсь мы "схватились"
        ray = viewport.screen_point_to_ray(x, y)

        if ray is None:
            return

        if self.axis_vec is None:
            print("GizmoMoveController start_drag: axis_vec is None (1)")  # --- DEBUG ---
            return

        t0, axis_hit_point = closest_point_on_axis_from_ray(
            axis_point=self.axis_point,
            axis_dir=self.axis_vec,
            ray_origin=ray.origin,
            ray_dir=ray.direction
        )

        # важное: учитываем, что пользователь схватился НЕ за origin
        self.grab_offset = self.start_target_pos - axis_hit_point


    def on_mouse_move(self, viewport, x, y, dx, dy):
        if not self.dragging or self.target is None:
            return

        ray = viewport.screen_point_to_ray(x, y)
        if ray is None:
            return

        if self.axis_vec is None:
            print("GizmoMoveController on_mouse_move: axis_vec is None (2)")  # --- DEBUG ---
            return

        t, axis_point_now = closest_point_on_axis_from_ray(
            axis_point=self.axis_point,
            axis_dir=self.axis_vec,
            ray_origin=ray.origin,
            ray_dir=ray.direction
        )

        # возвращаем offset хватания
        new_pos = axis_point_now + self.grab_offset

        self.target.transform.relocate_global(
            Pose3(
                lin=new_pos,
                ang=self.target.transform.global_pose().ang
            )
        )

        self.gizmo.transform.relocate_global(
            self.target.transform.global_pose()
        )


    def get_axis_vector(self, axis: str) -> np.ndarray:
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