"""Dynamic window creation/destruction test.

Main window with a button to spawn new 3D view windows.
Tests that render surfaces can be created and destroyed correctly.
"""

from __future__ import annotations

import sys
import numpy as np
from PyQt6 import QtWidgets, QtCore

from termin.visualization.core.scene import Scene
from termin.visualization.core.entity import Entity
from termin.visualization.core.camera import PerspectiveCameraComponent, OrbitCameraController
from termin.visualization.core.display import Display
from termin.visualization.core.material import Material
from termin.visualization.render.components import MeshRenderer
from termin.mesh.mesh import UVSphereMesh
from termin.mesh import TcMesh
from termin.geombase import Pose3
from tgfx import TcShader
from termin._native.render import RenderEngine
from termin.graphics import OpenGLGraphicsBackend
from termin.visualization.platform.backends.qt import QtWindowBackend, QtGLWindowHandle


VERT = """
#version 330 core
layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_normal;

void main() {
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
"""

FRAG = """
#version 330 core
in vec3 v_normal;
uniform vec4 u_color;

out vec4 FragColor;

void main() {
    vec3 n = normalize(v_normal);
    float ndotl = max(dot(n, vec3(0.2, 0.6, 0.5)), 0.0);
    vec3 color = u_color.rgb * (0.25 + 0.75 * ndotl);
    FragColor = vec4(color, u_color.a);
}
"""


def make_preview_pipeline():
    from termin.visualization.render.framegraph import (
        ColorPass, PresentToScreenPass, RenderPipeline,
    )
    from termin.visualization.render.framegraph.passes.skybox import SkyBoxPass

    passes = [
        SkyBoxPass(input_res="empty", output_res="skybox", pass_name="Skybox"),
        ColorPass(
            input_res="skybox", output_res="color",
            shadow_res=None, pass_name="Color", phase_mark="opaque",
        ),
        PresentToScreenPass(input_res="color", pass_name="Present"),
    ]
    return RenderPipeline(name="dynamic_windows", _init_passes=passes)


def build_scene() -> Scene:
    shader = TcShader.from_sources(VERT, FRAG, "", "DynWinShader")
    material = Material(
        name="DynWinMaterial",
        shader=shader,
        color=np.array([0.3, 0.7, 0.9, 1.0], dtype=np.float32),
    )

    mesh3 = UVSphereMesh(radius=1.0, n_meridians=32, n_parallels=16)
    tc_mesh = TcMesh.from_mesh3(mesh3, "DynWinSphere")

    sphere = Entity(pose=Pose3.identity(), name="sphere")
    sphere.add_component(MeshRenderer(tc_mesh, material))

    scene = Scene.create(name="dynamic_windows")
    scene.add(sphere)
    scene.update(0)
    return scene


class ViewRenderer:
    def __init__(self, handle, display, engine, graphics, viewport, scene, camera):
        self.handle = handle
        self.display = display
        self.engine = engine
        self.graphics = graphics
        self.viewport = viewport
        self.scene = scene
        self.camera = camera

    def render(self, from_backend=False):
        self.display.make_current()
        self.graphics.ensure_ready()

        width, height = self.display.get_size()
        if width <= 0 or height <= 0:
            return

        surface = self.display.surface
        if surface is None:
            return
        display_fbo = surface.get_framebuffer()

        self.camera.set_aspect(width / float(max(1, height)))

        pipeline = self.viewport.pipeline
        if pipeline is None:
            return

        self.engine.render_view_to_fbo(
            pipeline, display_fbo, width, height,
            self.scene, self.camera, self.viewport,
            self.viewport.effective_layer_mask,
        )
        self.display.present()


class ViewWindow(QtWidgets.QMainWindow):
    closed = QtCore.pyqtSignal(object)

    def __init__(self, qt_backend, engine, graphics, scene, window_id):
        super().__init__()
        self.setWindowTitle(f"View #{window_id}")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self.resize(600, 400)

        # Create GL widget with parent to avoid reparenting
        central = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        handle = qt_backend.create_window(
            width=600, height=400, title=f"View #{window_id}", parent=central,
        )
        layout.addWidget(handle.widget)
        self.setCentralWidget(central)

        # Camera for this window
        cam_entity = Entity(
            pose=Pose3.looking_at([0, -4, 0], [0, 0, 0]),
            name=f"camera_{window_id}",
        )
        camera = PerspectiveCameraComponent()
        cam_entity.add_component(camera)
        cam_entity.add_component(OrbitCameraController(radius=4.0))
        scene.add(cam_entity)
        scene.update(0)

        # Display + viewport + renderer
        display = Display(handle)
        viewport = display.create_viewport(scene=scene, camera=camera, name=f"view_{window_id}")
        viewport.pipeline = make_preview_pipeline()

        renderer = ViewRenderer(handle, display, engine, graphics, viewport, scene, camera)
        handle.set_user_pointer(renderer)

        self._handle = handle
        self._display = display
        self._renderer = renderer

    def closeEvent(self, event):
        self._handle.close()
        self.closed.emit(self)
        super().closeEvent(event)


def main():
    graphics = OpenGLGraphicsBackend.get_instance()
    qt_backend = QtWindowBackend(graphics=graphics)
    engine = RenderEngine(graphics)
    scene = build_scene()

    windows: list[ViewWindow] = []
    counter = [0]

    def spawn_window():
        counter[0] += 1
        win = ViewWindow(qt_backend, engine, graphics, scene, counter[0])
        win.closed.connect(lambda w: windows.remove(w))
        windows.append(win)
        win.show()

    # Main control window (no GL)
    main_window = QtWidgets.QWidget()
    main_window.setWindowTitle("Dynamic Windows Test")
    layout = QtWidgets.QVBoxLayout(main_window)

    label = QtWidgets.QLabel(
        "Click to spawn 3D view windows.\n"
        "Close them to test surface cleanup."
    )
    layout.addWidget(label)

    btn = QtWidgets.QPushButton("New Window")
    btn.clicked.connect(spawn_window)
    layout.addWidget(btn)

    quit_btn = QtWidgets.QPushButton("Quit")
    quit_btn.clicked.connect(qt_backend.app.quit)
    layout.addWidget(quit_btn)

    main_window.resize(300, 150)
    main_window.show()

    sys.exit(qt_backend.app.exec())


if __name__ == "__main__":
    main()
