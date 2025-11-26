<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/posteffects/blur.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import numpy as np<br>
from ..shader import ShaderProgram<br>
from ..postprocess import PostEffect<br>
<br>
# ================================================================<br>
#          TWO-PASS GAUSSIAN BLUR (H + V)<br>
# ================================================================<br>
<br>
GAUSS_VERT = &quot;&quot;&quot;<br>
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
GAUSS_FRAG = &quot;&quot;&quot;<br>
#version 330 core<br>
in vec2 v_uv;<br>
<br>
uniform sampler2D u_texture;<br>
uniform vec2 u_direction;   // (1,0) for horizontal, (0,1) for vertical<br>
uniform vec2 u_texel_size;  // 1.0 / resolution<br>
<br>
out vec4 FragColor;<br>
<br>
// 5-tap gaussian weights (approx sigma=2)<br>
const float w0 = 0.227027;<br>
const float w1 = 0.316216;<br>
const float w2 = 0.070270;<br>
<br>
void main() {<br>
    vec2 ts = u_texel_size;<br>
    vec2 dir = u_direction;<br>
<br>
    vec3 c = texture(u_texture, v_uv).rgb * w0;<br>
    c += texture(u_texture, v_uv + dir * ts * 1.0).rgb * w1;<br>
    c += texture(u_texture, v_uv - dir * ts * 1.0).rgb * w1;<br>
    c += texture(u_texture, v_uv + dir * ts * 2.0).rgb * w2;<br>
    c += texture(u_texture, v_uv - dir * ts * 2.0).rgb * w2;<br>
<br>
    FragColor = vec4(c, 1.0);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
class GaussianBlurPass(PostEffect):<br>
    &quot;&quot;&quot;Один проход: горизонтальный или вертикальный.&quot;&quot;&quot;<br>
<br>
    def __init__(self, direction):<br>
        self.shader = ShaderProgram(GAUSS_VERT, GAUSS_FRAG)<br>
        self.direction = np.array(direction, dtype=np.float32)<br>
<br>
    def draw(self, gfx, key, color_tex, extra_textures, size):<br>
        w, h = size<br>
        texel_size = np.array([1.0/max(1,w), 1.0/max(1,h)], dtype=np.float32)<br>
<br>
        self.shader.ensure_ready(gfx)<br>
        self.shader.use()<br>
<br>
        color_tex.bind(0)<br>
        self.shader.set_uniform_int(&quot;u_texture&quot;, 0)<br>
        self.shader.set_uniform_auto(&quot;u_texel_size&quot;, texel_size)<br>
        self.shader.set_uniform_auto(&quot;u_direction&quot;, self.direction)<br>
<br>
        gfx.set_depth_test(False)<br>
        gfx.set_cull_face(False)<br>
        gfx.set_blend(False)<br>
<br>
        gfx.draw_ui_textured_quad(key)<br>
<!-- END SCAT CODE -->
</body>
</html>
