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
&#9;Entity,<br>
&#9;MeshDrawable,<br>
&#9;Scene,<br>
&#9;Material,<br>
&#9;VisualizationWorld,<br>
&#9;PerspectiveCameraComponent,<br>
&#9;OrbitCameraController,<br>
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
&#9;v_normal = mat3(transpose(inverse(u_model))) * a_normal;<br>
&#9;gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);<br>
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
&#9;vec3 n = normalize(v_normal);<br>
&#9;float ndotl = max(dot(n, vec3(0.2, 0.6, 0.5)), 0.0);<br>
&#9;vec3 color = u_color.rgb * (0.25 + 0.75 * ndotl);<br>
&#9;FragColor = vec4(color, u_color.a);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
def build_scene(world: VisualizationWorld) -&gt; tuple[Scene, PerspectiveCameraComponent]:<br>
&#9;&quot;&quot;&quot;Создаём простую сцену с шаром и skybox.&quot;&quot;&quot;<br>
&#9;shader = ShaderProgram(VERT, FRAG)<br>
&#9;material = Material(<br>
&#9;&#9;shader=shader,<br>
&#9;&#9;color=np.array([0.3, 0.7, 0.9, 1.0], dtype=np.float32),<br>
&#9;)<br>
&#9;mesh = MeshDrawable(UVSphereMesh(radius=1.0, n_meridians=32, n_parallels=16))<br>
<br>
&#9;sphere = Entity(pose=Pose3.identity(), name=&quot;sphere&quot;)<br>
&#9;sphere.add_component(MeshRenderer(mesh, material))<br>
<br>
&#9;scene = Scene()<br>
&#9;scene.add(sphere)<br>
&#9;scene.add(SkyBoxEntity())<br>
&#9;world.add_scene(scene)<br>
<br>
&#9;cam_entity = Entity(name=&quot;camera&quot;)<br>
&#9;camera = PerspectiveCameraComponent()<br>
&#9;cam_entity.add_component(camera)<br>
&#9;cam_entity.add_component(OrbitCameraController(radius=4.0))<br>
&#9;scene.add(cam_entity)<br>
<br>
&#9;return scene, camera<br>
<br>
<br>
def main():<br>
&#9;# 1) Создаём Qt backend — внутри поднимется QApplication,<br>
&#9;#    поэтому до этого нельзя создавать QtWidgets.QWidget().<br>
&#9;qt_backend = QtWindowBackend()<br>
<br>
&#9;# 2) Создаём мир визуализации с Qt окном.<br>
&#9;world = VisualizationWorld(window_backend=qt_backend)<br>
&#9;scene, camera = build_scene(world)<br>
<br>
&#9;# 3) Дальше обычный Qt-интерфейс.<br>
&#9;main_window = QtWidgets.QMainWindow()<br>
&#9;central = QtWidgets.QWidget()<br>
&#9;layout = QtWidgets.QVBoxLayout(central)<br>
&#9;layout.setContentsMargins(0, 0, 0, 0)<br>
&#9;layout.setSpacing(6)<br>
<br>
&#9;# 4) Создаём окно визуализации как &quot;дочернее&quot; к central.<br>
&#9;#    QtWindowBackend внутри:<br>
&#9;#      - создаст QOpenGLWindow,<br>
&#9;#      - обернёт его в QWidget.createWindowContainer(parent),<br>
&#9;#      - вернёт handle, у которого .widget — это либо контейнер, либо само окно.<br>
&#9;vis_window = world.create_window(<br>
&#9;&#9;width=800,<br>
&#9;&#9;height=600,<br>
&#9;&#9;title=&quot;termin Qt embed&quot;,<br>
&#9;&#9;parent=central,  # ключевой момент — передаём parent<br>
&#9;)<br>
<br>
<br>
&#9;vis_window.add_viewport(scene, camera)<br>
<br>
&#9;# handle.widget должен вернуть Qt-вский виджет (container), который можно добавить в layout<br>
&#9;layout.addWidget(vis_window.handle.widget)<br>
<br>
&#9;quit_btn = QtWidgets.QPushButton(&quot;Закрыть&quot;)<br>
<br>
&#9;def close_all():<br>
&#9;&#9;vis_window.close()<br>
&#9;&#9;main_window.close()<br>
<br>
&#9;quit_btn.clicked.connect(close_all)<br>
&#9;layout.addWidget(quit_btn)<br>
<br>
&#9;main_window.setCentralWidget(central)<br>
&#9;main_window.resize(900, 700)<br>
&#9;main_window.setWindowTitle(&quot;Qt + termin visualization&quot;)<br>
&#9;main_window.show()<br>
<br>
&#9;# 5) Главный цикл: внутри будет<br>
&#9;#    - world.run() → while windows:<br>
&#9;#        - window.render()<br>
&#9;#        - window_backend.poll_events()<br>
&#9;#<br>
&#9;#    В Qt backend poll_events() делает app.processEvents(),<br>
&#9;#    так что отдельного app.exec_() вызывать не надо.<br>
&#9;world.run()<br>
<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
&#9;main()<br>
<!-- END SCAT CODE -->
</body>
</html>
