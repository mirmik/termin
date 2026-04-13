#!/usr/bin/env python

"""SDL2 window with a bright rotating cube and HDR bloom post-process.

Pipeline:
    ColorPass   → writes 'color' (HDR cube, deliberately bright)
    BloomPass   → reads 'color',  writes 'bloomed'
    PresentToScreen → reads 'bloomed'

Stage 5 of the tgfx2 migration — BloomPass now runs entirely through
RenderContext2 with four sub-passes (bright / downsample chain /
upsample chain / composite), an HDR mip pyramid of tgfx2 textures,
and std140 UBOs for every sub-shader's parameters.

Success == bright rim around the cube as the bloom glow, camera can
be orbited with the mouse.
"""

from __future__ import annotations

import numpy as np

from termin.entity import Entity, TcScene
from termin.entity._entity_native import OrbitCameraController
from termin.render_components import PerspectiveCameraComponent, MeshRenderer
from termin.display.display import Display
from termin.display.sdl_backend import SDLWindowBackend
from termin.geombase import Pose3
from tgfx import TcShader, OpenGLGraphicsBackend
from termin._native.render import (
    RenderEngine,
    ColorPass,
    PresentToScreenPass,
    BloomPass,
    TcMaterial,
)
from termin.render_framework import RenderPipeline
from tmesh import TcMesh, CubeMesh


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
    // Push cube HDR-bright so the bloom threshold has something to catch.
    vec3 color = u_color.rgb * (0.5 + 3.5 * ndotl);
    FragColor = vec4(color, u_color.a);
}
"""


def make_bloom_pipeline():
    passes = [
        ColorPass(
            input_res="empty", output_res="color",
            shadow_res="", pass_name="Color", phase_mark="opaque",
        ),
        BloomPass(
            input_res="color", output_res="bloomed",
            threshold=1.0, soft_threshold=0.5, intensity=1.2, mip_levels=5,
        ),
        PresentToScreenPass(input_res="bloomed", pass_name="Present"),
    ]
    return RenderPipeline(name="sdl_cube_bloom", _init_passes=passes)


def build_scene() -> tuple[TcScene, PerspectiveCameraComponent]:
    shader = TcShader.from_sources(VERT, FRAG, "", "SDLCubeBloomShader")
    material = TcMaterial(
        name="SDLCubeBloomMaterial",
        shader=shader,
        color=np.array([1.0, 0.5, 0.2, 1.0], dtype=np.float32),
    )

    mesh3 = CubeMesh()
    tc_mesh = TcMesh.from_mesh3(mesh3, "SDLCubeBloom")

    cube = Entity(pose=Pose3.identity(), name="cube")
    cube.add_component(MeshRenderer(tc_mesh, material))

    scene = TcScene.create(name="sdl_cube_bloom")
    scene.add(cube)

    cam_entity = Entity(
        pose=Pose3.looking_at([0, -4, 0], [0, 0, 0]),
        name="camera",
    )
    camera = PerspectiveCameraComponent()
    cam_entity.add_component(camera)
    cam_entity.add_component(OrbitCameraController(radius=4.0))
    scene.add(cam_entity)

    scene.update(0)
    return scene, camera


def main():
    graphics = OpenGLGraphicsBackend.get_instance()
    sdl_backend = SDLWindowBackend(graphics=graphics)

    scene, camera = build_scene()

    handle = sdl_backend.create_window(
        width=800, height=600, title="termin SDL cube — bloom (tgfx2)",
    )
    display = Display(handle)
    viewport = display.create_viewport(scene=scene, camera=camera, name="main")

    from termin.render_framework import render_target_new
    rt = render_target_new("main")
    rt.scene = scene
    rt.camera = camera
    rt.pipeline = make_bloom_pipeline()
    viewport.render_target = rt

    engine = RenderEngine(graphics)

    display.connect_input()

    pipeline = rt.pipeline

    while not handle.should_close():
        sdl_backend.poll_events()

        display.make_current()
        graphics.ensure_ready()

        width, height = display.get_size()
        if width <= 0 or height <= 0:
            continue

        surface = display.surface
        if surface is None:
            continue
        display_fbo = surface.get_framebuffer()

        camera.set_aspect(width / float(max(1, height)))

        if pipeline is None:
            continue

        engine.render_view_to_fbo(
            pipeline, display_fbo, width, height,
            scene, camera, viewport,
            viewport.layer_mask,
        )

        display.present()

    sdl_backend.terminate()


if __name__ == "__main__":
    main()
