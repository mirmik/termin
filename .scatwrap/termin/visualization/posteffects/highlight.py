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
&#9;v_uv = a_uv;<br>
&#9;gl_Position = vec4(a_pos, 0.0, 1.0);<br>
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
&#9;// сравниваем с небольшим допуском<br>
&#9;float d = distance(id_color, u_selected_color);<br>
&#9;return float(d &lt; 0.001);<br>
}<br>
<br>
void main()<br>
{<br>
&#9;vec4 base = texture(u_color, v_uv);<br>
<br>
&#9;// если эффект выключен — просто пробрасываем цвет<br>
&#9;if (u_enabled &lt; 0.5) {<br>
&#9;&#9;FragColor = base;<br>
&#9;&#9;return;<br>
&#9;}<br>
<br>
&#9;vec3 id_center = texture(u_id, v_uv).rgb;<br>
<br>
&#9;float center_sel = is_selected(id_center);<br>
<br>
&#9;vec2 ts = u_texel_size;<br>
<br>
&#9;// смотрим соседей — простой дифференциальный контур<br>
&#9;float neigh_sel = 0.0;<br>
&#9;neigh_sel = max(neigh_sel, is_selected(texture(u_id, v_uv + vec2( ts.x,  0.0)).rgb));<br>
&#9;neigh_sel = max(neigh_sel, is_selected(texture(u_id, v_uv + vec2(-ts.x,  0.0)).rgb));<br>
&#9;neigh_sel = max(neigh_sel, is_selected(texture(u_id, v_uv + vec2( 0.0,  ts.y)).rgb));<br>
&#9;neigh_sel = max(neigh_sel, is_selected(texture(u_id, v_uv + vec2( 0.0, -ts.y)).rgb));<br>
<br>
&#9;float outline = 0.0;<br>
<br>
&#9;// внутренняя граница: центр выбран, а вокруг нет<br>
&#9;outline = max(outline, center_sel * (1.0 - neigh_sel));<br>
&#9;// внешняя граница: центр не выбран, а рядом есть выбранные<br>
&#9;outline = max(outline, neigh_sel * (1.0 - center_sel));<br>
<br>
&#9;if (outline &gt; 0.0) {<br>
&#9;&#9;// смешиваем базовый цвет и цвет рамки<br>
&#9;&#9;float k = 0.8; // сила смешивания<br>
&#9;&#9;vec3 col = mix(base.rgb, u_outline_color, k);<br>
&#9;&#9;FragColor = vec4(col, base.a);<br>
&#9;} else {<br>
&#9;&#9;FragColor = base;<br>
&#9;}<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
class HighlightEffect(PostEffect):<br>
&#9;name = &quot;highlight&quot;<br>
<br>
&#9;def __init__(self, selected_id_getter, color=(0.0, 0.0, 0.0, 1.0)):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;selected_id_getter: callable -&gt; int | None<br>
&#9;&#9;(например, лямбда, которая читает selected_entity_id из редактора)<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self._get_id = selected_id_getter<br>
&#9;&#9;self._color = color<br>
&#9;&#9;self._shader: ShaderProgram | None = None<br>
<br>
&#9;def required_resources(self) -&gt; set[str]:<br>
&#9;&#9;# Нужна id-карта с именем &quot;id&quot; (её пишет IdPass)<br>
&#9;&#9;return {&quot;id&quot;}<br>
<br>
&#9;def _get_shader(self) -&gt; ShaderProgram:<br>
&#9;&#9;if self._shader is None:<br>
&#9;&#9;&#9;self._shader = ShaderProgram(HIGHLIGHT_VERT, HIGHLIGHT_FRAG)<br>
&#9;&#9;return self._shader<br>
<br>
&#9;def draw(self, gfx, key, color_tex, extra_textures, size):<br>
&#9;&#9;w, h = size<br>
&#9;&#9;tex_id = extra_textures.get(&quot;id&quot;)<br>
<br>
&#9;&#9;# id выделенного энтити<br>
&#9;&#9;selected_id = self._get_id() or 0<br>
<br>
&#9;&#9;shader = self._get_shader()<br>
&#9;&#9;shader.ensure_ready(gfx)<br>
&#9;&#9;shader.use()<br>
<br>
&#9;&#9;# основной цвет<br>
&#9;&#9;color_tex.bind(0)<br>
&#9;&#9;shader.set_uniform_int(&quot;u_color&quot;, 0)<br>
<br>
&#9;&#9;# включён ли эффект?<br>
&#9;&#9;enabled = (tex_id is not None) and (selected_id &gt; 0)<br>
&#9;&#9;shader.set_uniform_float(&quot;u_enabled&quot;, 1.0 if enabled else 0.0)<br>
<br>
&#9;&#9;# если можем — биндим id-map и передаём цвет выбранного id<br>
&#9;&#9;if enabled:<br>
&#9;&#9;&#9;tex_id.bind(1)<br>
&#9;&#9;&#9;shader.set_uniform_int(&quot;u_id&quot;, 1)<br>
<br>
&#9;&#9;&#9;sel_color = id_to_rgb(selected_id)  # (r,g,b) того же формата, что в IdPass<br>
&#9;&#9;&#9;shader.set_uniform_vec3(&quot;u_selected_color&quot;, sel_color)<br>
<br>
&#9;&#9;# размер текселя (для выборки соседей)<br>
&#9;&#9;texel_size = np.array(<br>
&#9;&#9;&#9;[1.0 / max(1, w), 1.0 / max(1, h)],<br>
&#9;&#9;&#9;dtype=np.float32,<br>
&#9;&#9;)<br>
&#9;&#9;shader.set_uniform_vec2(&quot;u_texel_size&quot;, texel_size)<br>
<br>
&#9;&#9;# цвет рамки (желтый, например)<br>
&#9;&#9;outline_color = np.array(self._color[0:3], dtype=np.float32)<br>
&#9;&#9;shader.set_uniform_vec3(&quot;u_outline_color&quot;, outline_color)<br>
<br>
&#9;&#9;# остальное состояние depth/blend уже подготовил PostProcessPass<br>
&#9;&#9;gfx.draw_ui_textured_quad(key)<br>
<!-- END SCAT CODE -->
</body>
</html>
