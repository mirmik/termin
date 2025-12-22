"""
System shaders registry.

Simple shaders used by render passes (shadow, pick, etc.)
that don't need material phases.

These are compiled lazily on first use and cached per-context.
"""

from __future__ import annotations

from typing import Dict, TYPE_CHECKING

from termin.visualization.render.shader import ShaderProgram

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend


# ============================================================
# Shader Sources
# ============================================================

SHADOW_VERT = """
#version 330 core

layout(location = 0) in vec3 a_position;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

void main()
{
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
"""

SHADOW_FRAG = """
#version 330 core

void main()
{
    // Depth-only pass
}
"""

PICK_VERT = """
#version 330 core

layout(location=0) in vec3 a_position;
layout(location=1) in vec3 a_normal;
layout(location=2) in vec2 a_texcoord;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

void main() {
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
"""

PICK_FRAG = """
#version 330 core

uniform vec3 u_pickColor;
out vec4 fragColor;

void main() {
    fragColor = vec4(u_pickColor, 1.0);
}
"""


# ============================================================
# Registry
# ============================================================

class SystemShaderRegistry:
    """
    Registry for system shaders.

    Shaders are created lazily and cached PER CONTEXT.
    Each GL context gets its own compiled shader instances.
    """

    _instance: "SystemShaderRegistry | None" = None

    def __init__(self):
        # Shader definitions: name -> (vert_source, frag_source)
        self._definitions: Dict[str, tuple[str, str]] = {
            "shadow": (SHADOW_VERT, SHADOW_FRAG),
            "pick": (PICK_VERT, PICK_FRAG),
        }

        # Compiled shaders per context: (context_key, name) -> ShaderProgram
        self._shaders: Dict[tuple[int, str], ShaderProgram] = {}

    @classmethod
    def instance(cls) -> "SystemShaderRegistry":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get(self, name: str, graphics: "GraphicsBackend") -> ShaderProgram:
        """
        Get a system shader by name for the current context, compiling if necessary.

        Args:
            name: Shader name ("shadow", "pick", etc.)
            graphics: Graphics backend for compilation

        Returns:
            Compiled ShaderProgram ready for use
        """
        from termin.visualization.platform.backends.opengl import get_current_context_key

        context_key = get_current_context_key()
        if context_key is None:
            context_key = 0  # fallback
        cache_key = (context_key, name)

        if cache_key not in self._shaders:
            if name not in self._definitions:
                raise KeyError(f"Unknown system shader: {name}")

            vert, frag = self._definitions[name]
            shader = ShaderProgram(vert, frag)
            shader.ensure_ready(graphics)
            self._shaders[cache_key] = shader

        return self._shaders[cache_key]

    def register(self, name: str, vert_source: str, frag_source: str) -> None:
        """
        Register a new system shader.

        Args:
            name: Shader name
            vert_source: Vertex shader GLSL source
            frag_source: Fragment shader GLSL source
        """
        self._definitions[name] = (vert_source, frag_source)
        # Clear all cached shaders for this name (will be recompiled on next get)
        keys_to_remove = [k for k in self._shaders if k[1] == name]
        for k in keys_to_remove:
            del self._shaders[k]


def get_system_shader(name: str, graphics: "GraphicsBackend") -> ShaderProgram:
    """
    Convenience function to get a system shader.

    Args:
        name: Shader name ("shadow", "pick", etc.)
        graphics: Graphics backend for compilation

    Returns:
        Compiled ShaderProgram ready for use
    """
    return SystemShaderRegistry.instance().get(name, graphics)
