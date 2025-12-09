import sys

import numpy as np
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtWidgets import QApplication
from PyQt6 import QtCore

from termin.editor.editor_window import EditorWindow
from termin.geombase.pose3 import Pose3
from termin.mesh.mesh import CubeMesh, CylinderMesh, Mesh3
from termin.visualization.core.camera import PerspectiveCameraComponent, OrbitCameraController
from termin.visualization.core.entity import Entity
from termin.visualization.core.material import Material
from termin.visualization.core.mesh import MeshDrawable
from termin.visualization.core.scene import Scene
from termin.visualization.core.world import VisualizationWorld
from termin.visualization.platform.backends import (
    OpenGLGraphicsBackend,
    QtWindowBackend,
    set_default_graphics_backend,
    set_default_window_backend,
)
from termin.visualization.render.components import MeshRenderer
from termin.visualization.render.components.light_component import LightComponent
from termin.visualization.core.lighting.light import LightType, LightShadowParams


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

    panel = Entity(pose=Pose3.identity(), name="cube2")
    panel.add_component(MeshRenderer(drawable, blue_material))
    panel.transform.relocate(Pose3(lin=np.array([0.0, 0.0, -3.0]), ang=np.array([0.0, 0.0, 0.0, 1.0])))
    panel.scale = np.array([10.0, 10.0, 0.1])
    scene.add(panel)


    # Направленный источник света для теней (направление совпадает с ShadowPass)
    light_entity = Entity(pose=Pose3.identity(), name="directional_light")
    light_component = LightComponent(
        light_type=LightType.DIRECTIONAL,
        color=(1.0, 1.0, 1.0),
        intensity=1.0,
        shadows=LightShadowParams(enabled=True, map_resolution=2048),
    )
    light_entity.add_component(light_component)
    # Направление света: [0.5, -1.0, 0.5] (совпадает с ShadowPass)
    # Для directional light направление берётся из трансформа сущности
    scene.add(light_entity)

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

    palette.setColor(QPalette.ColorRole.Window, window)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, base)
    palette.setColor(QPalette.ColorRole.AlternateBase, bg)
    palette.setColor(QPalette.ColorRole.ToolTipBase, base)
    palette.setColor(QPalette.ColorRole.ToolTipText, text)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.Button, window)
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))

    palette.setColor(QPalette.ColorRole.Highlight, highlight)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))

    # Отключённые элементы
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_text)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_text)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled_text)

    app.setPalette(palette)


def run_editor():
    QApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    app = QApplication(sys.argv)
    
    set_default_graphics_backend(OpenGLGraphicsBackend())
    set_default_window_backend(QtWindowBackend())

    world = VisualizationWorld()
    scene = build_scene(world)

    apply_dark_palette(app)
    win = EditorWindow(world, scene)
    win.show()
    app.exec()


if __name__ == "__main__":
    run_editor()
