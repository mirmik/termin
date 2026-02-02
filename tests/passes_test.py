import tempfile
import unittest
from pathlib import Path

from termin.visualization.platform.backends import OpenGLGraphicsBackend
from termin.visualization.core.scene import Scene
from termin.visualization.core.camera import PerspectiveCameraComponent
from termin.visualization.render.framegraph import RenderPipeline, ResourceSpec
from termin.visualization.render.framegraph.passes.color import ColorPass
from termin.visualization.render.framegraph.passes.present import PresentToScreenPass
from termin.visualization.core.entity import Entity
from termin.mesh.mesh import CubeMesh
from termin.visualization.render.components.mesh_renderer import MeshRenderer
from termin.visualization.render.materials.simple import ColorMaterial
from termin.geombase import Pose3, Vec3
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
            graphics = OpenGLGraphicsBackend.get_instance()
            graphics.ensure_ready()

            # Создаём сцену с кубом
            scene = Scene()

            # Камера
            camera_entity = Entity(name="camera")
            camera_entity = scene.add(camera_entity)  # Capture migrated entity
            camera = camera_entity.add_component(PerspectiveCameraComponent())
            camera_entity.transform.relocate(Pose3.looking_at(
                eye=numpy.array([3.0, 3.0, 3.0]),
                target=numpy.array([0.0, 0.0, 0.0]),
                up=numpy.array([0.0, 0.0, 1.0]),
            ))

            # Красный куб
            cube = Entity(name="cube")
            cube = scene.add(cube)  # Capture migrated entity
            material = ColorMaterial(color=(1.0, 0.0, 0.0, 1.0))
            cube.add_component(MeshRenderer(CubeMesh(), material=material))

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
                _init_passes=[color_pass, present_pass],
                _init_specs=[
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
                pipeline=pipeline,
            )
            state = ViewportRenderState()

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
            graphics = OpenGLGraphicsBackend.get_instance()
            graphics.ensure_ready()

            # Поверхность для offscreen-рендера
            surface = OffscreenRenderSurface(graphics, width, height)
            framebuffer = surface.get_framebuffer()

            # --- Сцена: один куб перед камерой ---

            scene = Scene()

            # Куб в центре мира
            cube_entity = Entity(name="cube")
            cube_entity = scene.add(cube_entity)  # Capture migrated entity
            cube_mesh = CubeMesh()
            # Используем новый API: MeshRenderer принимает mesh напрямую
            material = ColorMaterial(color=(1.0, 0.0, 0.0, 1.0))
            cube_renderer = MeshRenderer(cube_mesh, material=material)
            cube_entity.add_component(cube_renderer)

            # Камера на (0, -3, 0), смотрит в центр (Y-forward convention)
            camera_entity = Entity(name="camera")
            camera_entity = scene.add(camera_entity)  # Capture migrated entity
            camera = camera_entity.add_component(PerspectiveCameraComponent(
                fov_y_degrees=60.0,
                aspect=width / float(height),
                near=0.1,
                far=10.0,
            ))
            # Use looking_at to properly orient camera towards the cube at origin
            camera_entity.transform.relocate(Pose3.looking_at(
                eye=Vec3(0.0, -3.0, 0.0),
                target=Vec3(0.0, 0.0, 0.0),
                up=Vec3(0.0, 0.0, 1.0)
            ))

            # --- DepthPass ---
            from termin.visualization.render.framegraph.passes.depth import DepthPass

            depth_pass = DepthPass(input_res="empty_depth", output_res="depth")

            reads_fbos = {"empty_depth": framebuffer}
            writes_fbos = {"depth": framebuffer}

            rect = (0, 0, width, height)

            from termin.visualization.render.framegraph.execute_context import ExecuteContext
            ctx = ExecuteContext(
                graphics=graphics,
                reads_fbos=reads_fbos,
                writes_fbos=writes_fbos,
                rect=rect,
                scene=scene,
                camera=camera,
                lights=None,
            )
            depth_pass.execute(ctx)

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
        from termin.visualization.render.texture import reset_dummy_shadow_texture

        # Сбрасываем кэш (они могут быть невалидны после предыдущих тестов)
        PresentToScreenPass._shader = None
        reset_dummy_shadow_texture()

        # Создаём headless OpenGL контекст
        context = self._create_headless_or_skip()

        try:
            graphics = OpenGLGraphicsBackend.get_instance()
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
            camera_entity = scene.add(camera_entity)  # Capture migrated entity
            camera = camera_entity.add_component(PerspectiveCameraComponent())
            camera_entity.transform.relocate(Pose3.looking_at(
                eye=numpy.array([3.0, 3.0, 3.0]),
                target=numpy.array([0.0, 0.0, 0.0]),
                up=numpy.array([0.0, 0.0, 1.0]),
            ))

            # Куб с многофазным материалом
            cube = Entity(name="cube")
            cube = scene.add(cube)  # Capture migrated entity
            cube.add_component(MeshRenderer(CubeMesh(), material=material))

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
                _init_passes=[color_pass_opaque, present_pass],
                _init_specs=[
                    ResourceSpec(
                        resource="empty",
                        clear_color=(0.0, 0.0, 0.0, 1.0),  # Чёрный фон
                        clear_depth=1.0,
                    ),
                ],
            )

            view = RenderView(scene=scene, camera=camera, rect=(0.0, 0.0, 1.0, 1.0), pipeline=pipeline_opaque)
            state_opaque = ViewportRenderState()

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
                _init_passes=[color_pass_transparent, present_pass],
                _init_specs=[
                    ResourceSpec(
                        resource="empty",
                        clear_color=(0.0, 0.0, 0.0, 1.0),  # Чёрный фон
                        clear_depth=1.0,
                    ),
                ],
            )

            state_transparent = ViewportRenderState()
            view_transparent = RenderView(scene=scene, camera=camera, rect=(0.0, 0.0, 1.0, 1.0), pipeline=pipeline_transparent)

            engine.render_single_view(
                surface=offscreen,
                view=view_transparent,
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
        from termin.visualization.render.texture import reset_dummy_shadow_texture

        # Сбрасываем кэш (они могут быть невалидны после предыдущих тестов)
        PresentToScreenPass._shader = None
        reset_dummy_shadow_texture()

        # Создаём headless OpenGL контекст
        context = self._create_headless_or_skip()

        try:
            graphics = OpenGLGraphicsBackend.get_instance()
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
                camera_entity = scene.add(camera_entity)  # Capture migrated entity
                camera = camera_entity.add_component(PerspectiveCameraComponent())
                camera_entity.transform.relocate(Pose3.looking_at(
                    eye=numpy.array([3.0, 3.0, 3.0]),
                    target=numpy.array([0.0, 0.0, 0.0]),
                    up=numpy.array([0.0, 0.0, 1.0]),
                ))

                # Куб с загруженным материалом
                cube = Entity(name="cube")
                cube = scene.add(cube)  # Capture migrated entity
                cube.add_component(MeshRenderer(CubeMesh(), material=material))

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
                    _init_passes=[color_pass, present_pass],
                    _init_specs=[
                        ResourceSpec(
                            resource="empty",
                            clear_color=(0.0, 0.0, 0.0, 1.0),
                            clear_depth=1.0,
                        ),
                    ],
                )

                view = RenderView(scene=scene, camera=camera, rect=(0.0, 0.0, 1.0, 1.0), pipeline=pipeline)
                state = ViewportRenderState()

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


class TestPipelineSerialization(unittest.TestCase):
    """Тесты сериализации/десериализации RenderPipeline."""

    def setUp(self):
        """Регистрируем встроенные пассы и эффекты перед каждым тестом."""
        from termin.visualization.core.resources import ResourceManager
        self.rm = ResourceManager.instance()
        self.rm.register_builtin_frame_passes()
        self.rm.register_builtin_post_effects()

    def test_color_pass_serialization(self):
        """Тест сериализации ColorPass."""
        color_pass = ColorPass(
            input_res="skybox",
            output_res="color",
            shadow_res="shadows",
            pass_name="MyColorPass",
            phase_mark="opaque",
        )
        color_pass.enabled = False

        data = color_pass.serialize()

        self.assertEqual(data["type"], "ColorPass")
        self.assertEqual(data["pass_name"], "MyColorPass")
        self.assertEqual(data["enabled"], False)
        self.assertEqual(data["input_res"], "skybox")
        self.assertEqual(data["output_res"], "color")
        self.assertEqual(data["shadow_res"], "shadows")
        self.assertEqual(data["phase_mark"], "opaque")

        # Десериализация
        from termin.visualization.render.framegraph.core import FramePass
        restored = FramePass.deserialize(data, self.rm)

        self.assertIsInstance(restored, ColorPass)
        self.assertEqual(restored.pass_name, "MyColorPass")
        self.assertEqual(restored.enabled, False)
        self.assertEqual(restored.input_res, "skybox")
        self.assertEqual(restored.output_res, "color")
        self.assertEqual(restored.shadow_res, "shadows")
        self.assertEqual(restored.phase_mark, "opaque")

    def test_shadow_pass_serialization(self):
        """Тест сериализации ShadowPass."""
        from termin.visualization.render.framegraph.passes.shadow import ShadowPass

        shadow_pass = ShadowPass(
            output_res="my_shadows",
            pass_name="MyShadows",
            caster_offset=100.0,
        )

        data = shadow_pass.serialize()

        self.assertEqual(data["type"], "ShadowPass")

        # Десериализация
        from termin.visualization.render.framegraph.core import FramePass
        restored = FramePass.deserialize(data, self.rm)

        self.assertIsInstance(restored, ShadowPass)
        self.assertEqual(restored.output_res, "my_shadows")

    def test_post_effect_serialization(self):
        """Тест сериализации PostEffect."""
        from termin.visualization.render.posteffects.fog import FogEffect
        from termin.visualization.render.postprocess import PostEffect

        fog = FogEffect(
            fog_color=(1.0, 0.5, 0.2),
            fog_start=0.15,
            fog_end=0.85,
        )

        data = fog.serialize()

        self.assertEqual(data["type"], "FogEffect")
        self.assertEqual(data["name"], "fog")
        self.assertEqual(data["fog_color"], [1.0, 0.5, 0.2])
        self.assertEqual(data["fog_start"], 0.15)
        self.assertEqual(data["fog_end"], 0.85)

        # Десериализация
        restored = PostEffect.deserialize(data, self.rm)

        self.assertIsInstance(restored, FogEffect)
        self.assertEqual(restored._fog_color, (1.0, 0.5, 0.2))
        self.assertEqual(restored._fog_start, 0.15)
        self.assertEqual(restored._fog_end, 0.85)

    def test_post_process_pass_with_effects_serialization(self):
        """Тест сериализации PostProcessPass с эффектами."""
        from termin.visualization.render.postprocess import PostProcessPass, PostEffect
        from termin.visualization.render.posteffects.fog import FogEffect
        from termin.visualization.render.posteffects.gray import GrayscaleEffect
        from termin.visualization.render.framegraph.core import FramePass

        pp = PostProcessPass(
            effects=[
                FogEffect(fog_color=(0.8, 0.8, 0.9), fog_start=0.3, fog_end=1.0),
                GrayscaleEffect(),
            ],
            input_res="color",
            output_res="color_pp",
            pass_name="MyPostProcess",
        )

        data = pp.serialize()

        self.assertEqual(data["type"], "PostProcessPass")
        self.assertEqual(data["input_res"], "color")
        self.assertEqual(data["output_res"], "color_pp")
        self.assertEqual(len(data["effects"]), 2)
        self.assertEqual(data["effects"][0]["type"], "FogEffect")
        self.assertEqual(data["effects"][1]["type"], "GrayscaleEffect")

        # Десериализация
        restored = FramePass.deserialize(data, self.rm)

        self.assertIsInstance(restored, PostProcessPass)
        self.assertEqual(restored.input_res, "color")
        self.assertEqual(restored.output_res, "color_pp")
        self.assertEqual(len(restored.effects), 2)
        self.assertIsInstance(restored.effects[0], FogEffect)
        self.assertIsInstance(restored.effects[1], GrayscaleEffect)

    def test_resource_spec_serialization(self):
        """Тест сериализации ResourceSpec."""
        spec = ResourceSpec(
            resource="my_fbo",
            resource_type="fbo",
            size=(1024, 1024),
            clear_color=(0.1, 0.2, 0.3, 1.0),
            clear_depth=0.5,
            format="RGBA16F",
        )

        data = spec.serialize()

        self.assertEqual(data["resource"], "my_fbo")
        self.assertEqual(data["resource_type"], "fbo")
        self.assertEqual(data["size"], [1024, 1024])
        self.assertEqual(data["clear_color"], [0.1, 0.2, 0.3, 1.0])
        self.assertEqual(data["clear_depth"], 0.5)
        self.assertEqual(data["format"], "RGBA16F")

        # Десериализация
        restored = ResourceSpec.deserialize(data)

        self.assertEqual(restored.resource, "my_fbo")
        self.assertEqual(restored.resource_type, "fbo")
        self.assertEqual(restored.size, (1024, 1024))
        self.assertEqual(restored.clear_color, (0.1, 0.2, 0.3, 1.0))
        self.assertEqual(restored.clear_depth, 0.5)
        self.assertEqual(restored.format, "RGBA16F")

    def test_full_pipeline_serialization(self):
        """Тест сериализации полного RenderPipeline."""
        from termin.visualization.render.framegraph.passes.skybox import SkyBoxPass
        from termin.visualization.render.framegraph.passes.shadow import ShadowPass
        from termin.visualization.render.postprocess import PostProcessPass
        from termin.visualization.render.posteffects.highlight import HighlightEffect

        # Создаём сложный пайплайн
        pipeline = RenderPipeline(
            _init_passes=[
                ShadowPass(
                    output_res="shadows",
                ),
                SkyBoxPass(
                    input_res="empty",
                    output_res="skybox",
                ),
                ColorPass(
                    input_res="skybox",
                    output_res="color",
                    shadow_res="shadows",
                    phase_mark="main",
                ),
                PostProcessPass(
                    effects=[HighlightEffect(color=(1.0, 1.0, 0.0, 1.0))],
                    input_res="color",
                    output_res="color_pp",
                ),
                PresentToScreenPass(
                    input_res="color_pp",
                ),
            ],
            _init_specs=[
                ResourceSpec(
                    resource="empty",
                    clear_color=(0.1, 0.1, 0.1, 1.0),
                    clear_depth=1.0,
                ),
            ],
        )

        # Сериализуем
        data = pipeline.serialize()

        self.assertEqual(len(data["passes"]), 5)
        self.assertEqual(data["passes"][0]["type"], "ShadowPass")
        self.assertEqual(data["passes"][1]["type"], "SkyBoxPass")
        self.assertEqual(data["passes"][2]["type"], "ColorPass")
        self.assertEqual(data["passes"][3]["type"], "PostProcessPass")
        self.assertEqual(data["passes"][4]["type"], "PresentToScreenPass")

        self.assertEqual(len(data["pipeline_specs"]), 1)
        self.assertEqual(data["pipeline_specs"][0]["resource"], "empty")

        # Десериализуем
        restored = RenderPipeline.deserialize(data, self.rm)

        self.assertEqual(len(restored.passes), 5)
        self.assertIsInstance(restored.passes[0], ShadowPass)
        self.assertIsInstance(restored.passes[1], SkyBoxPass)
        self.assertIsInstance(restored.passes[2], ColorPass)
        self.assertIsInstance(restored.passes[3], PostProcessPass)
        self.assertIsInstance(restored.passes[4], PresentToScreenPass)

        # Проверяем параметры восстановленных пассов
        self.assertEqual(restored.passes[0].default_resolution, 1024)
        self.assertEqual(restored.passes[2].phase_mark, "main")
        self.assertEqual(restored.passes[2].shadow_res, "shadows")

        # Проверяем эффекты в PostProcessPass
        pp = restored.passes[3]
        self.assertEqual(len(pp.effects), 1)
        self.assertIsInstance(pp.effects[0], HighlightEffect)
        self.assertEqual(pp.effects[0]._color, (1.0, 1.0, 0.0, 1.0))

        # Проверяем specs
        self.assertEqual(len(restored.pipeline_specs), 1)
        self.assertEqual(restored.pipeline_specs[0].resource, "empty")
        self.assertEqual(restored.pipeline_specs[0].clear_color, (0.1, 0.1, 0.1, 1.0))

    def test_pipeline_json_roundtrip(self):
        """Тест сериализации в JSON и обратно."""
        import json
        from termin.visualization.render.framegraph.passes.skybox import SkyBoxPass

        pipeline = RenderPipeline(
            _init_passes=[
                SkyBoxPass(input_res="empty", output_res="skybox"),
                ColorPass(input_res="skybox", output_res="color", phase_mark="main"),
                PresentToScreenPass(input_res="color"),
            ],
        )

        # Сериализуем в JSON
        data = pipeline.serialize()
        json_str = json.dumps(data, indent=2)

        # Десериализуем из JSON
        loaded_data = json.loads(json_str)
        restored = RenderPipeline.deserialize(loaded_data, self.rm)

        self.assertEqual(len(restored.passes), 3)
        self.assertEqual(restored.passes[0].input_res, "empty")
        self.assertEqual(restored.passes[1].phase_mark, "main")


if __name__ == "__main__":
    unittest.main()
