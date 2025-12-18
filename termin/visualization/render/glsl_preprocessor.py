"""
GLSL Preprocessor with #include support.

Processes #include directives in GLSL source code by resolving
include names through ResourceManager's glsl registry.

Usage:
    from termin.visualization.render.glsl_preprocessor import preprocess_glsl

    processed_source = preprocess_glsl(source, "my_shader.vert")
"""

from __future__ import annotations

import re
from typing import Set


# Pattern for #include "name" or #include <name>
# Captures the include name without quotes/brackets
_INCLUDE_PATTERN = re.compile(
    r'^\s*#\s*include\s+[<"]([^>"]+)[>"]',
    re.MULTILINE
)


class GlslPreprocessorError(Exception):
    """Error during GLSL preprocessing."""
    pass


def preprocess_glsl(
    source: str,
    source_name: str = "<unknown>",
    included: Set[str] | None = None,
) -> str:
    """
    Preprocess GLSL source, resolving #include directives.

    Looks up include names in ResourceManager.glsl registry.
    Recursively processes includes in included files.
    Detects and reports circular includes.

    Args:
        source: GLSL source code
        source_name: Name of the source file (for error messages)
        included: Set of already included names (for cycle detection)

    Returns:
        Processed GLSL source with includes resolved

    Raises:
        GlslPreprocessorError: If include not found or circular include detected

    Example:
        # In shader:
        #include "shadows"
        #include "lighting"

        # Resolves to content from ResourceManager.glsl.get("shadows") etc.
    """
    if included is None:
        included = set()

    # Find all #include directives
    def replace_include(match: re.Match) -> str:
        include_name = match.group(1)

        # Check for circular include
        if include_name in included:
            raise GlslPreprocessorError(
                f"Circular include detected: '{include_name}' "
                f"(included from '{source_name}')"
            )

        # Get include source from ResourceManager
        from termin.visualization.core.resources import ResourceManager
        rm = ResourceManager.instance()

        include_source = rm.get_glsl(include_name)
        if include_source is None:
            raise GlslPreprocessorError(
                f"GLSL include not found: '{include_name}' "
                f"(included from '{source_name}')\n"
                f"Make sure '{include_name}.glsl' is in your project "
                f"or standard library is deployed."
            )

        # Recursively preprocess the included source
        new_included = included | {include_name}
        processed = preprocess_glsl(
            include_source,
            source_name=include_name,
            included=new_included,
        )

        # Add markers for debugging
        return (
            f"// === BEGIN INCLUDE: {include_name} ===\n"
            f"{processed}\n"
            f"// === END INCLUDE: {include_name} ==="
        )

    # Replace all includes
    result = _INCLUDE_PATTERN.sub(replace_include, source)
    return result


def has_includes(source: str) -> bool:
    """Check if source contains any #include directives."""
    return bool(_INCLUDE_PATTERN.search(source))
