"""GLSL Preprocessor - re-export from C++."""

from termin._native.render import (
    GlslPreprocessor,
    glsl_preprocessor,
    register_glsl_preprocessor,
)


class GlslPreprocessorError(Exception):
    """Error during GLSL preprocessing."""


def _glsl_fallback_loader(name: str) -> bool:
    """Load GLSL include from ResourceManager if not already registered."""
    from tcbase import log
    from termin.assets.resources import ResourceManager

    try:
        rm = ResourceManager.instance()
        asset = rm.glsl.get_asset(name)
        if asset is None:
            log.error(f"[GlslPreprocessor] Fallback: glsl '{name}' not found in ResourceManager")
            return False

        asset.ensure_loaded()
        return glsl_preprocessor().has_include(name)
    except Exception as e:
        log.error(f"[GlslPreprocessor] Fallback loader error for GLSL include '{name}': {e}")
        return False


# Set up fallback loader on module import
glsl_preprocessor().set_fallback_loader(_glsl_fallback_loader)

# Register the preprocessor with the C shader compilation system
# This allows tc_shader_compile_gpu to preprocess #include directives
register_glsl_preprocessor()


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
