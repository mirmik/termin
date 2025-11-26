<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/gizmos/gizmo_axes.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import numpy as np<br>
<br>
from termin.mesh.mesh import CylinderMesh, ConeMesh, RingMesh<br>
from termin.visualization.material import Material<br>
from termin.visualization.entity import Entity, InputComponent<br>
from termin.visualization.components import MeshRenderer<br>
from termin.geombase.pose3 import Pose3<br>
from termin.util import qmul   # &lt;-- вот это добавляем<br>
<br>
<br>
# ---------- ВСПОМОГАТЕЛЬНАЯ МАТЕМАТИКА ----------<br>
<br>
def closest_point_on_axis_from_ray(axis_point, axis_dir, ray_origin, ray_dir):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Находит ближайшую точку на прямой (axis_point + t * axis_dir) к лучу (ray_origin + s * ray_dir),<br>
&#9;возвращает параметр t и саму точку.<br>
&#9;&quot;&quot;&quot;<br>
&#9;p = np.asarray(axis_point, dtype=np.float32)<br>
&#9;a = np.asarray(axis_dir, dtype=np.float32)<br>
&#9;o = np.asarray(ray_origin, dtype=np.float32)<br>
&#9;d = np.asarray(ray_dir, dtype=np.float32)<br>
<br>
&#9;a_norm = np.linalg.norm(a)<br>
&#9;if a_norm == 0:<br>
&#9;&#9;return 0.0, p.copy()<br>
&#9;a /= a_norm<br>
<br>
&#9;d_norm = np.linalg.norm(d)<br>
&#9;if d_norm == 0:<br>
&#9;&#9;return 0.0, p.copy()<br>
&#9;d /= d_norm<br>
<br>
&#9;w0 = p - o<br>
&#9;a_dot_d = np.dot(a, d)<br>
&#9;denom = 1.0 - a_dot_d * a_dot_d<br>
<br>
&#9;if float(np.abs(denom)) &lt; 1e-6:<br>
&#9;&#9;t = -np.dot(w0, a)<br>
&#9;&#9;return t, p + a * t<br>
<br>
&#9;w0_dot_d = np.dot(w0, d)<br>
&#9;w0_dot_a = np.dot(w0, a)<br>
<br>
&#9;t = (a_dot_d * w0_dot_d - w0_dot_a) / denom<br>
&#9;point_on_axis = p + a * t<br>
&#9;return t, point_on_axis<br>
<br>
<br>
def rotation_matrix_from_axis_angle(axis_vec: np.ndarray, angle: float) -&gt; np.ndarray:<br>
&#9;&quot;&quot;&quot;<br>
&#9;Строит матрицу поворота (3×3) вокруг произвольной оси.<br>
&#9;Ось задаётся в мировых координатах.<br>
&#9;&quot;&quot;&quot;<br>
&#9;axis = np.asarray(axis_vec, dtype=float)<br>
&#9;n = np.linalg.norm(axis)<br>
&#9;if n == 0.0:<br>
&#9;&#9;return np.eye(3, dtype=float)<br>
&#9;axis /= n<br>
<br>
&#9;x, y, z = axis<br>
&#9;c = float(np.cos(angle))<br>
&#9;s = float(np.sin(angle))<br>
&#9;C = 1.0 - c<br>
<br>
&#9;return np.array(<br>
&#9;&#9;[<br>
&#9;&#9;&#9;[x * x * C + c,     x * y * C - z * s, x * z * C + y * s],<br>
&#9;&#9;&#9;[y * x * C + z * s, y * y * C + c,     y * z * C - x * s],<br>
&#9;&#9;&#9;[z * x * C - y * s, z * y * C + x * s, z * z * C + c],<br>
&#9;&#9;],<br>
&#9;&#9;dtype=float,<br>
&#9;)<br>
<br>
<br>
# ---------- ГРАФИЧЕСКИЕ ОБЪЕКТЫ ГИЗМО ----------<br>
<br>
class GizmoArrow(Entity):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Стрелка гизмо для перемещения вдоль одной оси.<br>
&#9;Состоит из цилиндра (ствол) и конуса (наконечник).<br>
&#9;Базовая модель ориентирована вдоль +Y.<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, axis: str, length=1.0, color=(1.0, 0.0, 0.0, 1.0)):<br>
&#9;&#9;super().__init__(<br>
&#9;&#9;&#9;Pose3.identity(),<br>
&#9;&#9;&#9;name=f&quot;gizmo_axis_{axis}&quot;,<br>
&#9;&#9;&#9;pickable=True,<br>
&#9;&#9;&#9;selectable=False<br>
&#9;&#9;)<br>
<br>
&#9;&#9;self.axis = axis<br>
&#9;&#9;shaft_len = length * 0.75<br>
&#9;&#9;head_len = length * 0.25<br>
<br>
&#9;&#9;# тут же можно &quot;утолщать&quot; геометрию, чтобы легче было попадать мышкой<br>
&#9;&#9;shaft = CylinderMesh(radius=0.03, height=shaft_len, segments=24)<br>
&#9;&#9;head = ConeMesh(radius=0.06, height=head_len, segments=24)<br>
<br>
&#9;&#9;mat = Material(color=color)<br>
<br>
&#9;&#9;# цилиндр (ствол)<br>
&#9;&#9;shaft_ent = Entity(<br>
&#9;&#9;&#9;Pose3.translation(0, shaft_len * 0.5, 0),<br>
&#9;&#9;&#9;name=f&quot;{axis}_shaft&quot;,<br>
&#9;&#9;&#9;pickable=True,<br>
&#9;&#9;&#9;selectable=False<br>
&#9;&#9;)<br>
&#9;&#9;shaft_ent.add_component(MeshRenderer(shaft, mat))<br>
&#9;&#9;self.shaft_ent = shaft_ent<br>
&#9;&#9;self.transform.add_child(shaft_ent.transform)<br>
<br>
&#9;&#9;# конус (наконечник)<br>
&#9;&#9;head_ent = Entity(<br>
&#9;&#9;&#9;Pose3.translation(0, shaft_len + head_len * 0.5, 0),<br>
&#9;&#9;&#9;name=f&quot;{axis}_head&quot;,<br>
&#9;&#9;&#9;pickable=True,<br>
&#9;&#9;&#9;selectable=False<br>
&#9;&#9;)<br>
&#9;&#9;head_ent.add_component(MeshRenderer(head, mat))<br>
&#9;&#9;self.head_ent = head_ent<br>
&#9;&#9;self.transform.add_child(head_ent.transform)<br>
<br>
&#9;&#9;# ориентация оси:<br>
&#9;&#9;# базовая модель ориентирована вдоль +Y,<br>
&#9;&#9;# поворачиваем, чтобы она смотрела вдоль нужной мировой оси<br>
&#9;&#9;if axis == &quot;x&quot;:<br>
&#9;&#9;&#9;# местная ось Y → мировая X<br>
&#9;&#9;&#9;self.transform.relocate(Pose3.rotateZ(-np.pi / 2.0))<br>
&#9;&#9;elif axis == &quot;z&quot;:<br>
&#9;&#9;&#9;# местная ось Y → мировая Z<br>
&#9;&#9;&#9;self.transform.relocate(Pose3.rotateX(np.pi / 2.0))<br>
&#9;&#9;# для оси Y поворот не нужен<br>
<br>
<br>
class GizmoRing(Entity):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Кольцо для гизмо вращения вокруг одной оси.<br>
&#9;Базовый меш лежит в XZ-плоскости, нормаль по +Y.<br>
&#9;Ориентацией transform доводим до нужной оси.<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, axis: str, radius=1.2, thickness=0.05, color=(1.0, 1.0, 0.0, 1.0)):<br>
&#9;&#9;super().__init__(<br>
&#9;&#9;&#9;Pose3.identity(),<br>
&#9;&#9;&#9;name=f&quot;gizmo_rot_{axis}&quot;,<br>
&#9;&#9;&#9;pickable=True,<br>
&#9;&#9;&#9;selectable=False<br>
&#9;&#9;)<br>
<br>
&#9;&#9;self.axis = axis<br>
<br>
&#9;&#9;# здесь толщина кольца и радиус — естественное место для &quot;утолщённой&quot; геометрии<br>
&#9;&#9;ring_mesh = RingMesh(radius=radius, thickness=thickness, segments=48)<br>
&#9;&#9;mat = Material(color=color)<br>
<br>
&#9;&#9;ring_ent = Entity(<br>
&#9;&#9;&#9;Pose3.identity(),<br>
&#9;&#9;&#9;name=f&quot;{axis}_ring&quot;,<br>
&#9;&#9;&#9;pickable=True,<br>
&#9;&#9;&#9;selectable=False<br>
&#9;&#9;)<br>
&#9;&#9;ring_ent.add_component(MeshRenderer(ring_mesh, mat))<br>
&#9;&#9;self.ring_ent = ring_ent<br>
&#9;&#9;self.transform.add_child(ring_ent.transform)<br>
<br>
&#9;&#9;# базовый RingMesh имеет нормаль (ось) вдоль +Y,<br>
&#9;&#9;# поворачиваем так же, как стрелки:<br>
&#9;&#9;if axis == &quot;x&quot;:<br>
&#9;&#9;&#9;# нормаль Y → X<br>
&#9;&#9;&#9;self.transform.relocate(Pose3.rotateZ(-np.pi / 2.0))<br>
&#9;&#9;elif axis == &quot;z&quot;:<br>
&#9;&#9;&#9;# нормаль Y → Z<br>
&#9;&#9;&#9;self.transform.relocate(Pose3.rotateX(np.pi / 2.0))<br>
&#9;&#9;# для оси Y поворот не нужен<br>
<br>
<br>
class GizmoEntity(Entity):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Общая сущность гизмо, которая содержит:<br>
&#9;- стрелки для перемещения<br>
&#9;- кольца для вращения<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, size=1.0):<br>
&#9;&#9;super().__init__(<br>
&#9;&#9;&#9;Pose3.identity(),<br>
&#9;&#9;&#9;name=&quot;gizmo&quot;,<br>
&#9;&#9;&#9;pickable=True,<br>
&#9;&#9;&#9;selectable=False<br>
&#9;&#9;)<br>
<br>
&#9;&#9;# стрелки перемещения<br>
&#9;&#9;self.x = GizmoArrow(&quot;x&quot;, length=size, color=(1, 0, 0, 1))<br>
&#9;&#9;self.y = GizmoArrow(&quot;y&quot;, length=size, color=(0, 1, 0, 1))<br>
&#9;&#9;self.z = GizmoArrow(&quot;z&quot;, length=size, color=(0, 0, 1, 1))<br>
<br>
&#9;&#9;self.transform.add_child(self.x.transform)<br>
&#9;&#9;self.transform.add_child(self.y.transform)<br>
&#9;&#9;self.transform.add_child(self.z.transform)<br>
<br>
&#9;&#9;# кольца вращения (слегка больше по радиусу)<br>
&#9;&#9;ring_radius = size * 1.25<br>
&#9;&#9;ring_thickness = size * 0.05<br>
<br>
&#9;&#9;self.rx = GizmoRing(&quot;x&quot;, radius=ring_radius, thickness=ring_thickness, color=(1, 0.3, 0.3, 1))<br>
&#9;&#9;self.ry = GizmoRing(&quot;y&quot;, radius=ring_radius, thickness=ring_thickness, color=(0.3, 1, 0.3, 1))<br>
&#9;&#9;self.rz = GizmoRing(&quot;z&quot;, radius=ring_radius, thickness=ring_thickness, color=(0.3, 0.3, 1, 1))<br>
<br>
&#9;&#9;self.transform.add_child(self.rx.transform)<br>
&#9;&#9;self.transform.add_child(self.ry.transform)<br>
&#9;&#9;self.transform.add_child(self.rz.transform)<br>
<br>
<br>
# ---------- ЕДИНЫЙ КОНТРОЛЛЕР ПЕРЕМЕЩЕНИЯ+ВРАЩЕНИЯ ----------<br>
<br>
class GizmoMoveController(InputComponent):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Единый контроллер:<br>
&#9;- перемещение по стрелкам (gizmo_axis_x / y / z)<br>
&#9;- вращение по кольцам   (gizmo_rot_x / y / z)<br>
<br>
&#9;ВАЖНО:<br>
&#9;- пиккинг делает EditorWindow через pick_entity_at<br>
&#9;- сюда прилетает только &quot;ось и режим&quot; через start_*_from_pick<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, gizmo_entity: GizmoEntity, scene, rotate_sensitivity: float = 1.0):<br>
&#9;&#9;super().__init__()<br>
&#9;&#9;self.gizmo = gizmo_entity<br>
&#9;&#9;self.scene = scene  # сейчас почти не используется, но оставим<br>
<br>
&#9;&#9;self.enabled = False<br>
&#9;&#9;self.target: Entity | None = None<br>
<br>
&#9;&#9;# общее состояние драга<br>
&#9;&#9;self.dragging: bool = False<br>
&#9;&#9;self.drag_mode: str | None = None  # &quot;move&quot; или &quot;rotate&quot;<br>
&#9;&#9;self.active_axis: str | None = None<br>
<br>
&#9;&#9;# --- состояние для перемещения ---<br>
&#9;&#9;self.axis_vec: np.ndarray | None = None       # направление оси (мир)<br>
&#9;&#9;self.axis_point: np.ndarray | None = None     # точка на оси<br>
&#9;&#9;self.grab_offset: np.ndarray | None = None    # сдвиг от оси до центра объекта<br>
&#9;&#9;self.start_target_pos: np.ndarray | None = None<br>
<br>
&#9;&#9;# --- состояние для вращения (циркулярный драг) ---<br>
&#9;&#9;self.start_target_ang: np.ndarray | None = None  # кватернион (x, y, z, w)<br>
&#9;&#9;self.rot_axis: np.ndarray | None = None          # нормаль плоскости (ось вращения, мир)<br>
&#9;&#9;self.rot_plane_origin: np.ndarray | None = None  # O – центр вращения<br>
&#9;&#9;self.rot_vec0: np.ndarray | None = None          # нормализованный вектор OA в плоскости<br>
<br>
&#9;&#9;# координаты мыши на старте – больше для дебага, но пусть остаются<br>
&#9;&#9;self.start_mouse_x: float = 0.0<br>
&#9;&#9;self.start_mouse_y: float = 0.0<br>
<br>
&#9;&#9;# чувствительность по факту теперь задаётся длиной дуги, так что фактор можно держать =1<br>
&#9;&#9;self.rotate_sensitivity: float = rotate_sensitivity<br>
<br>
&#9;&#9;self.set_enabled(False)<br>
<br>
&#9;# ---------- утилита: пересечение луча с плоскостью ----------<br>
<br>
&#9;@staticmethod<br>
&#9;def _ray_plane_intersection(ray, plane_origin: np.ndarray, plane_normal: np.ndarray):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Возвращает точку пересечения луча с плоскостью (origin, normal),<br>
&#9;&#9;либо None, если луч почти параллелен плоскости.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;n = np.asarray(plane_normal, dtype=float)<br>
&#9;&#9;n_norm = np.linalg.norm(n)<br>
&#9;&#9;if n_norm == 0.0:<br>
&#9;&#9;&#9;return None<br>
&#9;&#9;n /= n_norm<br>
<br>
&#9;&#9;ro = np.asarray(ray.origin, dtype=float)<br>
&#9;&#9;rd = np.asarray(ray.direction, dtype=float)<br>
<br>
&#9;&#9;denom = float(np.dot(rd, n))<br>
&#9;&#9;if abs(denom) &lt; 1e-6:<br>
&#9;&#9;&#9;return None  # почти параллелен<br>
<br>
&#9;&#9;t = float(np.dot(plane_origin - ro, n) / denom)<br>
&#9;&#9;# можно не проверять знак t – это бесконечная плоскость, а не физический объект<br>
&#9;&#9;return ro + rd * t<br>
<br>
&#9;# ---------- привязка к целевому объекту ----------<br>
<br>
&#9;def set_target(self, target_entity: Entity | None):<br>
&#9;&#9;if target_entity is not None and target_entity.pickable is False:<br>
&#9;&#9;&#9;target_entity = None<br>
<br>
&#9;&#9;self._end_drag()<br>
<br>
&#9;&#9;self.target = target_entity<br>
&#9;&#9;if self.target is None:<br>
&#9;&#9;&#9;self.set_enabled(False)<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;self.set_enabled(True)<br>
<br>
&#9;&#9;self.gizmo.transform.relocate_global(<br>
&#9;&#9;&#9;self.target.transform.global_pose()<br>
&#9;&#9;)<br>
<br>
&#9;def set_enabled(self, flag: bool):<br>
&#9;&#9;self.enabled = flag<br>
&#9;&#9;self.gizmo.set_visible(flag)<br>
<br>
&#9;# ---------- публичные вызовы из EditorWindow ----------<br>
<br>
&#9;def start_translate_from_pick(self, axis: str, viewport, x: float, y: float):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Вызывается EditorWindow из _after_render,<br>
&#9;&#9;когда пик показал, что кликнули по стрелке гизмо.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;if not self.enabled or self.target is None:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;self._start_move(axis, viewport, x, y)<br>
<br>
&#9;def start_rotate_from_pick(self, axis: str, viewport, x: float, y: float):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Аналогично, но для кольца вращения.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;if not self.enabled or self.target is None:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;self._start_rotate(axis, viewport, x, y)<br>
<br>
&#9;# ---------- события мыши от движка ----------<br>
<br>
&#9;def on_mouse_button(self, viewport, button, action, mods):<br>
&#9;&#9;if not self.enabled:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;if button != 0:<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;# action == 0 -&gt; release<br>
&#9;&#9;if action == 0:<br>
&#9;&#9;&#9;self._end_drag()<br>
<br>
&#9;def on_mouse_move(self, viewport, x, y, dx, dy):<br>
&#9;&#9;if not self.enabled or not self.dragging or self.target is None:<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;if self.drag_mode == &quot;move&quot;:<br>
&#9;&#9;&#9;self._update_move(viewport, x, y)<br>
&#9;&#9;elif self.drag_mode == &quot;rotate&quot;:<br>
&#9;&#9;&#9;self._update_rotate(viewport, x, y)<br>
<br>
&#9;# ---------- внутренняя логика начала / конца драга ----------<br>
<br>
&#9;def _end_drag(self):<br>
&#9;&#9;self.dragging = False<br>
&#9;&#9;self.drag_mode = None<br>
&#9;&#9;self.active_axis = None<br>
<br>
&#9;&#9;self.axis_vec = None<br>
&#9;&#9;self.axis_point = None<br>
&#9;&#9;self.grab_offset = None<br>
&#9;&#9;self.start_target_pos = None<br>
<br>
&#9;&#9;self.start_target_ang = None<br>
&#9;&#9;self.rot_axis = None<br>
&#9;&#9;self.rot_plane_origin = None<br>
&#9;&#9;self.rot_vec0 = None<br>
<br>
&#9;&#9;self.start_mouse_x = 0.0<br>
&#9;&#9;self.start_mouse_y = 0.0<br>
<br>
&#9;# ---------- ПЕРЕМЕЩЕНИЕ ----------<br>
<br>
&#9;def _start_move(self, axis: str, viewport, x: float, y: float):<br>
&#9;&#9;self.dragging = True<br>
&#9;&#9;self.drag_mode = &quot;move&quot;<br>
&#9;&#9;self.active_axis = axis<br>
<br>
&#9;&#9;pose = self.target.transform.global_pose()<br>
&#9;&#9;self.start_target_pos = pose.lin.copy()<br>
<br>
&#9;&#9;self.axis_vec = self._get_axis_vector(axis)<br>
&#9;&#9;self.axis_point = self.start_target_pos.copy()<br>
<br>
&#9;&#9;ray = viewport.screen_point_to_ray(x, y)<br>
&#9;&#9;if ray is None or self.axis_vec is None:<br>
&#9;&#9;&#9;self._end_drag()<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;_, axis_hit_point = closest_point_on_axis_from_ray(<br>
&#9;&#9;&#9;axis_point=self.axis_point,<br>
&#9;&#9;&#9;axis_dir=self.axis_vec,<br>
&#9;&#9;&#9;ray_origin=ray.origin,<br>
&#9;&#9;&#9;ray_dir=ray.direction<br>
&#9;&#9;)<br>
<br>
&#9;&#9;self.grab_offset = self.start_target_pos - axis_hit_point<br>
<br>
&#9;def _update_move(self, viewport, x: float, y: float):<br>
&#9;&#9;if (<br>
&#9;&#9;&#9;self.axis_vec is None or<br>
&#9;&#9;&#9;self.axis_point is None or<br>
&#9;&#9;&#9;self.grab_offset is None or<br>
&#9;&#9;&#9;self.start_target_pos is None<br>
&#9;&#9;):<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;ray = viewport.screen_point_to_ray(x, y)<br>
&#9;&#9;if ray is None:<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;_, axis_point_now = closest_point_on_axis_from_ray(<br>
&#9;&#9;&#9;axis_point=self.axis_point,<br>
&#9;&#9;&#9;axis_dir=self.axis_vec,<br>
&#9;&#9;&#9;ray_origin=ray.origin,<br>
&#9;&#9;&#9;ray_dir=ray.direction<br>
&#9;&#9;)<br>
<br>
&#9;&#9;new_pos = axis_point_now + self.grab_offset<br>
<br>
&#9;&#9;old_pose = self.target.transform.global_pose()<br>
&#9;&#9;new_pose = Pose3(<br>
&#9;&#9;&#9;lin=new_pos,<br>
&#9;&#9;&#9;ang=old_pose.ang<br>
&#9;&#9;)<br>
&#9;&#9;self.target.transform.relocate_global(new_pose)<br>
<br>
&#9;&#9;self.gizmo.transform.relocate_global(<br>
&#9;&#9;&#9;self.target.transform.global_pose()<br>
&#9;&#9;)<br>
<br>
&#9;def _get_axis_vector(self, axis: str) -&gt; np.ndarray:<br>
&#9;&#9;t = self.gizmo.transform<br>
<br>
&#9;&#9;if axis == &quot;x&quot;:<br>
&#9;&#9;&#9;v = t.right(1.0)<br>
&#9;&#9;elif axis == &quot;y&quot;:<br>
&#9;&#9;&#9;v = t.up(1.0)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;v = t.forward(1.0)<br>
<br>
&#9;&#9;v = np.asarray(v, dtype=np.float32)<br>
&#9;&#9;n = np.linalg.norm(v)<br>
&#9;&#9;return v if n == 0.0 else (v / n)<br>
<br>
&#9;# ---------- ВРАЩЕНИЕ (циркулярный драг) ----------<br>
<br>
&#9;def _start_rotate(self, axis: str, viewport, x: float, y: float):<br>
&#9;&#9;self.dragging = True<br>
&#9;&#9;self.drag_mode = &quot;rotate&quot;<br>
&#9;&#9;self.active_axis = axis<br>
<br>
&#9;&#9;self.start_mouse_x = x<br>
&#9;&#9;self.start_mouse_y = y<br>
<br>
&#9;&#9;pose = self.target.transform.global_pose()<br>
&#9;&#9;self.start_target_pos = pose.lin.copy()<br>
&#9;&#9;self.start_target_ang = pose.ang.copy()<br>
<br>
&#9;&#9;# мировая ось вращения – та же, что и направление стрелки/кольца<br>
&#9;&#9;self.rot_axis = self._get_axis_vector(axis)<br>
&#9;&#9;if self.rot_axis is None is None:<br>
&#9;&#9;&#9;self._end_drag()<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;# O – центр вращения (центр гизмо / объекта)<br>
&#9;&#9;self.rot_plane_origin = self.start_target_pos.copy()<br>
<br>
&#9;&#9;ray = viewport.screen_point_to_ray(x, y)<br>
&#9;&#9;if ray is None:<br>
&#9;&#9;&#9;self._end_drag()<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;hit = self._ray_plane_intersection(ray, self.rot_plane_origin, self.rot_axis)<br>
&#9;&#9;if hit is None:<br>
&#9;&#9;&#9;self._end_drag()<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;v0 = hit - self.rot_plane_origin<br>
&#9;&#9;norm_v0 = np.linalg.norm(v0)<br>
&#9;&#9;if norm_v0 &lt; 1e-6:<br>
&#9;&#9;&#9;# если вдруг попали почти в центр – зафиксируем какой-нибудь базовый вектор в плоскости<br>
&#9;&#9;&#9;# берём любое, не параллельное оси, и ортогонализуем<br>
&#9;&#9;&#9;tmp = np.array([1.0, 0.0, 0.0], dtype=float)<br>
&#9;&#9;&#9;if abs(np.dot(tmp, self.rot_axis)) &gt; 0.9:<br>
&#9;&#9;&#9;&#9;tmp = np.array([0.0, 1.0, 0.0], dtype=float)<br>
&#9;&#9;&#9;v0 = tmp - self.rot_axis * np.dot(tmp, self.rot_axis)<br>
&#9;&#9;&#9;norm_v0 = np.linalg.norm(v0)<br>
&#9;&#9;&#9;if norm_v0 &lt; 1e-6:<br>
&#9;&#9;&#9;&#9;self._end_drag()<br>
&#9;&#9;&#9;&#9;return<br>
<br>
&#9;&#9;self.rot_vec0 = v0 / norm_v0<br>
<br>
&#9;def _update_rotate(self, viewport, x: float, y: float):<br>
&#9;&#9;if (<br>
&#9;&#9;&#9;self.start_target_ang is None or<br>
&#9;&#9;&#9;self.start_target_pos is None or<br>
&#9;&#9;&#9;self.rot_axis is None or<br>
&#9;&#9;&#9;self.rot_plane_origin is None or<br>
&#9;&#9;&#9;self.rot_vec0 is None<br>
&#9;&#9;):<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;ray = viewport.screen_point_to_ray(x, y)<br>
&#9;&#9;if ray is None:<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;hit = self._ray_plane_intersection(ray, self.rot_plane_origin, self.rot_axis)<br>
&#9;&#9;if hit is None:<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;v1 = hit - self.rot_plane_origin<br>
&#9;&#9;norm_v1 = np.linalg.norm(v1)<br>
&#9;&#9;if norm_v1 &lt; 1e-6:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;v1 /= norm_v1<br>
<br>
&#9;&#9;# угол между v0 и v1<br>
&#9;&#9;dot = float(np.clip(np.dot(self.rot_vec0, v1), -1.0, 1.0))<br>
&#9;&#9;cross = np.cross(self.rot_vec0, v1)<br>
<br>
&#9;&#9;# модуль креста даёт sin, скалярное произведение – cos<br>
&#9;&#9;sin_angle = np.linalg.norm(cross)<br>
&#9;&#9;cos_angle = dot<br>
<br>
&#9;&#9;# знак через ориентацию относительно оси вращения<br>
&#9;&#9;sign = np.sign(np.dot(cross, self.rot_axis))<br>
&#9;&#9;if sign == 0.0:<br>
&#9;&#9;&#9;sign = 1.0  # если почти ноль – считаем положительным<br>
<br>
&#9;&#9;angle = float(np.arctan2(sin_angle, cos_angle)) * sign<br>
<br>
&#9;&#9;# если хочешь ослабить/усилить чувствительность — домножь на self.rotate_sensitivity<br>
&#9;&#9;angle *= self.rotate_sensitivity<br>
<br>
&#9;&#9;# кватернион инкрементального поворота вокруг rot_axis<br>
&#9;&#9;axis = self.rot_axis / np.linalg.norm(self.rot_axis)<br>
&#9;&#9;half = angle * 0.5<br>
&#9;&#9;s = np.sin(half)<br>
&#9;&#9;c = np.cos(half)<br>
&#9;&#9;dq = np.array([axis[0] * s, axis[1] * s, axis[2] * s, c], dtype=float)<br>
<br>
&#9;&#9;new_ang = qmul(dq, self.start_target_ang)<br>
<br>
&#9;&#9;norm_q = np.linalg.norm(new_ang)<br>
&#9;&#9;if norm_q &gt; 0.0:<br>
&#9;&#9;&#9;new_ang /= norm_q<br>
<br>
&#9;&#9;new_pose = Pose3(<br>
&#9;&#9;&#9;lin=self.start_target_pos,<br>
&#9;&#9;&#9;ang=new_ang<br>
&#9;&#9;)<br>
<br>
&#9;&#9;self.target.transform.relocate_global(new_pose)<br>
<br>
&#9;&#9;self.gizmo.transform.relocate_global(<br>
&#9;&#9;&#9;self.target.transform.global_pose()<br>
&#9;&#9;)<br>
<!-- END SCAT CODE -->
</body>
</html>
