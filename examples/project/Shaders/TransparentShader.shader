@program TransparentShader

  @phase transparent

  @glBlend true
  @glDepthMask false
  @glDepthTest true
  @glCull false

  @property Color u_color = Color(1.0, 1.0, 1.0, 0.5)

  @stage vertex
  #version 330 core

  layout(location = 0) in vec3 a_position;
  layout(location = 1) in vec3 a_normal;

  uniform mat4 u_model;
  uniform mat4 u_view;
  uniform mat4 u_projection;

  void main() {
      gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
  }

  @stage fragment
  #version 330 core

  uniform vec4 u_color;

  out vec4 frag_color;

  void main() {
      frag_color = u_color;
  }