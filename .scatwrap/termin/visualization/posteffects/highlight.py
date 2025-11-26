<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/posteffects/highlight.py</title>
</head>
<body>
<pre><code>
# termin/visualization/posteffects/highlight.py

from __future__ import annotations

import numpy as np

from termin.visualization.postprocess import PostEffect
from termin.visualization.shader import ShaderProgram
from termin.visualization.picking import id_to_rgb


HIGHLIGHT_VERT = &quot;&quot;&quot;
#version 330 core
layout(location=0) in vec2 a_pos;
layout(location=1) in vec2 a_uv;
out vec2 v_uv;
void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
&quot;&quot;&quot;

HIGHLIGHT_FRAG = &quot;&quot;&quot;
#version 330 core
in vec2 v_uv;

uniform sampler2D u_color;        // обычный цветной рендер
uniform sampler2D u_id;           // id-map
uniform vec3      u_selected_color; // цвет, соответствующий выбранному id
uniform vec2      u_texel_size;   // 1.0 / resolution
uniform vec3      u_outline_color; // цвет рамки
uniform float     u_enabled;      // 0.0 -&gt; эффект выключен

out vec4 FragColor;

float is_selected(vec3 id_color)
{
    // сравниваем с небольшим допуском
    float d = distance(id_color, u_selected_color);
    return float(d &lt; 0.001);
}

void main()
{
    vec4 base = texture(u_color, v_uv);

    // если эффект выключен — просто пробрасываем цвет
    if (u_enabled &lt; 0.5) {
        FragColor = base;
        return;
    }

    vec3 id_center = texture(u_id, v_uv).rgb;

    float center_sel = is_selected(id_center);

    vec2 ts = u_texel_size;

    // смотрим соседей — простой дифференциальный контур
    float neigh_sel = 0.0;
    neigh_sel = max(neigh_sel, is_selected(texture(u_id, v_uv + vec2( ts.x,  0.0)).rgb));
    neigh_sel = max(neigh_sel, is_selected(texture(u_id, v_uv + vec2(-ts.x,  0.0)).rgb));
    neigh_sel = max(neigh_sel, is_selected(texture(u_id, v_uv + vec2( 0.0,  ts.y)).rgb));
    neigh_sel = max(neigh_sel, is_selected(texture(u_id, v_uv + vec2( 0.0, -ts.y)).rgb));

    float outline = 0.0;

    // внутренняя граница: центр выбран, а вокруг нет
    outline = max(outline, center_sel * (1.0 - neigh_sel));
    // внешняя граница: центр не выбран, а рядом есть выбранные
    outline = max(outline, neigh_sel * (1.0 - center_sel));

    if (outline &gt; 0.0) {
        // смешиваем базовый цвет и цвет рамки
        float k = 0.8; // сила смешивания
        vec3 col = mix(base.rgb, u_outline_color, k);
        FragColor = vec4(col, base.a);
    } else {
        FragColor = base;
    }
}
&quot;&quot;&quot;


class HighlightEffect(PostEffect):
    name = &quot;highlight&quot;

    def __init__(self, selected_id_getter, color=(0.0, 0.0, 0.0, 1.0)):
        &quot;&quot;&quot;
        selected_id_getter: callable -&gt; int | None
        (например, лямбда, которая читает selected_entity_id из редактора)
        &quot;&quot;&quot;
        self._get_id = selected_id_getter
        self._color = color
        self._shader: ShaderProgram | None = None

    def required_resources(self) -&gt; set[str]:
        # Нужна id-карта с именем &quot;id&quot; (её пишет IdPass)
        return {&quot;id&quot;}

    def _get_shader(self) -&gt; ShaderProgram:
        if self._shader is None:
            self._shader = ShaderProgram(HIGHLIGHT_VERT, HIGHLIGHT_FRAG)
        return self._shader

    def draw(self, gfx, key, color_tex, extra_textures, size):
        w, h = size
        tex_id = extra_textures.get(&quot;id&quot;)

        # id выделенного энтити
        selected_id = self._get_id() or 0

        shader = self._get_shader()
        shader.ensure_ready(gfx)
        shader.use()

        # основной цвет
        color_tex.bind(0)
        shader.set_uniform_int(&quot;u_color&quot;, 0)

        # включён ли эффект?
        enabled = (tex_id is not None) and (selected_id &gt; 0)
        shader.set_uniform_float(&quot;u_enabled&quot;, 1.0 if enabled else 0.0)

        # если можем — биндим id-map и передаём цвет выбранного id
        if enabled:
            tex_id.bind(1)
            shader.set_uniform_int(&quot;u_id&quot;, 1)

            sel_color = id_to_rgb(selected_id)  # (r,g,b) того же формата, что в IdPass
            shader.set_uniform_vec3(&quot;u_selected_color&quot;, sel_color)

        # размер текселя (для выборки соседей)
        texel_size = np.array(
            [1.0 / max(1, w), 1.0 / max(1, h)],
            dtype=np.float32,
        )
        shader.set_uniform_vec2(&quot;u_texel_size&quot;, texel_size)

        # цвет рамки (желтый, например)
        outline_color = np.array(self._color[0:3], dtype=np.float32)
        shader.set_uniform_vec3(&quot;u_outline_color&quot;, outline_color)

        # остальное состояние depth/blend уже подготовил PostProcessPass
        gfx.draw_ui_textured_quad(key)

</code></pre>
</body>
</html>
