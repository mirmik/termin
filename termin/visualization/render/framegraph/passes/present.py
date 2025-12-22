from __future__ import annotations

from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.visualization.render.shader import ShaderProgram
from termin.editor.inspect_field import InspectField


def _get_texture_from_resource(resource, shadow_map_index: int = 0):
    """
    Извлекает текстуру из ресурса framegraph для отображения.

    Поддерживает:
    - SingleFBO: возвращает color_texture()
    - ShadowMapArrayResource: возвращает текстуру из первого entry (или по индексу)

    Args:
        resource: объект ресурса (SingleFBO, ShadowMapArrayResource и т.д.)
        shadow_map_index: индекс shadow map для ShadowMapArrayResource

    Returns:
        TextureHandle или None
    """
    if resource is None:
        return None

    # Проверяем тип ресурса через атрибут resource_type
    if hasattr(resource, 'resource_type'):
        resource_type = resource.resource_type

        if resource_type == "shadow_map_array":
            # ShadowMapArrayResource - берем первую текстуру по умолчанию
            if len(resource) == 0:
                return None
            index = min(shadow_map_index, len(resource) - 1)
            entry = resource[index]
            return entry.texture()

        elif resource_type == "fbo":
            # SingleFBO
            return resource.color_texture()

    # Для обратной совместимости: если нет resource_type, пробуем color_texture
    if hasattr(resource, 'color_texture'):
        return resource.color_texture()

    return None


def blit_fbo_to_fbo(
    gfx: "GraphicsBackend",
    src_fb,
    dst_fb,
    size: tuple[int, int],
    context_key: int,
):
    from termin.visualization.platform.backends.nop_graphics import NOPGraphicsBackend

    # Для NOP бэкенда пропускаем реальные OpenGL операции
    if isinstance(gfx, NOPGraphicsBackend):
        return

    w, h = size

    # целевой FBO
    gfx.bind_framebuffer(dst_fb)
    gfx.set_viewport(0, 0, w, h)

    # глубина нам не нужна
    gfx.set_depth_test(False)
    gfx.set_depth_mask(False)

    # берём ту же фуллскрин-квад-программу, что и PresentToScreenPass
    shader = PresentToScreenPass._get_shader()
    shader.ensure_ready(gfx)
    shader.use()
    shader.set_uniform_int("u_tex", 0)

    # Извлекаем текстуру с учетом типа ресурса
    tex = _get_texture_from_resource(src_fb)
    if tex is None:
        # Если не удалось получить текстуру, ничего не делаем
        gfx.set_depth_test(True)
        gfx.set_depth_mask(True)
        return

    tex.bind(0)

    gfx.draw_ui_textured_quad(context_key)

    gfx.set_depth_test(True)
    gfx.set_depth_mask(True)


class BlitPass(RenderFramePass):
    """
    Копирует color-текстуру из одного FBO в другой через фуллскрин-квад.
    Источник задаётся колбэком get_source_res, чтобы его можно было
    динамически переключать из редактора/дебагера.

    Для отключения пасса используйте enabled=False.

    Note: get_source_res — runtime callback, не сериализуется.
    При десериализации нужно задать его отдельно.
    """

    def __init__(
        self,
        get_source_res=None,
        output_res: str = "debug",
        pass_name: str = "Blit",
    ):
        super().__init__(
            pass_name=pass_name,
            reads=set(),  # фактическое имя ресурса задаётся динамически
            writes={output_res},
        )
        self._get_source_res = get_source_res
        self.output_res = output_res
        self._current_src_name: str | None = None

    def _serialize_params(self) -> dict:
        """Сериализует параметры BlitPass."""
        return {
            "output_res": self.output_res,
        }

    @classmethod
    def _deserialize_instance(cls, data: dict, resource_manager=None) -> "BlitPass":
        """Создаёт BlitPass из сериализованных данных."""
        return cls(
            get_source_res=None,  # Runtime callback, не сериализуется
            output_res=data.get("output_res", "debug"),
            pass_name=data.get("pass_name", "Blit"),
        )

    def required_resources(self) -> set[str]:
        resources = set(self.writes)
        if self._get_source_res is None:
            self._current_src_name = None
            self.reads = set()
            return resources

        src_name = self._get_source_res()
        if src_name:
            self._current_src_name = src_name
            self.reads = {src_name}
            resources.add(src_name)
        else:
            self.reads = set()
            self._current_src_name = None

        return resources

    def execute(
        self,
        graphics: "GraphicsBackend",
        reads_fbos: dict[str, "FramebufferHandle" | None],
        writes_fbos: dict[str, "FramebufferHandle" | None],
        rect: tuple[int, int, int, int],
        scene=None,
        camera=None,
        context_key: int = 0,
        lights=None,
        canvas=None,
    ):
        px, py, pw, ph = rect
        key = context_key

        if self._get_source_res is None:
            return

        src_name = self._get_source_res()
        if not src_name:
            return

        fb_in = reads_fbos.get(src_name)
        if fb_in is None:
            return

        fb_out = writes_fbos.get(self.output_res)
        if fb_out is None:
            return
        
        blit_fbo_to_fbo(graphics, fb_in, fb_out, (pw, ph), key)


FSQ_VERT = """
#version 330 core
layout(location = 0) in vec2 a_pos;
layout(location = 1) in vec2 a_uv;

out vec2 v_uv;

void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
"""

FSQ_FRAG = """
#version 330 core
in vec2 v_uv;
out vec4 FragColor;

uniform sampler2D u_tex;

void main() {
    FragColor = texture(u_tex, v_uv);
}
"""


class ResolvePass(RenderFramePass):
    """
    Resolve MSAA FBO в обычный FBO через glBlitFramebuffer.

    Необходим перед любым pass'ом, который сэмплирует текстуру (PostProcess и др.),
    если источник — MSAA FBO.
    """

    def __init__(
        self,
        input_res: str,
        output_res: str,
        pass_name: str = "Resolve",
    ):
        super().__init__(
            pass_name=pass_name,
            reads={input_res},
            writes={output_res},
        )
        self.input_res = input_res
        self.output_res = output_res

    def _serialize_params(self) -> dict:
        return {
            "input_res": self.input_res,
            "output_res": self.output_res,
        }

    @classmethod
    def _deserialize_instance(cls, data: dict, resource_manager=None) -> "ResolvePass":
        return cls(
            input_res=data.get("input_res", "color"),
            output_res=data.get("output_res", "color_resolved"),
            pass_name=data.get("pass_name", "Resolve"),
        )

    def execute(
        self,
        graphics: "GraphicsBackend",
        reads_fbos: dict[str, "FramebufferHandle" | None],
        writes_fbos: dict[str, "FramebufferHandle" | None],
        rect: tuple[int, int, int, int],
        scene=None,
        camera=None,
        context_key: int = 0,
        lights=None,
        canvas=None,
    ):
        from termin.visualization.platform.backends.nop_graphics import NOPGraphicsBackend

        if isinstance(graphics, NOPGraphicsBackend):
            return

        px, py, pw, ph = rect

        fb_in = reads_fbos.get(self.input_res)
        fb_out = writes_fbos.get(self.output_res)
        if fb_in is None or fb_out is None:
            return

        src_size = fb_in.get_size()
        graphics.blit_framebuffer(
            fb_in,
            fb_out,
            (0, 0, src_size[0], src_size[1]),
            (0, 0, pw, ph),
        )


class PresentToScreenPass(RenderFramePass):
    """
    Берёт текстуру из ресурса input_res и выводит её на экран
    фуллскрин-квадом.
    """

    inspect_fields = {
        "input_res": InspectField(path="input_res", label="Input Resource", kind="string"),
        "output_res": InspectField(path="output_res", label="Output Resource", kind="string"),
    }

    _shader: ShaderProgram | None = None

    def __init__(self, input_res: str, output_res: str = "DISPLAY", pass_name: str = "PresentToScreen"):
        super().__init__(
            pass_name=pass_name,
            reads={input_res},
            writes={output_res},
        )
        self.input_res = input_res
        self.output_res = output_res

    def _serialize_params(self) -> dict:
        """Сериализует параметры PresentToScreenPass."""
        return {
            "input_res": self.input_res,
            "output_res": self.output_res,
        }

    @classmethod
    def _deserialize_instance(cls, data: dict, resource_manager=None) -> "PresentToScreenPass":
        """Создаёт PresentToScreenPass из сериализованных данных."""
        return cls(
            input_res=data.get("input_res", "color"),
            output_res=data.get("output_res", "DISPLAY"),
            pass_name=data.get("pass_name", "PresentToScreen"),
        )

    @classmethod
    def _get_shader(cls) -> ShaderProgram:
        if cls._shader is None:
            cls._shader = ShaderProgram(FSQ_VERT, FSQ_FRAG)
        return cls._shader

    def execute(
        self,
        graphics: "GraphicsBackend",
        reads_fbos: dict[str, "FramebufferHandle" | None],
        writes_fbos: dict[str, "FramebufferHandle" | None],
        rect: tuple[int, int, int, int],
        scene=None,
        camera=None,
        context_key: int = 0,
        lights=None,
        canvas=None,
    ):
        from termin.visualization.platform.backends.nop_graphics import NOPGraphicsBackend

        # Для NOP бэкенда пропускаем реальные OpenGL операции
        if isinstance(graphics, NOPGraphicsBackend):
            return

        px, py, pw, ph = rect

        fb_in = reads_fbos.get(self.input_res)
        fb_out = writes_fbos.get("DISPLAY")
        if fb_in is None or fb_out is None:
            return

        # Используем glBlitFramebuffer — работает и для обычных FBO, и для MSAA (resolve)
        src_size = fb_in.get_size()
        graphics.blit_framebuffer(
            fb_in,
            fb_out,
            (0, 0, src_size[0], src_size[1]),
            (px, py, px + pw, py + ph),
        )
