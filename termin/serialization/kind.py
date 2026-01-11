"""
Kind serialization system.

Allows registering custom serializers/deserializers for specific field kinds.
Each language (Python, C++, Rust) can register its own handlers independently.

Usage:
    from termin.serialization.kind import register_kind, KindRegistry

    # Register enum handler
    @register_kind("my_enum")
    class MyEnumKind:
        @staticmethod
        def serialize(obj):
            return {"value": obj.value}

        @staticmethod
        def deserialize(data):
            return MyEnum(data["value"])

    # Or register manually
    KindRegistry.instance().register_python(
        "my_handle",
        serialize=lambda obj: obj.to_dict(),
        deserialize=lambda data: MyHandle.from_dict(data),
        convert=None
    )
"""

from termin._native.kind import KindRegistry as _KindRegistry


class KindRegistry:
    """Registry for kind serialization handlers."""

    @staticmethod
    def instance() -> _KindRegistry:
        """Get the singleton instance."""
        return _KindRegistry.instance()

    @staticmethod
    def register_python(
        name: str,
        serialize=None,
        deserialize=None,
        convert=None
    ):
        """Register Python handlers for a kind.

        Args:
            name: Kind name (e.g., "mesh_handle", "my_enum")
            serialize: callable(obj) -> dict
            deserialize: callable(dict) -> obj
            convert: callable(obj) -> obj (optional, for UI value conversion)
        """
        _KindRegistry.instance().register_python(
            name,
            serialize or (lambda x: None),
            deserialize or (lambda x: None),
            convert
        )

    @staticmethod
    def serialize(kind: str, obj):
        """Serialize object using registered handler."""
        return _KindRegistry.instance().serialize(kind, obj)

    @staticmethod
    def deserialize(kind: str, data):
        """Deserialize data using registered handler."""
        return _KindRegistry.instance().deserialize(kind, data)

    @staticmethod
    def convert(kind: str, value):
        """Convert value using registered handler."""
        return _KindRegistry.instance().convert(kind, value)

    @staticmethod
    def kinds():
        """Get all registered kind names."""
        return _KindRegistry.instance().kinds()


def register_kind(name: str):
    """Decorator to register a kind handler class.

    The class should have static methods:
    - serialize(obj) -> dict
    - deserialize(dict) -> obj
    - convert(obj) -> obj (optional)

    Example:
        @register_kind("light_type")
        class LightTypeKind:
            @staticmethod
            def serialize(obj):
                return obj.value  # enum to int

            @staticmethod
            def deserialize(data):
                from termin.lighting import LightType
                return LightType(data)
    """
    def decorator(cls):
        serialize_fn = getattr(cls, 'serialize', None)
        deserialize_fn = getattr(cls, 'deserialize', None)
        convert_fn = getattr(cls, 'convert', None)

        KindRegistry.register_python(
            name,
            serialize=serialize_fn,
            deserialize=deserialize_fn,
            convert=convert_fn
        )
        return cls

    return decorator


__all__ = ["KindRegistry", "register_kind"]


# ============================================================================
# Builtin kind handlers
# ============================================================================

@register_kind("layer_mask")
class LayerMaskKind:
    """Handler for layer_mask kind (64-bit unsigned int as hex string)."""

    @staticmethod
    def serialize(obj):
        # Serialize as hex string to handle values > int64_t max
        return hex(obj)

    @staticmethod
    def deserialize(data):
        if isinstance(data, str):
            return int(data, 16) if data.startswith("0x") else int(data)
        return int(data)


@register_kind("navmesh_handle")
class NavMeshHandleKind:
    """Handler for navmesh_handle kind."""

    @staticmethod
    def serialize(obj):
        from termin.assets.navmesh_handle import NavMeshHandle
        if isinstance(obj, NavMeshHandle):
            return obj.serialize()
        return None

    @staticmethod
    def deserialize(data):
        from termin.assets.navmesh_handle import NavMeshHandle
        if isinstance(data, dict):
            return NavMeshHandle.deserialize(data)
        return NavMeshHandle()
