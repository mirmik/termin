# termin/visualization/materials/pick_material.py (или рядом)

from termin.visualization.material import Material

vert_shader = """
// vertex.glsl
layout(location=0) in vec3 a_position;
uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_proj;
void main() {
    gl_Position = u_proj * u_view * u_model * vec4(a_position, 1.0);
}
"""

frag_shader = """
// fragment.glsl
uniform vec3 u_pickColor;
out vec4 fragColor;
void main() {
    fragColor = vec4(u_pickColor, 1.0);
}
"""

class PickMaterial(Material):
    def __init__(self):
        shader = ShaderProgram(vert_shader, frag_shader)
        super().__init__(shader=shader)

    def apply_for_pick(self, model, view, proj, pick_color, graphics, context_key):
        self.apply(model, view, proj, graphics=graphics, context_key=context_key)
        self.shader.set_uniform_vec3("u_pickColor", pick_color)
