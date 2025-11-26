<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/posteffects/blur.py</title>
</head>
<body>
<pre><code>
import numpy as np
from ..shader import ShaderProgram
from ..postprocess import PostEffect

# ================================================================
#          TWO-PASS GAUSSIAN BLUR (H + V)
# ================================================================

GAUSS_VERT = &quot;&quot;&quot;
#version 330 core
layout(location=0) in vec2 a_pos;
layout(location=1) in vec2 a_uv;
out vec2 v_uv;
void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
&quot;&quot;&quot;

GAUSS_FRAG = &quot;&quot;&quot;
#version 330 core
in vec2 v_uv;

uniform sampler2D u_texture;
uniform vec2 u_direction;   // (1,0) for horizontal, (0,1) for vertical
uniform vec2 u_texel_size;  // 1.0 / resolution

out vec4 FragColor;

// 5-tap gaussian weights (approx sigma=2)
const float w0 = 0.227027;
const float w1 = 0.316216;
const float w2 = 0.070270;

void main() {
    vec2 ts = u_texel_size;
    vec2 dir = u_direction;

    vec3 c = texture(u_texture, v_uv).rgb * w0;
    c += texture(u_texture, v_uv + dir * ts * 1.0).rgb * w1;
    c += texture(u_texture, v_uv - dir * ts * 1.0).rgb * w1;
    c += texture(u_texture, v_uv + dir * ts * 2.0).rgb * w2;
    c += texture(u_texture, v_uv - dir * ts * 2.0).rgb * w2;

    FragColor = vec4(c, 1.0);
}
&quot;&quot;&quot;

class GaussianBlurPass(PostEffect):
    &quot;&quot;&quot;Один проход: горизонтальный или вертикальный.&quot;&quot;&quot;

    def __init__(self, direction):
        self.shader = ShaderProgram(GAUSS_VERT, GAUSS_FRAG)
        self.direction = np.array(direction, dtype=np.float32)

    def draw(self, gfx, key, color_tex, extra_textures, size):
        w, h = size
        texel_size = np.array([1.0/max(1,w), 1.0/max(1,h)], dtype=np.float32)

        self.shader.ensure_ready(gfx)
        self.shader.use()

        color_tex.bind(0)
        self.shader.set_uniform_int(&quot;u_texture&quot;, 0)
        self.shader.set_uniform_auto(&quot;u_texel_size&quot;, texel_size)
        self.shader.set_uniform_auto(&quot;u_direction&quot;, self.direction)

        gfx.set_depth_test(False)
        gfx.set_cull_face(False)
        gfx.set_blend(False)

        gfx.draw_ui_textured_quad(key)
</code></pre>
</body>
</html>
