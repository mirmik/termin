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
    &quot;&quot;&quot;<br>
    Находит ближайшую точку на прямой (axis_point + t * axis_dir) к лучу (ray_origin + s * ray_dir),<br>
    возвращает параметр t и саму точку.<br>
    &quot;&quot;&quot;<br>
    p = np.asarray(axis_point, dtype=np.float32)<br>
    a = np.asarray(axis_dir, dtype=np.float32)<br>
    o = np.asarray(ray_origin, dtype=np.float32)<br>
    d = np.asarray(ray_dir, dtype=np.float32)<br>
<br>
    a_norm = np.linalg.norm(a)<br>
    if a_norm == 0:<br>
        return 0.0, p.copy()<br>
    a /= a_norm<br>
<br>
    d_norm = np.linalg.norm(d)<br>
    if d_norm == 0:<br>
        return 0.0, p.copy()<br>
    d /= d_norm<br>
<br>
    w0 = p - o<br>
    a_dot_d = np.dot(a, d)<br>
    denom = 1.0 - a_dot_d * a_dot_d<br>
<br>
    if float(np.abs(denom)) &lt; 1e-6:<br>
        t = -np.dot(w0, a)<br>
        return t, p + a * t<br>
<br>
    w0_dot_d = np.dot(w0, d)<br>
    w0_dot_a = np.dot(w0, a)<br>
<br>
    t = (a_dot_d * w0_dot_d - w0_dot_a) / denom<br>
    point_on_axis = p + a * t<br>
    return t, point_on_axis<br>
<br>
<br>
def rotation_matrix_from_axis_angle(axis_vec: np.ndarray, angle: float) -&gt; np.ndarray:<br>
    &quot;&quot;&quot;<br>
    Строит матрицу поворота (3×3) вокруг произвольной оси.<br>
    Ось задаётся в мировых координатах.<br>
    &quot;&quot;&quot;<br>
    axis = np.asarray(axis_vec, dtype=float)<br>
    n = np.linalg.norm(axis)<br>
    if n == 0.0:<br>
        return np.eye(3, dtype=float)<br>
    axis /= n<br>
<br>
    x, y, z = axis<br>
    c = float(np.cos(angle))<br>
    s = float(np.sin(angle))<br>
    C = 1.0 - c<br>
<br>
    return np.array(<br>
        [<br>
            [x * x * C + c,     x * y * C - z * s, x * z * C + y * s],<br>
            [y * x * C + z * s, y * y * C + c,     y * z * C - x * s],<br>
            [z * x * C - y * s, z * y * C + x * s, z * z * C + c],<br>
        ],<br>
        dtype=float,<br>
    )<br>
<br>
<br>
# ---------- ГРАФИЧЕСКИЕ ОБЪЕКТЫ ГИЗМО ----------<br>
<br>
class GizmoArrow(Entity):<br>
    &quot;&quot;&quot;<br>
    Стрелка гизмо для перемещения вдоль одной оси.<br>
    Состоит из цилиндра (ствол) и конуса (наконечник).<br>
    Базовая модель ориентирована вдоль +Y.<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(self, axis: str, length=1.0, color=(1.0, 0.0, 0.0, 1.0)):<br>
        super().__init__(<br>
            Pose3.identity(),<br>
            name=f&quot;gizmo_axis_{axis}&quot;,<br>
            pickable=True,<br>
            selectable=False<br>
        )<br>
<br>
        self.axis = axis<br>
        shaft_len = length * 0.75<br>
        head_len = length * 0.25<br>
<br>
        # тут же можно &quot;утолщать&quot; геометрию, чтобы легче было попадать мышкой<br>
        shaft = CylinderMesh(radius=0.03, height=shaft_len, segments=24)<br>
        head = ConeMesh(radius=0.06, height=head_len, segments=24)<br>
<br>
        mat = Material(color=color)<br>
<br>
        # цилиндр (ствол)<br>
        shaft_ent = Entity(<br>
            Pose3.translation(0, shaft_len * 0.5, 0),<br>
            name=f&quot;{axis}_shaft&quot;,<br>
            pickable=True,<br>
            selectable=False<br>
        )<br>
        shaft_ent.add_component(MeshRenderer(shaft, mat))<br>
        self.shaft_ent = shaft_ent<br>
        self.transform.add_child(shaft_ent.transform)<br>
<br>
        # конус (наконечник)<br>
        head_ent = Entity(<br>
            Pose3.translation(0, shaft_len + head_len * 0.5, 0),<br>
            name=f&quot;{axis}_head&quot;,<br>
            pickable=True,<br>
            selectable=False<br>
        )<br>
        head_ent.add_component(MeshRenderer(head, mat))<br>
        self.head_ent = head_ent<br>
        self.transform.add_child(head_ent.transform)<br>
<br>
        # ориентация оси:<br>
        # базовая модель ориентирована вдоль +Y,<br>
        # поворачиваем, чтобы она смотрела вдоль нужной мировой оси<br>
        if axis == &quot;x&quot;:<br>
            # местная ось Y → мировая X<br>
            self.transform.relocate(Pose3.rotateZ(-np.pi / 2.0))<br>
        elif axis == &quot;z&quot;:<br>
            # местная ось Y → мировая Z<br>
            self.transform.relocate(Pose3.rotateX(np.pi / 2.0))<br>
        # для оси Y поворот не нужен<br>
<br>
<br>
class GizmoRing(Entity):<br>
    &quot;&quot;&quot;<br>
    Кольцо для гизмо вращения вокруг одной оси.<br>
    Базовый меш лежит в XZ-плоскости, нормаль по +Y.<br>
    Ориентацией transform доводим до нужной оси.<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(self, axis: str, radius=1.2, thickness=0.05, color=(1.0, 1.0, 0.0, 1.0)):<br>
        super().__init__(<br>
            Pose3.identity(),<br>
            name=f&quot;gizmo_rot_{axis}&quot;,<br>
            pickable=True,<br>
            selectable=False<br>
        )<br>
<br>
        self.axis = axis<br>
<br>
        # здесь толщина кольца и радиус — естественное место для &quot;утолщённой&quot; геометрии<br>
        ring_mesh = RingMesh(radius=radius, thickness=thickness, segments=48)<br>
        mat = Material(color=color)<br>
<br>
        ring_ent = Entity(<br>
            Pose3.identity(),<br>
            name=f&quot;{axis}_ring&quot;,<br>
            pickable=True,<br>
            selectable=False<br>
        )<br>
        ring_ent.add_component(MeshRenderer(ring_mesh, mat))<br>
        self.ring_ent = ring_ent<br>
        self.transform.add_child(ring_ent.transform)<br>
<br>
        # базовый RingMesh имеет нормаль (ось) вдоль +Y,<br>
        # поворачиваем так же, как стрелки:<br>
        if axis == &quot;x&quot;:<br>
            # нормаль Y → X<br>
            self.transform.relocate(Pose3.rotateZ(-np.pi / 2.0))<br>
        elif axis == &quot;z&quot;:<br>
            # нормаль Y → Z<br>
            self.transform.relocate(Pose3.rotateX(np.pi / 2.0))<br>
        # для оси Y поворот не нужен<br>
<br>
<br>
class GizmoEntity(Entity):<br>
    &quot;&quot;&quot;<br>
    Общая сущность гизмо, которая содержит:<br>
    - стрелки для перемещения<br>
    - кольца для вращения<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(self, size=1.0):<br>
        super().__init__(<br>
            Pose3.identity(),<br>
            name=&quot;gizmo&quot;,<br>
            pickable=True,<br>
            selectable=False<br>
        )<br>
<br>
        # стрелки перемещения<br>
        self.x = GizmoArrow(&quot;x&quot;, length=size, color=(1, 0, 0, 1))<br>
        self.y = GizmoArrow(&quot;y&quot;, length=size, color=(0, 1, 0, 1))<br>
        self.z = GizmoArrow(&quot;z&quot;, length=size, color=(0, 0, 1, 1))<br>
<br>
        self.transform.add_child(self.x.transform)<br>
        self.transform.add_child(self.y.transform)<br>
        self.transform.add_child(self.z.transform)<br>
<br>
        # кольца вращения (слегка больше по радиусу)<br>
        ring_radius = size * 1.25<br>
        ring_thickness = size * 0.05<br>
<br>
        self.rx = GizmoRing(&quot;x&quot;, radius=ring_radius, thickness=ring_thickness, color=(1, 0.3, 0.3, 1))<br>
        self.ry = GizmoRing(&quot;y&quot;, radius=ring_radius, thickness=ring_thickness, color=(0.3, 1, 0.3, 1))<br>
        self.rz = GizmoRing(&quot;z&quot;, radius=ring_radius, thickness=ring_thickness, color=(0.3, 0.3, 1, 1))<br>
<br>
        self.transform.add_child(self.rx.transform)<br>
        self.transform.add_child(self.ry.transform)<br>
        self.transform.add_child(self.rz.transform)<br>
<br>
<br>
# ---------- ЕДИНЫЙ КОНТРОЛЛЕР ПЕРЕМЕЩЕНИЯ+ВРАЩЕНИЯ ----------<br>
<br>
class GizmoMoveController(InputComponent):<br>
    &quot;&quot;&quot;<br>
    Единый контроллер:<br>
    - перемещение по стрелкам (gizmo_axis_x / y / z)<br>
    - вращение по кольцам   (gizmo_rot_x / y / z)<br>
<br>
    ВАЖНО:<br>
    - пиккинг делает EditorWindow через pick_entity_at<br>
    - сюда прилетает только &quot;ось и режим&quot; через start_*_from_pick<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(self, gizmo_entity: GizmoEntity, scene, rotate_sensitivity: float = 1.0):<br>
        super().__init__()<br>
        self.gizmo = gizmo_entity<br>
        self.scene = scene  # сейчас почти не используется, но оставим<br>
<br>
        self.enabled = False<br>
        self.target: Entity | None = None<br>
<br>
        # общее состояние драга<br>
        self.dragging: bool = False<br>
        self.drag_mode: str | None = None  # &quot;move&quot; или &quot;rotate&quot;<br>
        self.active_axis: str | None = None<br>
<br>
        # --- состояние для перемещения ---<br>
        self.axis_vec: np.ndarray | None = None       # направление оси (мир)<br>
        self.axis_point: np.ndarray | None = None     # точка на оси<br>
        self.grab_offset: np.ndarray | None = None    # сдвиг от оси до центра объекта<br>
        self.start_target_pos: np.ndarray | None = None<br>
<br>
        # --- состояние для вращения (циркулярный драг) ---<br>
        self.start_target_ang: np.ndarray | None = None  # кватернион (x, y, z, w)<br>
        self.rot_axis: np.ndarray | None = None          # нормаль плоскости (ось вращения, мир)<br>
        self.rot_plane_origin: np.ndarray | None = None  # O – центр вращения<br>
        self.rot_vec0: np.ndarray | None = None          # нормализованный вектор OA в плоскости<br>
<br>
        # координаты мыши на старте – больше для дебага, но пусть остаются<br>
        self.start_mouse_x: float = 0.0<br>
        self.start_mouse_y: float = 0.0<br>
<br>
        # чувствительность по факту теперь задаётся длиной дуги, так что фактор можно держать =1<br>
        self.rotate_sensitivity: float = rotate_sensitivity<br>
<br>
        self.set_enabled(False)<br>
<br>
    # ---------- утилита: пересечение луча с плоскостью ----------<br>
<br>
    @staticmethod<br>
    def _ray_plane_intersection(ray, plane_origin: np.ndarray, plane_normal: np.ndarray):<br>
        &quot;&quot;&quot;<br>
        Возвращает точку пересечения луча с плоскостью (origin, normal),<br>
        либо None, если луч почти параллелен плоскости.<br>
        &quot;&quot;&quot;<br>
        n = np.asarray(plane_normal, dtype=float)<br>
        n_norm = np.linalg.norm(n)<br>
        if n_norm == 0.0:<br>
            return None<br>
        n /= n_norm<br>
<br>
        ro = np.asarray(ray.origin, dtype=float)<br>
        rd = np.asarray(ray.direction, dtype=float)<br>
<br>
        denom = float(np.dot(rd, n))<br>
        if abs(denom) &lt; 1e-6:<br>
            return None  # почти параллелен<br>
<br>
        t = float(np.dot(plane_origin - ro, n) / denom)<br>
        # можно не проверять знак t – это бесконечная плоскость, а не физический объект<br>
        return ro + rd * t<br>
<br>
    # ---------- привязка к целевому объекту ----------<br>
<br>
    def set_target(self, target_entity: Entity | None):<br>
        if target_entity is not None and target_entity.pickable is False:<br>
            target_entity = None<br>
<br>
        self._end_drag()<br>
<br>
        self.target = target_entity<br>
        if self.target is None:<br>
            self.set_enabled(False)<br>
            return<br>
<br>
        self.set_enabled(True)<br>
<br>
        self.gizmo.transform.relocate_global(<br>
            self.target.transform.global_pose()<br>
        )<br>
<br>
    def set_enabled(self, flag: bool):<br>
        self.enabled = flag<br>
        self.gizmo.set_visible(flag)<br>
<br>
    # ---------- публичные вызовы из EditorWindow ----------<br>
<br>
    def start_translate_from_pick(self, axis: str, viewport, x: float, y: float):<br>
        &quot;&quot;&quot;<br>
        Вызывается EditorWindow из _after_render,<br>
        когда пик показал, что кликнули по стрелке гизмо.<br>
        &quot;&quot;&quot;<br>
        if not self.enabled or self.target is None:<br>
            return<br>
        self._start_move(axis, viewport, x, y)<br>
<br>
    def start_rotate_from_pick(self, axis: str, viewport, x: float, y: float):<br>
        &quot;&quot;&quot;<br>
        Аналогично, но для кольца вращения.<br>
        &quot;&quot;&quot;<br>
        if not self.enabled or self.target is None:<br>
            return<br>
        self._start_rotate(axis, viewport, x, y)<br>
<br>
    # ---------- события мыши от движка ----------<br>
<br>
    def on_mouse_button(self, viewport, button, action, mods):<br>
        if not self.enabled:<br>
            return<br>
        if button != 0:<br>
            return<br>
<br>
        # action == 0 -&gt; release<br>
        if action == 0:<br>
            self._end_drag()<br>
<br>
    def on_mouse_move(self, viewport, x, y, dx, dy):<br>
        if not self.enabled or not self.dragging or self.target is None:<br>
            return<br>
<br>
        if self.drag_mode == &quot;move&quot;:<br>
            self._update_move(viewport, x, y)<br>
        elif self.drag_mode == &quot;rotate&quot;:<br>
            self._update_rotate(viewport, x, y)<br>
<br>
    # ---------- внутренняя логика начала / конца драга ----------<br>
<br>
    def _end_drag(self):<br>
        self.dragging = False<br>
        self.drag_mode = None<br>
        self.active_axis = None<br>
<br>
        self.axis_vec = None<br>
        self.axis_point = None<br>
        self.grab_offset = None<br>
        self.start_target_pos = None<br>
<br>
        self.start_target_ang = None<br>
        self.rot_axis = None<br>
        self.rot_plane_origin = None<br>
        self.rot_vec0 = None<br>
<br>
        self.start_mouse_x = 0.0<br>
        self.start_mouse_y = 0.0<br>
<br>
    # ---------- ПЕРЕМЕЩЕНИЕ ----------<br>
<br>
    def _start_move(self, axis: str, viewport, x: float, y: float):<br>
        self.dragging = True<br>
        self.drag_mode = &quot;move&quot;<br>
        self.active_axis = axis<br>
<br>
        pose = self.target.transform.global_pose()<br>
        self.start_target_pos = pose.lin.copy()<br>
<br>
        self.axis_vec = self._get_axis_vector(axis)<br>
        self.axis_point = self.start_target_pos.copy()<br>
<br>
        ray = viewport.screen_point_to_ray(x, y)<br>
        if ray is None or self.axis_vec is None:<br>
            self._end_drag()<br>
            return<br>
<br>
        _, axis_hit_point = closest_point_on_axis_from_ray(<br>
            axis_point=self.axis_point,<br>
            axis_dir=self.axis_vec,<br>
            ray_origin=ray.origin,<br>
            ray_dir=ray.direction<br>
        )<br>
<br>
        self.grab_offset = self.start_target_pos - axis_hit_point<br>
<br>
    def _update_move(self, viewport, x: float, y: float):<br>
        if (<br>
            self.axis_vec is None or<br>
            self.axis_point is None or<br>
            self.grab_offset is None or<br>
            self.start_target_pos is None<br>
        ):<br>
            return<br>
<br>
        ray = viewport.screen_point_to_ray(x, y)<br>
        if ray is None:<br>
            return<br>
<br>
        _, axis_point_now = closest_point_on_axis_from_ray(<br>
            axis_point=self.axis_point,<br>
            axis_dir=self.axis_vec,<br>
            ray_origin=ray.origin,<br>
            ray_dir=ray.direction<br>
        )<br>
<br>
        new_pos = axis_point_now + self.grab_offset<br>
<br>
        old_pose = self.target.transform.global_pose()<br>
        new_pose = Pose3(<br>
            lin=new_pos,<br>
            ang=old_pose.ang<br>
        )<br>
        self.target.transform.relocate_global(new_pose)<br>
<br>
        self.gizmo.transform.relocate_global(<br>
            self.target.transform.global_pose()<br>
        )<br>
<br>
    def _get_axis_vector(self, axis: str) -&gt; np.ndarray:<br>
        t = self.gizmo.transform<br>
<br>
        if axis == &quot;x&quot;:<br>
            v = t.right(1.0)<br>
        elif axis == &quot;y&quot;:<br>
            v = t.up(1.0)<br>
        else:<br>
            v = t.forward(1.0)<br>
<br>
        v = np.asarray(v, dtype=np.float32)<br>
        n = np.linalg.norm(v)<br>
        return v if n == 0.0 else (v / n)<br>
<br>
    # ---------- ВРАЩЕНИЕ (циркулярный драг) ----------<br>
<br>
    def _start_rotate(self, axis: str, viewport, x: float, y: float):<br>
        self.dragging = True<br>
        self.drag_mode = &quot;rotate&quot;<br>
        self.active_axis = axis<br>
<br>
        self.start_mouse_x = x<br>
        self.start_mouse_y = y<br>
<br>
        pose = self.target.transform.global_pose()<br>
        self.start_target_pos = pose.lin.copy()<br>
        self.start_target_ang = pose.ang.copy()<br>
<br>
        # мировая ось вращения – та же, что и направление стрелки/кольца<br>
        self.rot_axis = self._get_axis_vector(axis)<br>
        if self.rot_axis is None is None:<br>
            self._end_drag()<br>
            return<br>
<br>
        # O – центр вращения (центр гизмо / объекта)<br>
        self.rot_plane_origin = self.start_target_pos.copy()<br>
<br>
        ray = viewport.screen_point_to_ray(x, y)<br>
        if ray is None:<br>
            self._end_drag()<br>
            return<br>
<br>
        hit = self._ray_plane_intersection(ray, self.rot_plane_origin, self.rot_axis)<br>
        if hit is None:<br>
            self._end_drag()<br>
            return<br>
<br>
        v0 = hit - self.rot_plane_origin<br>
        norm_v0 = np.linalg.norm(v0)<br>
        if norm_v0 &lt; 1e-6:<br>
            # если вдруг попали почти в центр – зафиксируем какой-нибудь базовый вектор в плоскости<br>
            # берём любое, не параллельное оси, и ортогонализуем<br>
            tmp = np.array([1.0, 0.0, 0.0], dtype=float)<br>
            if abs(np.dot(tmp, self.rot_axis)) &gt; 0.9:<br>
                tmp = np.array([0.0, 1.0, 0.0], dtype=float)<br>
            v0 = tmp - self.rot_axis * np.dot(tmp, self.rot_axis)<br>
            norm_v0 = np.linalg.norm(v0)<br>
            if norm_v0 &lt; 1e-6:<br>
                self._end_drag()<br>
                return<br>
<br>
        self.rot_vec0 = v0 / norm_v0<br>
<br>
    def _update_rotate(self, viewport, x: float, y: float):<br>
        if (<br>
            self.start_target_ang is None or<br>
            self.start_target_pos is None or<br>
            self.rot_axis is None or<br>
            self.rot_plane_origin is None or<br>
            self.rot_vec0 is None<br>
        ):<br>
            return<br>
<br>
        ray = viewport.screen_point_to_ray(x, y)<br>
        if ray is None:<br>
            return<br>
<br>
        hit = self._ray_plane_intersection(ray, self.rot_plane_origin, self.rot_axis)<br>
        if hit is None:<br>
            return<br>
<br>
        v1 = hit - self.rot_plane_origin<br>
        norm_v1 = np.linalg.norm(v1)<br>
        if norm_v1 &lt; 1e-6:<br>
            return<br>
        v1 /= norm_v1<br>
<br>
        # угол между v0 и v1<br>
        dot = float(np.clip(np.dot(self.rot_vec0, v1), -1.0, 1.0))<br>
        cross = np.cross(self.rot_vec0, v1)<br>
<br>
        # модуль креста даёт sin, скалярное произведение – cos<br>
        sin_angle = np.linalg.norm(cross)<br>
        cos_angle = dot<br>
<br>
        # знак через ориентацию относительно оси вращения<br>
        sign = np.sign(np.dot(cross, self.rot_axis))<br>
        if sign == 0.0:<br>
            sign = 1.0  # если почти ноль – считаем положительным<br>
<br>
        angle = float(np.arctan2(sin_angle, cos_angle)) * sign<br>
<br>
        # если хочешь ослабить/усилить чувствительность — домножь на self.rotate_sensitivity<br>
        angle *= self.rotate_sensitivity<br>
<br>
        # кватернион инкрементального поворота вокруг rot_axis<br>
        axis = self.rot_axis / np.linalg.norm(self.rot_axis)<br>
        half = angle * 0.5<br>
        s = np.sin(half)<br>
        c = np.cos(half)<br>
        dq = np.array([axis[0] * s, axis[1] * s, axis[2] * s, c], dtype=float)<br>
<br>
        new_ang = qmul(dq, self.start_target_ang)<br>
<br>
        norm_q = np.linalg.norm(new_ang)<br>
        if norm_q &gt; 0.0:<br>
            new_ang /= norm_q<br>
<br>
        new_pose = Pose3(<br>
            lin=self.start_target_pos,<br>
            ang=new_ang<br>
        )<br>
<br>
        self.target.transform.relocate_global(new_pose)<br>
<br>
        self.gizmo.transform.relocate_global(<br>
            self.target.transform.global_pose()<br>
        )<br>
<!-- END SCAT CODE -->
</body>
</html>
