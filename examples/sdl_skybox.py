#!/usr/bin/env python

"""SDL2 window with just a skybox — the minimal visual check for Stage 4.

Pipeline:
    SkyBoxPass      → writes 'color' (gradient sky)
    PresentToScreen → reads  'color'

The tgfx2-native SkyBoxPass (stage 4 of the migration) draws through
RenderContext2 end-to-end with a std140 UBO carrying view/projection +
skybox colors. Success == the window shows a blue-sky / warm-horizon
gradient that rotates with the orbit camera.
"""

from __future__ import annotations

from termin.entity import Entity, TcScene
from termin.entity._entity_native import OrbitCameraController, scene_render_state
from termin.render_components import PerspectiveCameraComponent
from termin.display.display import Display
from termin.display.sdl_backend import SDLWindowBackend
from termin.geombase import Pose3
from termin._native.render import (
    RenderEngine,
    PresentToScreenPass,
    SkyBoxPass,
)
from tgfx import OpenGLGraphicsBackend
from termin.render_framework import RenderPipeline


def make_skybox_pipeline():
    passes = [
        SkyBoxPass(input_res="empty", output_res="color", pass_name="Skybox"),
        PresentToScreenPass(input_res="color", pass_name="Present"),
    ]
    return RenderPipeline(name="sdl_skybox", _init_passes=passes)


def build_scene() -> tuple[TcScene, PerspectiveCameraComponent]:
    scene = TcScene.create(name="sdl_skybox")

    rs = scene_render_state(scene)
    rs.set_skybox_type(1)  # TC_SKYBOX_GRADIENT
    rs.set_skybox_top_color(0.2, 0.5, 0.9)      # deep sky blue
    rs.set_skybox_bottom_color(0.95, 0.6, 0.3)  # warm orange horizon

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
        width=800, height=600, title="termin skybox (tgfx2)",
    )
    display = Display(handle)
    viewport = display.create_viewport(scene=scene, camera=camera, name="main")

    from termin.render_framework import render_target_new
    rt = render_target_new("main")
    rt.scene = scene
    rt.camera = camera
    rt.pipeline = make_skybox_pipeline()
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
