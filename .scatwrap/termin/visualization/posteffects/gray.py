<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/posteffects/gray.py</title>
</head>
<body>
<pre><code>
from termin.visualization.shader import ShaderProgram
from termin.visualization.postprocess import PostEffect


# ================================================================
#                   GRAYSCALE EFFECT
# ================================================================

GRAY_VERT = &quot;&quot;&quot;
#version 330 core
layout(location=0) in vec2 a_pos;
layout(location=1) in vec2 a_uv;
out vec2 v_uv;
void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
&quot;&quot;&quot;

GRAY_FRAG = &quot;&quot;&quot;
#version 330 core
in vec2 v_uv;
uniform sampler2D u_texture;
out vec4 FragColor;

void main() {
    vec3 c = texture(u_texture, v_uv).rgb;
    float g = dot(c, vec3(0.299, 0.587, 0.114));
    FragColor = vec4(g, g, g, 1.0);
}
&quot;&quot;&quot;

class GrayscaleEffect(PostEffect):
    name = &quot;grayscale&quot;

    def __init__(self):
        self._shader: ShaderProgram | None = None

    def required_resources(self) -&gt; set[str]:
        # Ему не нужны доп. ресурсы, только входной color_tex
        return set()

    def _get_shader(self) -&gt; ShaderProgram:
        if self._shader is None:
            from termin.visualization.shader import ShaderProgram
            self._shader = ShaderProgram(GRAY_VERT, GRAY_FRAG)
        return self._shader

    def draw(self, gfx, key, color_tex, extra_textures, size):
        w, h = size

        shader = self._get_shader()
        shader.ensure_ready(gfx)
        shader.use()

        # биндим цвет на юнит 0
        color_tex.bind(0)

        shader.set_uniform_int(&quot;u_texture&quot;, 0)

        gfx.draw_ui_textured_quad(key)

</code></pre>
</body>
</html>
