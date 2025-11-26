<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/visual/qt_embed.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Embed termin visualization view inside a PyQt5 application.&quot;&quot;&quot;<br>
<br>
from __future__ import annotations<br>
<br>
import numpy as np<br>
from PyQt5 import QtWidgets<br>
<br>
from termin.geombase.pose3 import Pose3<br>
from termin.mesh.mesh import UVSphereMesh<br>
from termin.visualization import (<br>
    Entity,<br>
    MeshDrawable,<br>
    Scene,<br>
    Material,<br>
    VisualizationWorld,<br>
    PerspectiveCameraComponent,<br>
    OrbitCameraController,<br>
)<br>
from termin.visualization.components import MeshRenderer<br>
from termin.visualization.shader import ShaderProgram<br>
from termin.visualization.skybox import SkyBoxEntity<br>
from termin.visualization.backends.qt import QtWindowBackend<br>
<br>
<br>
VERT = &quot;&quot;&quot;<br>
#version 330 core<br>
layout(location = 0) in vec3 a_position;<br>
layout(location = 1) in vec3 a_normal;<br>
<br>
uniform mat4 u_model;<br>
uniform mat4 u_view;<br>
uniform mat4 u_projection;<br>
<br>
out vec3 v_normal;<br>
<br>
void main() {<br>
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;<br>
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
FRAG = &quot;&quot;&quot;<br>
#version 330 core<br>
in vec3 v_normal;<br>
uniform vec4 u_color;<br>
<br>
out vec4 FragColor;<br>
<br>
void main() {<br>
    vec3 n = normalize(v_normal);<br>
    float ndotl = max(dot(n, vec3(0.2, 0.6, 0.5)), 0.0);<br>
    vec3 color = u_color.rgb * (0.25 + 0.75 * ndotl);<br>
    FragColor = vec4(color, u_color.a);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
def build_scene(world: VisualizationWorld) -&gt; tuple[Scene, PerspectiveCameraComponent]:<br>
    &quot;&quot;&quot;Создаём простую сцену с шаром и skybox.&quot;&quot;&quot;<br>
    shader = ShaderProgram(VERT, FRAG)<br>
    material = Material(<br>
        shader=shader,<br>
        color=np.array([0.3, 0.7, 0.9, 1.0], dtype=np.float32),<br>
    )<br>
    mesh = MeshDrawable(UVSphereMesh(radius=1.0, n_meridians=32, n_parallels=16))<br>
<br>
    sphere = Entity(pose=Pose3.identity(), name=&quot;sphere&quot;)<br>
    sphere.add_component(MeshRenderer(mesh, material))<br>
<br>
    scene = Scene()<br>
    scene.add(sphere)<br>
    scene.add(SkyBoxEntity())<br>
    world.add_scene(scene)<br>
<br>
    cam_entity = Entity(name=&quot;camera&quot;)<br>
    camera = PerspectiveCameraComponent()<br>
    cam_entity.add_component(camera)<br>
    cam_entity.add_component(OrbitCameraController(radius=4.0))<br>
    scene.add(cam_entity)<br>
<br>
    return scene, camera<br>
<br>
<br>
def main():<br>
    # 1) Создаём Qt backend — внутри поднимется QApplication,<br>
    #    поэтому до этого нельзя создавать QtWidgets.QWidget().<br>
    qt_backend = QtWindowBackend()<br>
<br>
    # 2) Создаём мир визуализации с Qt окном.<br>
    world = VisualizationWorld(window_backend=qt_backend)<br>
    scene, camera = build_scene(world)<br>
<br>
    # 3) Дальше обычный Qt-интерфейс.<br>
    main_window = QtWidgets.QMainWindow()<br>
    central = QtWidgets.QWidget()<br>
    layout = QtWidgets.QVBoxLayout(central)<br>
    layout.setContentsMargins(0, 0, 0, 0)<br>
    layout.setSpacing(6)<br>
<br>
    # 4) Создаём окно визуализации как &quot;дочернее&quot; к central.<br>
    #    QtWindowBackend внутри:<br>
    #      - создаст QOpenGLWindow,<br>
    #      - обернёт его в QWidget.createWindowContainer(parent),<br>
    #      - вернёт handle, у которого .widget — это либо контейнер, либо само окно.<br>
    vis_window = world.create_window(<br>
        width=800,<br>
        height=600,<br>
        title=&quot;termin Qt embed&quot;,<br>
        parent=central,  # ключевой момент — передаём parent<br>
    )<br>
<br>
<br>
    vis_window.add_viewport(scene, camera)<br>
<br>
    # handle.widget должен вернуть Qt-вский виджет (container), который можно добавить в layout<br>
    layout.addWidget(vis_window.handle.widget)<br>
<br>
    quit_btn = QtWidgets.QPushButton(&quot;Закрыть&quot;)<br>
<br>
    def close_all():<br>
        vis_window.close()<br>
        main_window.close()<br>
<br>
    quit_btn.clicked.connect(close_all)<br>
    layout.addWidget(quit_btn)<br>
<br>
    main_window.setCentralWidget(central)<br>
    main_window.resize(900, 700)<br>
    main_window.setWindowTitle(&quot;Qt + termin visualization&quot;)<br>
    main_window.show()<br>
<br>
    # 5) Главный цикл: внутри будет<br>
    #    - world.run() → while windows:<br>
    #        - window.render()<br>
    #        - window_backend.poll_events()<br>
    #<br>
    #    В Qt backend poll_events() делает app.processEvents(),<br>
    #    так что отдельного app.exec_() вызывать не надо.<br>
    world.run()<br>
<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
    main()<br>
<!-- END SCAT CODE -->
</body>
</html>
