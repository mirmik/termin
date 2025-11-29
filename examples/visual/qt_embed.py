"""Embed termin visualization view inside a PyQt5 application."""

from __future__ import annotations

import numpy as np
from PyQt5 import QtWidgets

from termin.geombase.pose3 import Pose3
from termin.mesh.mesh import UVSphereMesh
from termin.visualization import (
    Entity,
    MeshDrawable,
    Scene,
    Material,
    VisualizationWorld,
    PerspectiveCameraComponent,
    OrbitCameraController,
)
from termin.visualization.render.components import MeshRenderer
from termin.visualization.render.shader import ShaderProgram
from termin.visualization.render.skybox import SkyBoxEntity
from termin.visualization.platform.backends.qt import QtWindowBackend


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


def build_scene(world: VisualizationWorld) -> tuple[Scene, PerspectiveCameraComponent]:
    """Создаём простую сцену с шаром и skybox."""
    shader = ShaderProgram(VERT, FRAG)
    material = Material(
        shader=shader,
        color=np.array([0.3, 0.7, 0.9, 1.0], dtype=np.float32),
    )
    mesh = MeshDrawable(UVSphereMesh(radius=1.0, n_meridians=32, n_parallels=16))

    sphere = Entity(pose=Pose3.identity(), name="sphere")
    sphere.add_component(MeshRenderer(mesh, material))

    scene = Scene()
    scene.add(sphere)
    scene.add(SkyBoxEntity())
    world.add_scene(scene)

    cam_entity = Entity(name="camera")
    camera = PerspectiveCameraComponent()
    cam_entity.add_component(camera)
    cam_entity.add_component(OrbitCameraController(radius=4.0))
    scene.add(cam_entity)

    return scene, camera


def main():
    # 1) Создаём Qt backend — внутри поднимется QApplication,
    #    поэтому до этого нельзя создавать QtWidgets.QWidget().
    qt_backend = QtWindowBackend()

    # 2) Создаём мир визуализации с Qt окном.
    world = VisualizationWorld(window_backend=qt_backend)
    scene, camera = build_scene(world)

    # 3) Дальше обычный Qt-интерфейс.
    main_window = QtWidgets.QMainWindow()
    central = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(central)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)

    # 4) Создаём окно визуализации как "дочернее" к central.
    #    QtWindowBackend внутри:
    #      - создаст QOpenGLWindow,
    #      - обернёт его в QWidget.createWindowContainer(parent),
    #      - вернёт handle, у которого .widget — это либо контейнер, либо само окно.
    vis_window = world.create_window(
        width=800,
        height=600,
        title="termin Qt embed",
        parent=central,  # ключевой момент — передаём parent
    )


    vis_window.add_viewport(scene, camera)

    # handle.widget должен вернуть Qt-вский виджет (container), который можно добавить в layout
    layout.addWidget(vis_window.handle.widget)

    quit_btn = QtWidgets.QPushButton("Закрыть")

    def close_all():
        vis_window.close()
        main_window.close()

    quit_btn.clicked.connect(close_all)
    layout.addWidget(quit_btn)

    main_window.setCentralWidget(central)
    main_window.resize(900, 700)
    main_window.setWindowTitle("Qt + termin visualization")
    main_window.show()

    # 5) Главный цикл: внутри будет
    #    - world.run() → while windows:
    #        - window.render()
    #        - window_backend.poll_events()
    #
    #    В Qt backend poll_events() делает app.processEvents(),
    #    так что отдельного app.exec_() вызывать не надо.
    world.run()


if __name__ == "__main__":
    main()
