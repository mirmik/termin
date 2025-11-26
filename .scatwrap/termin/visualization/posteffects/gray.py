<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/posteffects/gray.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from termin.visualization.shader import ShaderProgram<br>
from termin.visualization.postprocess import PostEffect<br>
<br>
<br>
# ================================================================<br>
#                   GRAYSCALE EFFECT<br>
# ================================================================<br>
<br>
GRAY_VERT = &quot;&quot;&quot;<br>
#version 330 core<br>
layout(location=0) in vec2 a_pos;<br>
layout(location=1) in vec2 a_uv;<br>
out vec2 v_uv;<br>
void main() {<br>
    v_uv = a_uv;<br>
    gl_Position = vec4(a_pos, 0.0, 1.0);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
GRAY_FRAG = &quot;&quot;&quot;<br>
#version 330 core<br>
in vec2 v_uv;<br>
uniform sampler2D u_texture;<br>
out vec4 FragColor;<br>
<br>
void main() {<br>
    vec3 c = texture(u_texture, v_uv).rgb;<br>
    float g = dot(c, vec3(0.299, 0.587, 0.114));<br>
    FragColor = vec4(g, g, g, 1.0);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
class GrayscaleEffect(PostEffect):<br>
    name = &quot;grayscale&quot;<br>
<br>
    def __init__(self):<br>
        self._shader: ShaderProgram | None = None<br>
<br>
    def required_resources(self) -&gt; set[str]:<br>
        # Ему не нужны доп. ресурсы, только входной color_tex<br>
        return set()<br>
<br>
    def _get_shader(self) -&gt; ShaderProgram:<br>
        if self._shader is None:<br>
            from termin.visualization.shader import ShaderProgram<br>
            self._shader = ShaderProgram(GRAY_VERT, GRAY_FRAG)<br>
        return self._shader<br>
<br>
    def draw(self, gfx, key, color_tex, extra_textures, size):<br>
        w, h = size<br>
<br>
        shader = self._get_shader()<br>
        shader.ensure_ready(gfx)<br>
        shader.use()<br>
<br>
        # биндим цвет на юнит 0<br>
        color_tex.bind(0)<br>
<br>
        shader.set_uniform_int(&quot;u_texture&quot;, 0)<br>
<br>
        gfx.draw_ui_textured_quad(key)<br>
<!-- END SCAT CODE -->
</body>
</html>
