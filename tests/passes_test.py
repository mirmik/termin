import unittest

from termin.visualization.platform.backends.glfw import GLFWWindowBackend
from termin.visualization.render.opengl.backends import OpenGLGraphicsBackend
from termin.visualization.platform.window import Window
from termin.visualization.core.scene import Scene
from termin.visualization.core.camera import PerspectiveCameraComponent
from termin.visualization.core.viewport import Viewport
from termin.visualization.render.framegraph import RenderPipeline
from termin.visualization.render.framegraph.passes.color import ColorPass
from termin.visualization.render.framegraph.passes.present import PresentToScreenPass
from termin.visualization.core.entity import Entity
from termin.mesh.mesh import Mesh, CubeMesh
from termin.visualization.render.components.mesh_renderer import MeshRenderer
from termin.visualization.render.materials.simple import ColorMaterial
from termin.geombase.pose3 import Pose3
from termin.visualization.render.pipeline_runner import PipelineRunner
import numpy

class TestPasses(unittest.TestCase):

    def test_color_pipeline_opengl_smoke(self):
        graphics = OpenGLGraphicsBackend()
        # window_backend = GLFWWindowBackend()
        # window = Window(
        #     width=320,
        #     height=240,
        #     title="test",
        #     graphics=graphics,
        #     window_backend=window_backend,
        # )

        scene = Scene()
        # Сцена должна хоть что-то рисовать,
        # можно заиспользовать готовый меш / сущность из примеров
        camera_entity = Entity()
        scene.add(camera_entity)
        camera = camera_entity.add_component(PerspectiveCameraComponent())

        camera_entity.transform.relocate(Pose3.looking_at(
            eye=numpy.array([3.0, 3.0, 3.0]),
            target=numpy.array([0.0, 0.0, 0.0]),
            up=numpy.array([0.0, 0.0, 1.0]),
        ))

        cube = Entity()
        scene.add(cube)
        material = ColorMaterial(color=(1.0, 0.0, 0.0, 1.0))
        cube.add_component(MeshRenderer(CubeMesh(), material=material))

        #viewport = window.add_viewport(scene, camera)

        color_pass = ColorPass(
            input_res="empty",
            output_res="color",
            pass_name="Color",
        )
        # present_pass = PresentToScreenPass(
        #     input_res="color",
        #     output_res="DISPLAY",
        #     pass_name="Present",
        # )

        pipeline = RenderPipeline(
            passes=[color_pass],
            clear_specs=[],
        )

        viewport.set_render_pipeline(pipeline)

        #while not window.should_close:
        #    window._render_core(from_backend=False)

        pipeline_runner = PipelineRunner(graphics)
        pipeline_runner.run_pipeline_once(pipeline, viewport, 320, 240)