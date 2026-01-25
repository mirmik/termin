"""
System shaders registry.

Simple shaders used by render passes (pick, etc.)
that don't need material phases.

These are compiled lazily on first use and cached.

Note: Shadow shader is now in C++ (shadow_pass.cpp).
"""

from __future__ import annotations

from typing import Dict

from termin._native.render import TcShader


# ============================================================
# Shader Sources
# ============================================================

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

    Shaders are created lazily and cached.
    """

    _instance: "SystemShaderRegistry | None" = None

    def __init__(self):
        # Shader definitions: name -> (vert_source, frag_source)
        self._definitions: Dict[str, tuple[str, str]] = {
            "pick": (PICK_VERT, PICK_FRAG),
        }

        # Compiled shaders: name -> TcShader
        self._shaders: Dict[str, TcShader] = {}

    @classmethod
    def instance(cls) -> "SystemShaderRegistry":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get(self, name: str) -> TcShader:
        """
        Get a system shader by name, compiling if necessary.

        Args:
            name: Shader name ("pick", etc.)

        Returns:
            TcShader ready for use
        """
        if name not in self._shaders:
            if name not in self._definitions:
                raise KeyError(f"Unknown system shader: {name}")

            vert, frag = self._definitions[name]
            shader = TcShader.from_sources(vert, frag, "", f"system:{name}")
            shader.ensure_ready()
            self._shaders[name] = shader

        return self._shaders[name]

    def register(self, name: str, vert_source: str, frag_source: str) -> None:
        """
        Register a new system shader.

        Args:
            name: Shader name
            vert_source: Vertex shader GLSL source
            frag_source: Fragment shader GLSL source
        """
        self._definitions[name] = (vert_source, frag_source)
        # Clear cached shader for this name (will be recompiled on next get)
        if name in self._shaders:
            del self._shaders[name]


def get_system_shader(name: str) -> TcShader:
    """
    Convenience function to get a system shader.

    Args:
        name: Shader name ("pick", etc.)

    Returns:
        TcShader ready for use
    """
    return SystemShaderRegistry.instance().get(name)
