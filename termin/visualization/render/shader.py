"""Shader program - re-export from C++."""

# Re-export C++ classes
from termin._native.render import (
    TcShader,
    GlslPreprocessor,
    glsl_preprocessor,
)

# DEPRECATED: ShaderProgram is being phased out in favor of TcShader
# Keeping re-export for backwards compatibility during migration
from termin._native.render import ShaderProgram


class ShaderCompilationError(RuntimeError):
    """Raised when GLSL compilation or program linking fails."""


__all__ = [
    "TcShader",
    "ShaderProgram",  # DEPRECATED
    "ShaderCompilationError",
    "GlslPreprocessor",
    "glsl_preprocessor",
]
