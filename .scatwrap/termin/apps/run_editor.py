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
    cube_mesh = CubeMesh()<br>
    cyl_mesh = CylinderMesh(radius=0.5, height=2.0)<br>
    drawable = MeshDrawable(cube_mesh)<br>
    drawable_cyl = MeshDrawable(cyl_mesh)<br>
    red_material = Material(color=np.array([0.8, 0.3, 0.3, 1.0], dtype=np.float32))<br>
    blue_material = Material(color=np.array([0.3, 0.3, 0.8, 1.0], dtype=np.float32))<br>
    green_material = Material(color=np.array([0.3, 0.8, 0.3, 1.0], dtype=np.float32))<br>
   <br>
    scene = Scene()<br>
<br>
<br>
    entity_cyl = Entity(pose=Pose3.identity(), name=&quot;cylinder&quot;)<br>
    entity_cyl.add_component(MeshRenderer(drawable_cyl, green_material))<br>
    entity_cyl.transform.relocate(Pose3(lin=np.array([-2.0, 0.0, 0.0]), ang=np.array([0.0, 0.0, 0.0, 1.0])))<br>
    scene.add(entity_cyl)<br>
<br>
    entity = Entity(pose=Pose3.identity(), name=&quot;cube1&quot;)<br>
    entity.add_component(MeshRenderer(drawable, red_material))<br>
    scene.add(entity)<br>
<br>
    entity2 = Entity(pose=Pose3.identity(), name=&quot;cube2&quot;)<br>
    entity2.add_component(MeshRenderer(drawable, blue_material))<br>
    entity2.transform.relocate(Pose3(lin=np.array([3.0, 0.0, 0.0]), ang=np.array([0.0, 0.0, 0.0, 1.0])))<br>
    scene.add(entity2)<br>
<br>
<br>
    skybox = SkyBoxEntity()<br>
    scene.add(skybox)<br>
<br>
    world.add_scene(scene)<br>
<br>
    return scene<br>
<br>
<br>
def apply_dark_palette(app: QApplication):<br>
    app.setStyle(&quot;Fusion&quot;)  # более аккуратный стиль, чем дефолтный<br>
<br>
    palette = QPalette()<br>
<br>
    # Базовые цвета<br>
    bg      = QColor(30, 30, 30)<br>
    window  = QColor(37, 37, 38)<br>
    base    = QColor(45, 45, 48)<br>
    text    = QColor(220, 220, 220)<br>
    disabled_text = QColor(128, 128, 128)<br>
    highlight = QColor(0, 120, 215)<br>
<br>
    palette.setColor(QPalette.Window, window)<br>
    palette.setColor(QPalette.WindowText, text)<br>
    palette.setColor(QPalette.Base, base)<br>
    palette.setColor(QPalette.AlternateBase, bg)<br>
    palette.setColor(QPalette.ToolTipBase, base)<br>
    palette.setColor(QPalette.ToolTipText, text)<br>
    palette.setColor(QPalette.Text, text)<br>
    palette.setColor(QPalette.Button, window)<br>
    palette.setColor(QPalette.ButtonText, text)<br>
    palette.setColor(QPalette.BrightText, QColor(255, 0, 0))<br>
<br>
    palette.setColor(QPalette.Highlight, highlight)<br>
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))<br>
<br>
    # Отключённые элементы<br>
    palette.setColor(QPalette.Disabled, QPalette.Text, disabled_text)<br>
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, disabled_text)<br>
    palette.setColor(QPalette.Disabled, QPalette.WindowText, disabled_text)<br>
<br>
    app.setPalette(palette)<br>
<br>
<br>
def run_editor():<br>
    set_default_graphics_backend(OpenGLGraphicsBackend())<br>
    set_default_window_backend(QtWindowBackend())<br>
<br>
    world = VisualizationWorld()<br>
    scene = build_scene(world)<br>
<br>
    app = QApplication(sys.argv)<br>
    apply_dark_palette(app)<br>
    win = EditorWindow(world, scene)<br>
    win.show()<br>
    app.exec_()<br>
<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
    run_editor()<br>
<!-- END SCAT CODE -->
</body>
</html>
