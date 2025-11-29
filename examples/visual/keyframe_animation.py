"""Keyframed animation demo: translation + rotation + scale."""

from __future__ import annotations

import numpy as np

from termin.geombase.pose3 import Pose3
from termin.mesh.mesh import CubeMesh
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
from termin.visualization.animation import (
    AnimationChannel,
    AnimationClip,
    AnimationPlayer,
    AnimationKeyframe,
)


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
uniform vec3 u_light_dir;

out vec4 FragColor;

void main() {
    vec3 N = normalize(v_normal);
    float ndotl = max(dot(N, -normalize(u_light_dir)), 0.0);
    vec3 color = u_color.rgb * (0.2 + 0.8 * ndotl);
    FragColor = vec4(color, u_color.a);
}
"""


def build_scene(world: VisualizationWorld):
    mesh = MeshDrawable(CubeMesh(size=1.0))
    shader = ShaderProgram(VERT, FRAG)
    material = Material(
        shader=shader,
        color=np.array([0.4, 0.9, 0.4, 1.0], dtype=np.float32),
    )

    cube = Entity(pose=Pose3.identity(), name="animated_cube")
    cube.add_component(MeshRenderer(mesh, material))

    # ============
    # Keyframes
    # ============

    # движение по "квадрату"
    trs_keys = [
        AnimationKeyframe(0.0, translation=np.array([1.5, 0.0, 0.0])),
        AnimationKeyframe(1.0, translation=np.array([0.0, 1.5, 0.0])),
        AnimationKeyframe(2.0, translation=np.array([-1.5, 0.0, 0.0])),
        AnimationKeyframe(3.0, translation=np.array([0.0, -1.5, 0.0])),
        AnimationKeyframe(4.0, translation=np.array([1.5, 0.0, 0.0])),
    ]

    # полный оборот вокруг Y за 4 секунды
    rot_keys = [
        AnimationKeyframe(0.0, rotation=Pose3.rotateY(0.0).ang),
        AnimationKeyframe(1.0, rotation=Pose3.rotateY(np.pi/2).ang),
        AnimationKeyframe(2.0, rotation=Pose3.rotateY(np.pi).ang),
        AnimationKeyframe(3.0, rotation=Pose3.rotateY(1.5 * np.pi).ang),
        AnimationKeyframe(4.0, rotation=Pose3.rotateY(2.0 * np.pi).ang),
    ]

    # пульсация масштаба
    scale_keys = [
        AnimationKeyframe(0.0, scale=1.0),
        AnimationKeyframe(1.0, scale=1.5),
        AnimationKeyframe(2.0, scale=1.0),
        AnimationKeyframe(3.0, scale=0.7),
        AnimationKeyframe(4.0, scale=1.0),
    ]

    clip = AnimationClip(
        "move_rotate_scale",
        tps = 1.0,  # тики в секунду
        channels={
            "clip" :AnimationChannel(translation_keys=trs_keys, rotation_keys=rot_keys, scale_keys=scale_keys)
        },
        loop=True,
    )

    player = cube.add_component(AnimationPlayer())
    player.add_clip(clip)
    player.play("move_rotate_scale")

    scene = Scene()
    scene.add(cube)
    scene.add(SkyBoxEntity())
    world.add_scene(scene)

    cam_entity = Entity(name="camera")
    cam = PerspectiveCameraComponent()
    cam_entity.add_component(cam)
    cam_entity.add_component(OrbitCameraController(radius=6.0, elevation=30.0))
    scene.add(cam_entity)

    return scene, cam


def main():
    world = VisualizationWorld()
    scene, cam = build_scene(world)
    window = world.create_window(title="termin keyframed cube")
    window.add_viewport(scene, cam)
    world.run()


if __name__ == "__main__":
    main()
