"""Physics demo: drop cubes in the editor."""

import sys
import numpy as np
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtWidgets import QApplication
from PyQt5 import QtCore

from termin.geombase.pose3 import Pose3
from termin.mesh.mesh import CubeMesh
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

from termin.physics import RigidBodyComponent, PhysicsWorldComponent


def build_physics_scene(world):
    """Build a scene with physics objects."""
    scene = Scene()

    # Materials
    red_material = Material(color=np.array([0.8, 0.3, 0.3, 1.0], dtype=np.float32))
    blue_material = Material(color=np.array([0.3, 0.3, 0.8, 1.0], dtype=np.float32))
    green_material = Material(color=np.array([0.3, 0.8, 0.3, 1.0], dtype=np.float32))
    yellow_material = Material(color=np.array([0.8, 0.8, 0.3, 1.0], dtype=np.float32))
    gray_material = Material(color=np.array([0.5, 0.5, 0.5, 1.0], dtype=np.float32))

    # Meshes
    cube_mesh = CubeMesh()
    cube_drawable = MeshDrawable(cube_mesh)

    # Ground plane (visual only - physics uses world.ground_height)
    ground = Entity(pose=Pose3.identity(), name="ground")
    ground.add_component(MeshRenderer(cube_drawable, gray_material))
    ground.transform.relocate(Pose3.identity().with_translation(np.array([0, 0, -0.05])))
    ground.scale = np.array([10.0, 10.0, 0.1])
    scene.add(ground)

    # Falling cube 1
    cube1 = Entity(pose=Pose3.identity(), name="cube1")
    cube1.add_component(MeshRenderer(cube_drawable, red_material))
    cube1.transform.relocate(Pose3.identity().with_translation(np.array([0.0, 0.0, 3.0])))
    cube1.add_component(RigidBodyComponent(mass=1.0, is_static=False))
    scene.add(cube1)

    # Falling cube 2 (offset and tilted)
    import math
    angle = math.radians(30)
    quat = np.array([math.sin(angle/2), 0, 0, math.cos(angle/2)])
    cube2 = Entity(pose=Pose3.identity(), name="cube2")
    cube2.add_component(MeshRenderer(cube_drawable, blue_material))
    cube2.transform.relocate(Pose3(ang=quat, lin=np.array([2.0, 0.0, 4.0])))
    cube2.add_component(RigidBodyComponent(mass=1.0, is_static=False))
    scene.add(cube2)

    # Falling cube 3 (higher)
    cube3 = Entity(pose=Pose3.identity(), name="cube3")
    cube3.add_component(MeshRenderer(cube_drawable, green_material))
    cube3.transform.relocate(Pose3.identity().with_translation(np.array([-2.0, 0.0, 5.0])))
    cube3.add_component(RigidBodyComponent(mass=1.0, is_static=False))
    scene.add(cube3)

    # Falling cube 4 (will land on cube1)
    cube4 = Entity(pose=Pose3.identity(), name="cube4")
    cube4.add_component(MeshRenderer(cube_drawable, yellow_material))
    cube4.transform.relocate(Pose3.identity().with_translation(np.array([0.0, 0.0, 6.0])))
    cube4.add_component(RigidBodyComponent(mass=1.0, is_static=False))
    scene.add(cube4)

    # Physics world manager
    physics_entity = Entity(pose=Pose3.identity(), name="physics_world")
    physics_entity.add_component(PhysicsWorldComponent(
        gravity=np.array([0, 0, -9.81]),
        iterations=10,
        restitution=0.3,
        friction=0.5,
        ground_height=0.0,
        ground_enabled=True,
    ))
    scene.add(physics_entity)

    # Light
    light_entity = Entity(pose=Pose3.identity(), name="directional_light")
    light_component = LightComponent(
        light_type=LightType.DIRECTIONAL,
        color=(1.0, 1.0, 1.0),
        intensity=1.0,
        shadows=LightShadowParams(enabled=True, map_resolution=2048),
    )
    light_entity.add_component(light_component)
    scene.add(light_entity)

    world.add_scene(scene)
    return scene


def apply_dark_palette(app: QApplication):
    app.setStyle("Fusion")
    palette = QPalette()

    bg = QColor(30, 30, 30)
    window = QColor(37, 37, 38)
    base = QColor(45, 45, 48)
    text = QColor(220, 220, 220)
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
    palette.setColor(QPalette.Disabled, QPalette.Text, disabled_text)
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, disabled_text)
    palette.setColor(QPalette.Disabled, QPalette.WindowText, disabled_text)

    app.setPalette(palette)


def run_physics_demo():
    QApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts, True)
    app = QApplication(sys.argv)

    set_default_graphics_backend(OpenGLGraphicsBackend())
    set_default_window_backend(QtWindowBackend())

    world = VisualizationWorld()
    scene = build_physics_scene(world)

    apply_dark_palette(app)

    from termin.editor.editor_window import EditorWindow
    win = EditorWindow(world, scene)
    win.show()
    app.exec_()


if __name__ == "__main__":
    run_physics_demo()
