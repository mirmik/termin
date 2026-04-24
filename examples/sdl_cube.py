#!/usr/bin/env python
"""SDL2 window with a rotating cube — native tgfx2 path.

Creates a raw SDL GL window and drives a ``RenderEngine`` directly
through ``render_view_to_fbo_id(fbo_id=0)`` — the default framebuffer.
No ``GraphicsBackend``, ``Display``, or ``Viewport`` involved.
"""

from __future__ import annotations

import ctypes
import numpy as np
import sdl2
from sdl2 import video

from termin.entity import Entity, TcScene
from termin.render_components import PerspectiveCameraComponent, MeshRenderer
from termin.geombase import Pose3
from tgfx import TcShader
from termin._native.render import RenderEngine, ColorPass, PresentToScreenPass, TcMaterial
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
    vec3 color = u_color.rgb * (0.25 + 0.75 * ndotl);
    FragColor = vec4(color, u_color.a);
}
"""


def _create_sdl_window(title, width, height):
    if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO) != 0:
        raise RuntimeError(f"SDL_Init failed: {sdl2.SDL_GetError()}")
    video.SDL_GL_SetAttribute(video.SDL_GL_CONTEXT_MAJOR_VERSION, 3)
    video.SDL_GL_SetAttribute(video.SDL_GL_CONTEXT_MINOR_VERSION, 3)
    video.SDL_GL_SetAttribute(video.SDL_GL_CONTEXT_PROFILE_MASK,
                              video.SDL_GL_CONTEXT_PROFILE_CORE)
    video.SDL_GL_SetAttribute(video.SDL_GL_DOUBLEBUFFER, 1)
    video.SDL_GL_SetAttribute(video.SDL_GL_DEPTH_SIZE, 24)
    flags = video.SDL_WINDOW_OPENGL | video.SDL_WINDOW_RESIZABLE | video.SDL_WINDOW_SHOWN
    window = video.SDL_CreateWindow(
        title.encode(),
        video.SDL_WINDOWPOS_CENTERED, video.SDL_WINDOWPOS_CENTERED,
        width, height, flags,
    )
    gl_ctx = video.SDL_GL_CreateContext(window)
    video.SDL_GL_MakeCurrent(window, gl_ctx)
    video.SDL_GL_SetSwapInterval(1)
    return window, gl_ctx


def make_preview_pipeline():
    passes = [
        ColorPass(
            input_res="empty", output_res="color",
            shadow_res="", pass_name="Color", phase_mark="opaque",
        ),
        PresentToScreenPass(input_res="color", pass_name="Present"),
    ]
    return RenderPipeline(name="sdl_cube", _init_passes=passes)


def build_scene():
    shader = TcShader.from_sources(VERT, FRAG, "", "SDLCubeShader")
    material = TcMaterial(
        name="SDLCubeMaterial",
        shader=shader,
        color=np.array([0.3, 0.6, 0.8, 1.0], dtype=np.float32),
    )

    mesh3 = CubeMesh()
    tc_mesh = TcMesh.from_mesh3(mesh3, "SDLCube")

    cube = Entity(pose=Pose3.identity(), name="cube")
    cube.add_component(MeshRenderer(tc_mesh, material))

    scene = TcScene.create(name="sdl_cube")
    scene.add(cube)

    cam_entity = Entity(
        pose=Pose3.looking_at([0, -4, 0], [0, 0, 0]),
        name="camera",
    )
    camera = PerspectiveCameraComponent()
    cam_entity.add_component(camera)
    scene.add(cam_entity)

    scene.update(0)
    return scene, camera


def main():
    window, gl_ctx = _create_sdl_window("termin SDL cube", 800, 600)

    scene, camera = build_scene()
    pipeline = make_preview_pipeline()
    engine = RenderEngine()

    event = sdl2.SDL_Event()
    running = True
    while running:
        while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
            if event.type == sdl2.SDL_QUIT:
                running = False
                break
            if event.type == sdl2.SDL_KEYDOWN and \
               event.key.keysym.scancode == sdl2.SDL_SCANCODE_ESCAPE:
                running = False
                break

        w = ctypes.c_int()
        h = ctypes.c_int()
        video.SDL_GL_GetDrawableSize(window, ctypes.byref(w), ctypes.byref(h))
        width, height = w.value, h.value
        if width <= 0 or height <= 0:
            continue

        camera.set_aspect(width / float(max(1, height)))

        engine.render_view_to_fbo_id(
            pipeline, 0, width, height,
            scene, camera, None,
            0xFFFFFFFFFFFFFFFF,
        )

        video.SDL_GL_SwapWindow(window)

    video.SDL_GL_DeleteContext(gl_ctx)
    video.SDL_DestroyWindow(window)
    sdl2.SDL_Quit()


if __name__ == "__main__":
    main()
