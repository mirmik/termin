from termin.visualization.postprocess import PostEffect
from termin.visualization.shader import ShaderProgram

class HighlightEffect(PostEffect):
    name = "highlight"

    def __init__(self, selected_id_getter):
        """
        selected_id_getter: callable -> int | None
        (например, лямбда, которая читает selected_entity_id из редактора)
        """
        self._get_id = selected_id_getter
        self._shader: ShaderProgram | None = None

    def required_resources(self) -> set[str]:
        # Хочется иметь доступ к id-карте
        return {"id"}

    def _get_shader(self) -> ShaderProgram:
        if self._shader is None:
            from termin.visualization.shader import ShaderProgram
            self._shader = ShaderProgram(HIGHLIGHT_VERT, HIGHLIGHT_FRAG)
        return self._shader

    def draw(self, gfx, key, color_tex, extra_textures, size):
        w, h = size
        tex_id = extra_textures.get("id")

        # если id-карты нет — просто пробрасываем color как есть
        if tex_id is None:
            # можно сделать через identity-шейдер, если нужно
            color_tex.bind(0)
            # ... отрисовка FSQ ...
            return

        selected_id = self._get_id() or 0

        shader = self._get_shader()
        shader.ensure_ready(gfx)
        shader.use()

        # биндим цвет и id на разные юниты
        color_tex.bind(0)
        tex_id.bind(1)

        shader.set_uniform_int("u_color", 0)
        shader.set_uniform_int("u_id", 1)

        # на CPU ты можешь превратить selected_id в цвет через id_to_rgb
        from .picking import id_to_rgb
        sel_color = id_to_rgb(selected_id)
        shader.set_uniform_vec3("u_selected_color", sel_color[:3])
        # + любые параметры рамочки

        gfx.draw_ui_textured_quad(key)
