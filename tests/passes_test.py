import tempfile
import unittest
from pathlib import Path

from termin.visualization.platform.backends.opengl import OpenGLGraphicsBackend
from termin.visualization.core.scene import Scene
from termin.visualization.core.camera import PerspectiveCameraComponent
from termin.visualization.render.framegraph import RenderPipeline, ResourceSpec
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

    def _create_headless_or_skip(self, width: int = 1, height: int = 1) -> HeadlessContext:
        """
        Создаёт HeadlessContext или пропускает тест, если GLFW недоступен
        (например, нет X11/Wayland дисплея в окружении CI).
        """
        try:
            return HeadlessContext(width, height)
        except RuntimeError as exc:
            if "GLFW" in str(exc):
                self.skipTest(f"GLFW unavailable for headless rendering: {exc}")
            raise

    def test_color_pipeline_opengl(self):
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
        context = self._create_headless_or_skip()
        
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
                shadow_res=None,  # Без shadow mapping в тесте
                pass_name="Color",
            )
            present_pass = PresentToScreenPass(
                input_res="color",
                output_res="DISPLAY",
                pass_name="Present",
            )

            pipeline = RenderPipeline(
                passes=[color_pass, present_pass],
                pipeline_specs=[
                    ResourceSpec(
                        resource="empty",
                        clear_color=(0.2, 0.2, 0.2, 1.0),
                        clear_depth=1.0,
                    ),
                    # "color" теперь алиас "empty" (inplace), отдельный спек не нужен
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


    def test_depth_pass_opengl(self):
        """
        Smoke-тест DepthPass.
        
        Проверяет, что:
        1. DepthPass рендерит глубину куба
        2. Глубина в центре кадра меньше 1.0 (есть объект)
        
        Pipeline:
            empty_depth --[DepthPass]--> depth
        """
        width, height = 128, 128

        # Headless OpenGL-контекст
        context = self._create_headless_or_skip(width, height)

        try:
            graphics = OpenGLGraphicsBackend()
            graphics.ensure_ready()

            # Поверхность для offscreen-рендера
            surface = OffscreenRenderSurface(graphics, width, height)
            framebuffer = surface.get_framebuffer()

            # --- Сцена: один куб перед камерой ---

            scene = Scene()

            # Куб в центре мира
            cube_entity = Entity(name="cube")
            cube_mesh = CubeMesh()
            # Используем новый API: MeshRenderer принимает mesh напрямую
            material = ColorMaterial(color=(1.0, 0.0, 0.0, 1.0))
            cube_renderer = MeshRenderer(cube_mesh, material=material)
            cube_entity.add_component(cube_renderer)
            scene.add(cube_entity)

            # Камера на (0, 0, 3), смотрит в центр
            camera_entity = Entity(name="camera")
            scene.add(camera_entity)
            camera = camera_entity.add_component(PerspectiveCameraComponent(
                fov_y_degrees=60.0,
                aspect=width / float(height),
                near=0.1,
                far=10.0,
            ))
            camera_entity.transform.relocate(Pose3.translation(0.0, 0.0, 3.0))

            # Подготовка сцены
            scene.ensure_ready(graphics)

            # --- DepthPass ---
            from termin.visualization.render.framegraph.passes.depth import DepthPass

            depth_pass = DepthPass(input_res="empty_depth", output_res="depth")

            reads_fbos = {"empty_depth": framebuffer}
            writes_fbos = {"depth": framebuffer}

            rect = (0, 0, width, height)

            depth_pass.execute(
                graphics=graphics,
                reads_fbos=reads_fbos,
                writes_fbos=writes_fbos,
                rect=rect,
                scene=scene,
                camera=camera,
                context_key=surface.context_key(),
                lights=None,
                canvas=None,
            )

            # --- Проверяем результат ---

            x = width // 2
            y = height // 2
            r, g, b, a = graphics.read_pixel(framebuffer, x, y)

            # sanity-check по диапазону
            for channel in (r, g, b, a):
                self.assertGreaterEqual(channel, 0.0)
                self.assertLessEqual(channel, 1.0)

            # Объект должен дать заметно более тёмное значение чем фон (1.0)
            self.assertTrue(
                r < 0.99 or g < 0.99 or b < 0.99,
                f"Expected depth < 1.0 at center, got ({r}, {g}, {b})"
            )

            # Очистка
            surface.delete()

        finally:
            context.destroy()

    def test_multiphase_material_colorpass(self):
        """
        Тест многофазного материала с ColorPass.

        Проверяет, что:
        1. Материал с двумя фазами (opaque=красный, transparent=синий) корректно парсится
        2. ColorPass(phase_mark="opaque") рендерит красный куб
        3. ColorPass(phase_mark="transparent") рендерит синий куб

        Pipeline:
            empty --[ColorPass(phase_mark)]--> color --[PresentToScreenPass]--> DISPLAY
        """
        from termin.visualization.render.shader_parser import parse_shader_text, ShaderMultyPhaseProgramm
        from termin.visualization.core.material import Material

        # Сбрасываем кэш шейдеров (они могут быть невалидны после предыдущих тестов)
        PresentToScreenPass._shader = None

        # Создаём headless OpenGL контекст
        context = self._create_headless_or_skip()

        try:
            graphics = OpenGLGraphicsBackend()
            graphics.ensure_ready()

            # Шейдер с двумя фазами: opaque (красный) и transparent (синий)
            shader_text = """
@program TwoPhaseTest

@phase opaque
@priority 0
@glDepthTest true
@glDepthMask true
@property Color u_color = Color(1.0, 0.0, 0.0, 1.0)

@stage vertex
#version 330 core
layout(location = 0) in vec3 a_position;
uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;
void main() {
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
@endstage

@stage fragment
#version 330 core
uniform vec4 u_color;
out vec4 FragColor;
void main() {
    FragColor = u_color;
}
@endstage
@endphase

@phase transparent
@priority 100
@glDepthTest true
@glDepthMask false
@glBlend true
@property Color u_color = Color(0.0, 0.0, 1.0, 1.0)

@stage vertex
#version 330 core
layout(location = 0) in vec3 a_position;
uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;
void main() {
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
@endstage

@stage fragment
#version 330 core
uniform vec4 u_color;
out vec4 FragColor;
void main() {
    FragColor = u_color;
}
@endstage
@endphase
"""
            # Парсим шейдер и создаём материал
            tree = parse_shader_text(shader_text)
            program = ShaderMultyPhaseProgramm.from_tree(tree)
            material = Material.from_parsed(program)

            # Проверяем, что материал имеет две фазы
            self.assertEqual(len(material.phases), 2)
            self.assertEqual(material.phases[0].phase_mark, "opaque")
            self.assertEqual(material.phases[1].phase_mark, "transparent")

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

            # Куб с многофазным материалом
            cube = Entity(name="cube")
            scene.add(cube)
            cube.add_component(MeshRenderer(CubeMesh(), material=material))

            # Подготавливаем сцену
            scene.ensure_ready(graphics)

            # --- Тест 1: ColorPass с phase_mark="opaque" должен дать красный куб ---

            color_pass_opaque = ColorPass(
                input_res="empty",
                output_res="color",
                shadow_res=None,
                pass_name="ColorOpaque",
                phase_mark="opaque",
            )
            present_pass = PresentToScreenPass(
                input_res="color",
                output_res="DISPLAY",
                pass_name="Present",
            )

            pipeline_opaque = RenderPipeline(
                passes=[color_pass_opaque, present_pass],
                pipeline_specs=[
                    ResourceSpec(
                        resource="empty",
                        clear_color=(0.0, 0.0, 0.0, 1.0),  # Чёрный фон
                        clear_depth=1.0,
                    ),
                ],
            )

            view = RenderView(scene=scene, camera=camera, rect=(0.0, 0.0, 1.0, 1.0))
            state_opaque = ViewportRenderState(pipeline=pipeline_opaque)

            offscreen = OffscreenRenderSurface(graphics, width=128, height=128)
            engine = RenderEngine(graphics)

            engine.render_single_view(
                surface=offscreen,
                view=view,
                state=state_opaque,
                present=False,
            )

            pixels_opaque = offscreen.read_pixels()

            # Проверяем центральный пиксель — должен быть красным
            center_y, center_x = 64, 64
            center_pixel = pixels_opaque[center_y, center_x]
            self.assertGreater(center_pixel[0], 200, f"Opaque phase: Red should be high, got {center_pixel}")
            self.assertLess(center_pixel[1], 50, f"Opaque phase: Green should be low, got {center_pixel}")
            self.assertLess(center_pixel[2], 50, f"Opaque phase: Blue should be low, got {center_pixel}")

            # --- Тест 2: ColorPass с phase_mark="transparent" должен дать синий куб ---

            color_pass_transparent = ColorPass(
                input_res="empty",
                output_res="color",
                shadow_res=None,
                pass_name="ColorTransparent",
                phase_mark="transparent",
            )

            pipeline_transparent = RenderPipeline(
                passes=[color_pass_transparent, present_pass],
                pipeline_specs=[
                    ResourceSpec(
                        resource="empty",
                        clear_color=(0.0, 0.0, 0.0, 1.0),  # Чёрный фон
                        clear_depth=1.0,
                    ),
                ],
            )

            state_transparent = ViewportRenderState(pipeline=pipeline_transparent)

            engine.render_single_view(
                surface=offscreen,
                view=view,
                state=state_transparent,
                present=False,
            )

            pixels_transparent = offscreen.read_pixels()

            # Проверяем центральный пиксель — должен быть синим
            center_pixel = pixels_transparent[center_y, center_x]
            self.assertLess(center_pixel[0], 50, f"Transparent phase: Red should be low, got {center_pixel}")
            self.assertLess(center_pixel[1], 50, f"Transparent phase: Green should be low, got {center_pixel}")
            self.assertGreater(center_pixel[2], 200, f"Transparent phase: Blue should be high, got {center_pixel}")

            # Очистка
            offscreen.delete()
            state_opaque.clear_fbos()
            state_transparent.clear_fbos()

        finally:
            context.destroy()

    def test_material_from_shader_file(self):
        """
        Тест загрузки материала из файла шейдера.

        Проверяет полный пайплайн:
        1. Создаём .shader файл во временной директории
        2. Читаем и парсим файл
        3. Создаём Material из parsed данных
        4. Рендерим куб с этим материалом
        5. Проверяем, что цвет соответствует заданному в файле (зелёный)
        """
        from termin.visualization.render.shader_parser import parse_shader_text, ShaderMultyPhaseProgramm
        from termin.visualization.core.material import Material

        # Сбрасываем кэш шейдеров (они могут быть невалидны после предыдущих тестов)
        PresentToScreenPass._shader = None

        # Создаём headless OpenGL контекст
        context = self._create_headless_or_skip()

        try:
            graphics = OpenGLGraphicsBackend()
            graphics.ensure_ready()

            # Содержимое шейдер-файла — зелёный материал
            shader_content = """\
@program GreenMaterial

@phase opaque
@priority 0
@glDepthTest true
@glDepthMask true
@property Color u_color = Color(0.0, 1.0, 0.0, 1.0)

@stage vertex
#version 330 core
layout(location = 0) in vec3 a_position;
uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;
void main() {
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
@endstage

@stage fragment
#version 330 core
uniform vec4 u_color;
out vec4 FragColor;
void main() {
    FragColor = u_color;
}
@endstage
@endphase
"""

            # Создаём временный файл
            with tempfile.TemporaryDirectory() as tmpdir:
                shader_path = Path(tmpdir) / "green_material.shader"
                shader_path.write_text(shader_content, encoding="utf-8")

                # Загружаем и парсим из файла
                loaded_text = shader_path.read_text(encoding="utf-8")
                tree = parse_shader_text(loaded_text)
                program = ShaderMultyPhaseProgramm.from_tree(tree)

                # Проверяем, что парсинг прошёл успешно
                self.assertEqual(program.program, "GreenMaterial")
                self.assertEqual(len(program.phases), 1)
                self.assertEqual(program.phases[0].phase_mark, "opaque")

                # Создаём материал
                material = Material.from_parsed(program)

                # Проверяем uniforms
                phase = material.phases[0]
                self.assertIn("u_color", phase.uniforms)

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

                # Куб с загруженным материалом
                cube = Entity(name="cube")
                scene.add(cube)
                cube.add_component(MeshRenderer(CubeMesh(), material=material))

                # Подготавливаем сцену
                scene.ensure_ready(graphics)

                # Pipeline с phase_mark="opaque"
                color_pass = ColorPass(
                    input_res="empty",
                    output_res="color",
                    shadow_res=None,
                    pass_name="Color",
                    phase_mark="opaque",
                )
                present_pass = PresentToScreenPass(
                    input_res="color",
                    output_res="DISPLAY",
                    pass_name="Present",
                )

                pipeline = RenderPipeline(
                    passes=[color_pass, present_pass],
                    pipeline_specs=[
                        ResourceSpec(
                            resource="empty",
                            clear_color=(0.0, 0.0, 0.0, 1.0),
                            clear_depth=1.0,
                        ),
                    ],
                )

                view = RenderView(scene=scene, camera=camera, rect=(0.0, 0.0, 1.0, 1.0))
                state = ViewportRenderState(pipeline=pipeline)

                offscreen = OffscreenRenderSurface(graphics, width=128, height=128)
                engine = RenderEngine(graphics)

                engine.render_single_view(
                    surface=offscreen,
                    view=view,
                    state=state,
                    present=False,
                )

                pixels = offscreen.read_pixels()

                # Проверяем центральный пиксель — должен быть зелёным
                center_y, center_x = 64, 64
                center_pixel = pixels[center_y, center_x]
                self.assertLess(center_pixel[0], 50, f"Red should be low, got {center_pixel}")
                self.assertGreater(center_pixel[1], 200, f"Green should be high, got {center_pixel}")
                self.assertLess(center_pixel[2], 50, f"Blue should be low, got {center_pixel}")

                # Очистка
                offscreen.delete()
                state.clear_fbos()

        finally:
            context.destroy()


if __name__ == "__main__":
    unittest.main()
