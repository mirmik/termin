"""
Shader variant registry - caches compiled shader variants by source hash.

Allows different components to request the same shader variant without
recompiling it. For example, multiple SkinnedMeshRenderers can share
the same skinned variant of a shadow shader.

Usage:
    from termin.visualization.render.shader_variants import (
        ShaderVariantRegistry,
        ShaderVariantOp,
        get_variant_registry,
    )

    registry = get_variant_registry()
    skinned_shader = registry.get_variant(original_shader, ShaderVariantOp.SKINNING)
"""

from __future__ import annotations

import hashlib
from enum import Enum, auto
from typing import Callable, Dict, Tuple

from termin.visualization.render.shader import ShaderProgram


class ShaderVariantOp(Enum):
    """Types of shader variant operations."""

    SKINNING = auto()  # Add skeletal animation support
    LINE_RIBBON = auto()  # Convert lines to screen-space ribbons via geometry shader


# Type alias for variant transform functions
# Takes original shader, returns transformed shader
VariantTransformFunc = Callable[[ShaderProgram], ShaderProgram]


def compute_shader_hash(shader: ShaderProgram) -> str:
    """
    Compute a stable hash from shader source code.

    Combines vertex, fragment, and geometry sources into a single hash.
    """
    hasher = hashlib.sha256()
    hasher.update(shader.vertex_source.encode('utf-8'))
    hasher.update(b'\x00')  # Separator
    hasher.update(shader.fragment_source.encode('utf-8'))
    if shader.geometry_source:
        hasher.update(b'\x00')
        hasher.update(shader.geometry_source.encode('utf-8'))
    return hasher.hexdigest()[:16]  # 16 hex chars = 64 bits, enough for uniqueness


class ShaderVariantRegistry:
    """
    Registry for caching shader variants by source hash.

    Maps (source_hash, operation) -> compiled ShaderProgram.

    This allows multiple components to share the same shader variant
    without recompiling. For example, if two SkinnedMeshRenderers
    both need a skinned version of the shadow shader, only one
    compilation happens.
    """

    def __init__(self):
        # Map (hash, op) -> ShaderProgram
        self._cache: Dict[Tuple[str, ShaderVariantOp], ShaderProgram] = {}

        # Map op -> transform function
        self._transforms: Dict[ShaderVariantOp, VariantTransformFunc] = {}

    def register_transform(
        self,
        op: ShaderVariantOp,
        transform: VariantTransformFunc,
    ) -> None:
        """
        Register a transform function for a variant operation.

        Args:
            op: The variant operation type
            transform: Function that takes a shader and returns transformed shader
        """
        self._transforms[op] = transform

    def get_variant(
        self,
        shader: ShaderProgram,
        op: ShaderVariantOp,
    ) -> ShaderProgram:
        """
        Get or create a shader variant.

        If the variant already exists in cache, returns cached version.
        Otherwise, applies the transform and caches the result.

        Args:
            shader: Original shader program
            op: Variant operation to apply

        Returns:
            Transformed shader program

        Raises:
            ValueError: If no transform is registered for the operation
        """
        # Compute hash of original shader
        source_hash = compute_shader_hash(shader)
        cache_key = (source_hash, op)

        # Check cache
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Get transform function
        transform = self._transforms.get(op)
        if transform is None:
            raise ValueError(f"No transform registered for operation: {op}")

        # Apply transform and cache
        variant = transform(shader)
        self._cache[cache_key] = variant

        return variant

    def has_variant(
        self,
        shader: ShaderProgram,
        op: ShaderVariantOp,
    ) -> bool:
        """Check if a variant exists in cache without creating it."""
        source_hash = compute_shader_hash(shader)
        return (source_hash, op) in self._cache

    def clear(self) -> None:
        """Clear all cached variants."""
        self._cache.clear()

    def clear_operation(self, op: ShaderVariantOp) -> None:
        """Clear cached variants for a specific operation."""
        keys_to_remove = [k for k in self._cache if k[1] == op]
        for key in keys_to_remove:
            del self._cache[key]

    @property
    def cache_size(self) -> int:
        """Number of cached variants."""
        return len(self._cache)


# Global singleton registry
_global_registry: ShaderVariantRegistry | None = None


def get_variant_registry() -> ShaderVariantRegistry:
    """Get the global shader variant registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = ShaderVariantRegistry()
        _register_default_transforms(_global_registry)
    return _global_registry


def _register_default_transforms(registry: ShaderVariantRegistry) -> None:
    """Register default variant transforms."""
    # Import here to avoid circular imports
    from termin.visualization.render.shader_skinning import (
        inject_skinning_into_vertex_shader,
    )
    from termin.visualization.render.shader_line_ribbon import (
        inject_line_ribbon_geometry_shader,
    )

    def skinning_transform(shader: ShaderProgram) -> ShaderProgram:
        """Transform shader to add skinning support."""
        skinned_vert = inject_skinning_into_vertex_shader(shader.vertex_source)
        return ShaderProgram(
            vertex_source=skinned_vert,
            fragment_source=shader.fragment_source,
            geometry_source=shader.geometry_source,
            source_path=f"{shader.source_path}:skinned" if shader.source_path else "",
        )

    def line_ribbon_transform(shader: ShaderProgram) -> ShaderProgram:
        """Transform shader to add line ribbon geometry shader."""
        return inject_line_ribbon_geometry_shader(shader)

    registry.register_transform(ShaderVariantOp.SKINNING, skinning_transform)
    registry.register_transform(ShaderVariantOp.LINE_RIBBON, line_ribbon_transform)


def clear_variant_cache() -> None:
    """Clear all cached shader variants. Call when shaders are reloaded."""
    global _global_registry
    if _global_registry is not None:
        _global_registry.clear()
