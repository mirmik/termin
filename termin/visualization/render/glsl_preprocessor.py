"""GLSL Preprocessor - re-export from C++."""

from termin._native import (
    GlslPreprocessor,
    glsl_preprocessor,
)


class GlslPreprocessorError(Exception):
    """Error during GLSL preprocessing."""


def preprocess_glsl(source: str, source_name: str = "<unknown>") -> str:
    """
    Preprocess GLSL source, resolving #include directives.

    Uses the global C++ preprocessor instance.
    Include files must be registered via glsl_preprocessor().register_include().

    Args:
        source: GLSL source code
        source_name: Name for error messages

    Returns:
        Processed source with includes resolved
    """
    return glsl_preprocessor().preprocess(source, source_name)


def has_includes(source: str) -> bool:
    """Check if source contains any #include directives."""
    return GlslPreprocessor.has_includes(source)


__all__ = [
    "GlslPreprocessor",
    "GlslPreprocessorError",
    "glsl_preprocessor",
    "preprocess_glsl",
    "has_includes",
]
