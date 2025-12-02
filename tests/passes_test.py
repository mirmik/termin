import unittest

from termin.visualization.render.opengl.backends import OpenGLGraphicsBackend
from termin.visualization.core.scene import Scene
from termin.visualization.core.camera import PerspectiveCameraComponent
from termin.visualization.render.framegraph import RenderPipeline, ClearSpec
from termin.visualization.render.framegraph.passes.color import ColorPass
from termin.visualization.render.framegraph.passes.present import PresentToScreenPass
from termin.visualization.core.entity import Entity
from termin.mesh.mesh import CubeMesh
from termin.visualization.render.components.mesh_renderer import MeshRenderer
from termin.visualization.render.materials.simple import ColorMaterial
from termin.geombase.pose3 import Pose3
from termin.visualization.render import (
    RenderEngine,
    HeadlessContext,
    OffscreenRenderSurface,
    RenderView,
    ViewportRenderState,
)
import numpy


class TestPasses(unittest.TestCase):

    def test_color_pipeline_opengl_smoke(self):
        """
        Smoke-тест offscreen рендеринга с ColorPass.
        
        Проверяет, что:
        1. HeadlessContext создаёт OpenGL контекст
        2. RenderEngine выполняет pipeline
        3. Результат можно прочитать из offscreen surface
        4. Красный куб виден в центре, фон серый
        
        Pipeline:
            empty --[ColorPass]--> color --[PresentToScreenPass]--> DISPLAY
        """
        # Создаём headless OpenGL контекст
        context = HeadlessContext()
        
        try:
            graphics = OpenGLGraphicsBackend()
            graphics.ensure_ready()

            # Создаём сцену с кубом
            scene = Scene()
            
            # Камера
            camera_entity = Entity(name="camera")
            scene.add(camera_entity)
            camera = camera_entity.add_component(PerspectiveCameraComponent())
            camera_entity.transform.relocate(Pose3.looking_at(
                eye=numpy.array([3.0, 3.0, 3.0]),
                target=numpy.array([0.0, 0.0, 0.0]),
                up=numpy.array([0.0, 0.0, 1.0]),
            ))

            # Красный куб
            cube = Entity(name="cube")
            scene.add(cube)
            material = ColorMaterial(color=(1.0, 0.0, 0.0, 1.0))
            cube.add_component(MeshRenderer(CubeMesh(), material=material))

            # Подготавливаем сцену (загрузка мешей/текстур)
            scene.ensure_ready(graphics)

            # Создаём pipeline: ColorPass -> PresentToScreenPass
            color_pass = ColorPass(
                input_res="empty",
                output_res="color",
                pass_name="Color",
            )
            present_pass = PresentToScreenPass(
                input_res="color",
                output_res="DISPLAY",
                pass_name="Present",
            )

            pipeline = RenderPipeline(
                passes=[color_pass, present_pass],
                clear_specs=[
                    ClearSpec(resource="empty", color=(0.2, 0.2, 0.2, 1.0), depth=1.0),
                ],
            )

            # Создаём RenderView и ViewportRenderState
            view = RenderView(
                scene=scene,
                camera=camera,
                rect=(0.0, 0.0, 1.0, 1.0),
            )
            state = ViewportRenderState(pipeline=pipeline)

            # Создаём offscreen surface
            offscreen = OffscreenRenderSurface(graphics, width=320, height=240)

            # Создаём движок и рендерим
            engine = RenderEngine(graphics)
            engine.render_single_view(
                surface=offscreen,
                view=view,
                state=state,
                present=False,  # offscreen не нужен present
            )

            # Читаем результат
            pixels = offscreen.read_pixels()

            # Проверяем базовые свойства результата
            self.assertEqual(pixels.shape, (240, 320, 4))
            self.assertEqual(pixels.dtype, numpy.uint8)

            # Проверяем, что куб виден в центре (красный)
            center_y, center_x = 120, 160
            center_pixel = pixels[center_y, center_x]
            self.assertGreater(center_pixel[0], 100, "Red component should be significant at center (cube)")
            self.assertLess(center_pixel[1], 50, "Green component should be low at center")
            self.assertLess(center_pixel[2], 50, "Blue component should be low at center")

            # Проверяем, что фон серый (угол изображения)
            corner_pixel = pixels[0, 0]
            # Фон (0.2, 0.2, 0.2) -> примерно (51, 51, 51), но с гамма-коррекцией может отличаться
            self.assertGreater(corner_pixel[0], 5, "Corner should not be black")
            self.assertLess(corner_pixel[0], 100, "Corner should not be bright red")

            # Очистка
            offscreen.delete()
            state.clear_fbos()
            
        finally:
            context.destroy()


if __name__ == "__main__":
    unittest.main()
