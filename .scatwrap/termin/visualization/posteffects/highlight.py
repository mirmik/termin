<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/posteffects/highlight.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
# termin/visualization/posteffects/highlight.py<br>
<br>
from __future__ import annotations<br>
<br>
import numpy as np<br>
<br>
from termin.visualization.postprocess import PostEffect<br>
from termin.visualization.shader import ShaderProgram<br>
from termin.visualization.picking import id_to_rgb<br>
<br>
<br>
HIGHLIGHT_VERT = &quot;&quot;&quot;<br>
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
HIGHLIGHT_FRAG = &quot;&quot;&quot;<br>
#version 330 core<br>
in vec2 v_uv;<br>
<br>
uniform sampler2D u_color;        // обычный цветной рендер<br>
uniform sampler2D u_id;           // id-map<br>
uniform vec3      u_selected_color; // цвет, соответствующий выбранному id<br>
uniform vec2      u_texel_size;   // 1.0 / resolution<br>
uniform vec3      u_outline_color; // цвет рамки<br>
uniform float     u_enabled;      // 0.0 -&gt; эффект выключен<br>
<br>
out vec4 FragColor;<br>
<br>
float is_selected(vec3 id_color)<br>
{<br>
    // сравниваем с небольшим допуском<br>
    float d = distance(id_color, u_selected_color);<br>
    return float(d &lt; 0.001);<br>
}<br>
<br>
void main()<br>
{<br>
    vec4 base = texture(u_color, v_uv);<br>
<br>
    // если эффект выключен — просто пробрасываем цвет<br>
    if (u_enabled &lt; 0.5) {<br>
        FragColor = base;<br>
        return;<br>
    }<br>
<br>
    vec3 id_center = texture(u_id, v_uv).rgb;<br>
<br>
    float center_sel = is_selected(id_center);<br>
<br>
    vec2 ts = u_texel_size;<br>
<br>
    // смотрим соседей — простой дифференциальный контур<br>
    float neigh_sel = 0.0;<br>
    neigh_sel = max(neigh_sel, is_selected(texture(u_id, v_uv + vec2( ts.x,  0.0)).rgb));<br>
    neigh_sel = max(neigh_sel, is_selected(texture(u_id, v_uv + vec2(-ts.x,  0.0)).rgb));<br>
    neigh_sel = max(neigh_sel, is_selected(texture(u_id, v_uv + vec2( 0.0,  ts.y)).rgb));<br>
    neigh_sel = max(neigh_sel, is_selected(texture(u_id, v_uv + vec2( 0.0, -ts.y)).rgb));<br>
<br>
    float outline = 0.0;<br>
<br>
    // внутренняя граница: центр выбран, а вокруг нет<br>
    outline = max(outline, center_sel * (1.0 - neigh_sel));<br>
    // внешняя граница: центр не выбран, а рядом есть выбранные<br>
    outline = max(outline, neigh_sel * (1.0 - center_sel));<br>
<br>
    if (outline &gt; 0.0) {<br>
        // смешиваем базовый цвет и цвет рамки<br>
        float k = 0.8; // сила смешивания<br>
        vec3 col = mix(base.rgb, u_outline_color, k);<br>
        FragColor = vec4(col, base.a);<br>
    } else {<br>
        FragColor = base;<br>
    }<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
class HighlightEffect(PostEffect):<br>
    name = &quot;highlight&quot;<br>
<br>
    def __init__(self, selected_id_getter, color=(0.0, 0.0, 0.0, 1.0)):<br>
        &quot;&quot;&quot;<br>
        selected_id_getter: callable -&gt; int | None<br>
        (например, лямбда, которая читает selected_entity_id из редактора)<br>
        &quot;&quot;&quot;<br>
        self._get_id = selected_id_getter<br>
        self._color = color<br>
        self._shader: ShaderProgram | None = None<br>
<br>
    def required_resources(self) -&gt; set[str]:<br>
        # Нужна id-карта с именем &quot;id&quot; (её пишет IdPass)<br>
        return {&quot;id&quot;}<br>
<br>
    def _get_shader(self) -&gt; ShaderProgram:<br>
        if self._shader is None:<br>
            self._shader = ShaderProgram(HIGHLIGHT_VERT, HIGHLIGHT_FRAG)<br>
        return self._shader<br>
<br>
    def draw(self, gfx, key, color_tex, extra_textures, size):<br>
        w, h = size<br>
        tex_id = extra_textures.get(&quot;id&quot;)<br>
<br>
        # id выделенного энтити<br>
        selected_id = self._get_id() or 0<br>
<br>
        shader = self._get_shader()<br>
        shader.ensure_ready(gfx)<br>
        shader.use()<br>
<br>
        # основной цвет<br>
        color_tex.bind(0)<br>
        shader.set_uniform_int(&quot;u_color&quot;, 0)<br>
<br>
        # включён ли эффект?<br>
        enabled = (tex_id is not None) and (selected_id &gt; 0)<br>
        shader.set_uniform_float(&quot;u_enabled&quot;, 1.0 if enabled else 0.0)<br>
<br>
        # если можем — биндим id-map и передаём цвет выбранного id<br>
        if enabled:<br>
            tex_id.bind(1)<br>
            shader.set_uniform_int(&quot;u_id&quot;, 1)<br>
<br>
            sel_color = id_to_rgb(selected_id)  # (r,g,b) того же формата, что в IdPass<br>
            shader.set_uniform_vec3(&quot;u_selected_color&quot;, sel_color)<br>
<br>
        # размер текселя (для выборки соседей)<br>
        texel_size = np.array(<br>
            [1.0 / max(1, w), 1.0 / max(1, h)],<br>
            dtype=np.float32,<br>
        )<br>
        shader.set_uniform_vec2(&quot;u_texel_size&quot;, texel_size)<br>
<br>
        # цвет рамки (желтый, например)<br>
        outline_color = np.array(self._color[0:3], dtype=np.float32)<br>
        shader.set_uniform_vec3(&quot;u_outline_color&quot;, outline_color)<br>
<br>
        # остальное состояние depth/blend уже подготовил PostProcessPass<br>
        gfx.draw_ui_textured_quad(key)<br>
<!-- END SCAT CODE -->
</body>
</html>
