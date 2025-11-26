<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/apps/run_editor.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import sys<br>
from PyQt5.QtWidgets import QApplication<br>
from PyQt5.QtGui import QPalette, QColor<br>
<br>
from termin.visualization.backends import QtWindowBackend, OpenGLGraphicsBackend, set_default_graphics_backend, set_default_window_backend<br>
from termin.visualization.world import VisualizationWorld<br>
<br>
from editor_window import EditorWindow<br>
<br>
<br>
<br>
<br>
from termin.mesh.mesh import CubeMesh, CylinderMesh, Mesh3<br>
from termin.visualization.entity import Entity<br>
from termin.visualization.components import MeshRenderer<br>
from termin.visualization.world import VisualizationWorld<br>
from termin.visualization.mesh import MeshDrawable<br>
from termin.visualization.material import Material<br>
from termin.visualization.scene import Scene<br>
import numpy as np<br>
from termin.geombase.pose3 import Pose3<br>
from termin.visualization.skybox import SkyBoxEntity<br>
from termin.visualization.camera import PerspectiveCameraComponent, OrbitCameraController<br>
<br>
def build_scene(world):<br>
<br>
&#9;cube_mesh = CubeMesh()<br>
&#9;cyl_mesh = CylinderMesh(radius=0.5, height=2.0)<br>
&#9;drawable = MeshDrawable(cube_mesh)<br>
&#9;drawable_cyl = MeshDrawable(cyl_mesh)<br>
&#9;red_material = Material(color=np.array([0.8, 0.3, 0.3, 1.0], dtype=np.float32))<br>
&#9;blue_material = Material(color=np.array([0.3, 0.3, 0.8, 1.0], dtype=np.float32))<br>
&#9;green_material = Material(color=np.array([0.3, 0.8, 0.3, 1.0], dtype=np.float32))<br>
<br>
&#9;scene = Scene()<br>
<br>
<br>
&#9;entity_cyl = Entity(pose=Pose3.identity(), name=&quot;cylinder&quot;)<br>
&#9;entity_cyl.add_component(MeshRenderer(drawable_cyl, green_material))<br>
&#9;entity_cyl.transform.relocate(Pose3(lin=np.array([-2.0, 0.0, 0.0]), ang=np.array([0.0, 0.0, 0.0, 1.0])))<br>
&#9;scene.add(entity_cyl)<br>
<br>
&#9;entity = Entity(pose=Pose3.identity(), name=&quot;cube1&quot;)<br>
&#9;entity.add_component(MeshRenderer(drawable, red_material))<br>
&#9;scene.add(entity)<br>
<br>
&#9;entity2 = Entity(pose=Pose3.identity(), name=&quot;cube2&quot;)<br>
&#9;entity2.add_component(MeshRenderer(drawable, blue_material))<br>
&#9;entity2.transform.relocate(Pose3(lin=np.array([3.0, 0.0, 0.0]), ang=np.array([0.0, 0.0, 0.0, 1.0])))<br>
&#9;scene.add(entity2)<br>
<br>
<br>
&#9;skybox = SkyBoxEntity()<br>
&#9;scene.add(skybox)<br>
<br>
&#9;world.add_scene(scene)<br>
<br>
&#9;return scene<br>
<br>
<br>
def apply_dark_palette(app: QApplication):<br>
&#9;app.setStyle(&quot;Fusion&quot;)  # более аккуратный стиль, чем дефолтный<br>
<br>
&#9;palette = QPalette()<br>
<br>
&#9;# Базовые цвета<br>
&#9;bg      = QColor(30, 30, 30)<br>
&#9;window  = QColor(37, 37, 38)<br>
&#9;base    = QColor(45, 45, 48)<br>
&#9;text    = QColor(220, 220, 220)<br>
&#9;disabled_text = QColor(128, 128, 128)<br>
&#9;highlight = QColor(0, 120, 215)<br>
<br>
&#9;palette.setColor(QPalette.Window, window)<br>
&#9;palette.setColor(QPalette.WindowText, text)<br>
&#9;palette.setColor(QPalette.Base, base)<br>
&#9;palette.setColor(QPalette.AlternateBase, bg)<br>
&#9;palette.setColor(QPalette.ToolTipBase, base)<br>
&#9;palette.setColor(QPalette.ToolTipText, text)<br>
&#9;palette.setColor(QPalette.Text, text)<br>
&#9;palette.setColor(QPalette.Button, window)<br>
&#9;palette.setColor(QPalette.ButtonText, text)<br>
&#9;palette.setColor(QPalette.BrightText, QColor(255, 0, 0))<br>
<br>
&#9;palette.setColor(QPalette.Highlight, highlight)<br>
&#9;palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))<br>
<br>
&#9;# Отключённые элементы<br>
&#9;palette.setColor(QPalette.Disabled, QPalette.Text, disabled_text)<br>
&#9;palette.setColor(QPalette.Disabled, QPalette.ButtonText, disabled_text)<br>
&#9;palette.setColor(QPalette.Disabled, QPalette.WindowText, disabled_text)<br>
<br>
&#9;app.setPalette(palette)<br>
<br>
<br>
def run_editor():<br>
&#9;set_default_graphics_backend(OpenGLGraphicsBackend())<br>
&#9;set_default_window_backend(QtWindowBackend())<br>
<br>
&#9;world = VisualizationWorld()<br>
&#9;scene = build_scene(world)<br>
<br>
&#9;app = QApplication(sys.argv)<br>
&#9;apply_dark_palette(app)<br>
&#9;win = EditorWindow(world, scene)<br>
&#9;win.show()<br>
&#9;app.exec_()<br>
<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
&#9;run_editor()<br>
<!-- END SCAT CODE -->
</body>
</html>
