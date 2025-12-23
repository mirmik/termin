"""Shader program - re-export from C++."""

# Re-export C++ classes
from termin._native.render import (
    ShaderProgram,
    GlslPreprocessor,
    glsl_preprocessor,
)


class ShaderCompilationError(RuntimeError):
    """Raised when GLSL compilation or program linking fails."""


__all__ = [
    "ShaderProgram",
    "ShaderCompilationError",
    "GlslPreprocessor",
    "glsl_preprocessor",
]
