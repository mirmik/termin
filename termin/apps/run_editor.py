import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPalette, QColor

from termin.visualization.backends import QtWindowBackend, OpenGLGraphicsBackend, set_default_graphics_backend, set_default_window_backend
from termin.visualization.world import VisualizationWorld

from editor_window import EditorWindow




from termin.mesh.mesh import CubeMesh, CylinderMesh, Mesh3
from termin.visualization.entity import Entity
from termin.visualization.components import MeshRenderer
from termin.visualization.world import VisualizationWorld
from termin.visualization.mesh import MeshDrawable
from termin.visualization.material import Material
from termin.visualization.scene import Scene
import numpy as np
from termin.geombase.pose3 import Pose3
from termin.visualization.skybox import SkyBoxEntity
from termin.visualization.camera import PerspectiveCameraComponent, OrbitCameraController

def build_scene(world):

    cube_mesh = CubeMesh()
    cyl_mesh = CylinderMesh(radius=0.5, height=2.0)
    drawable = MeshDrawable(cube_mesh)
    drawable_cyl = MeshDrawable(cyl_mesh)
    red_material = Material(color=np.array([0.8, 0.3, 0.3, 1.0], dtype=np.float32))
    blue_material = Material(color=np.array([0.3, 0.3, 0.8, 1.0], dtype=np.float32))
    green_material = Material(color=np.array([0.3, 0.8, 0.3, 1.0], dtype=np.float32))
   
    scene = Scene()


    entity_cyl = Entity(pose=Pose3.identity(), name="cylinder")
    entity_cyl.add_component(MeshRenderer(drawable_cyl, green_material))
    entity_cyl.transform.relocate(Pose3(lin=np.array([-2.0, 0.0, 0.0]), ang=np.array([0.0, 0.0, 0.0, 1.0])))
    scene.add(entity_cyl)

    entity = Entity(pose=Pose3.identity(), name="cube1")
    entity.add_component(MeshRenderer(drawable, red_material))
    scene.add(entity)

    entity2 = Entity(pose=Pose3.identity(), name="cube2")
    entity2.add_component(MeshRenderer(drawable, blue_material))
    entity2.transform.relocate(Pose3(lin=np.array([3.0, 0.0, 0.0]), ang=np.array([0.0, 0.0, 0.0, 1.0])))
    scene.add(entity2)


    skybox = SkyBoxEntity()
    scene.add(skybox)

    world.add_scene(scene)

    return scene


def apply_dark_palette(app: QApplication):
    app.setStyle("Fusion")  # более аккуратный стиль, чем дефолтный

    palette = QPalette()

    # Базовые цвета
    bg      = QColor(30, 30, 30)
    window  = QColor(37, 37, 38)
    base    = QColor(45, 45, 48)
    text    = QColor(220, 220, 220)
    disabled_text = QColor(128, 128, 128)
    highlight = QColor(0, 120, 215)

    palette.setColor(QPalette.Window, window)
    palette.setColor(QPalette.WindowText, text)
    palette.setColor(QPalette.Base, base)
    palette.setColor(QPalette.AlternateBase, bg)
    palette.setColor(QPalette.ToolTipBase, base)
    palette.setColor(QPalette.ToolTipText, text)
    palette.setColor(QPalette.Text, text)
    palette.setColor(QPalette.Button, window)
    palette.setColor(QPalette.ButtonText, text)
    palette.setColor(QPalette.BrightText, QColor(255, 0, 0))

    palette.setColor(QPalette.Highlight, highlight)
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))

    # Отключённые элементы
    palette.setColor(QPalette.Disabled, QPalette.Text, disabled_text)
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, disabled_text)
    palette.setColor(QPalette.Disabled, QPalette.WindowText, disabled_text)

    app.setPalette(palette)


def run_editor():
    set_default_graphics_backend(OpenGLGraphicsBackend())
    set_default_window_backend(QtWindowBackend())

    world = VisualizationWorld()
    scene = build_scene(world)

    app = QApplication(sys.argv)
    apply_dark_palette(app)
    win = EditorWindow(world, scene)
    win.show()
    app.exec_()


if __name__ == "__main__":
    run_editor()
