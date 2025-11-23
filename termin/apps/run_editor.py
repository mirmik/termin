import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPalette, QColor

from termin.visualization.backends import QtWindowBackend, OpenGLGraphicsBackend, set_default_graphics_backend, set_default_window_backend
from termin.visualization.world import VisualizationWorld

from editor_window import EditorWindow




from termin.mesh.mesh import CubeMesh
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
    drawable = MeshDrawable(cube_mesh)
    material = Material(color=np.array([0.8, 0.3, 0.3, 1.0], dtype=np.float32))
    entity = Entity(pose=Pose3.identity(), name="cube")
    entity.add_component(MeshRenderer(drawable, material))
    scene = Scene()
    scene.add(entity)

    skybox = SkyBoxEntity()
    scene.add(skybox)
    world.add_scene(scene)

    camera_entity = Entity(name="camera")
    camera = PerspectiveCameraComponent()
    camera_entity.add_component(camera)
    camera_entity.add_component(OrbitCameraController())
    scene.add(camera_entity)

    return scene, camera


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
    scene, cam = build_scene(world)

    app = QApplication(sys.argv)
    apply_dark_palette(app)
    win = EditorWindow(world, scene, cam)
    win.show()
    app.exec_()


if __name__ == "__main__":
    run_editor()
