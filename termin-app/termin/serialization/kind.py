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
        deserialize=lambda data: MyHandle.from_dict(data)
    )
"""

from termin.inspect.kind import KindRegistry, register_kind


__all__ = ["KindRegistry", "register_kind"]


# ============================================================================
# Builtin kind handlers
# ============================================================================

@register_kind("navmesh_handle")
class NavMeshHandleKind:
    """Handler for navmesh_handle kind.

    The kind name is legacy scene schema; the runtime value is TcNavMesh.
    """

    @staticmethod
    def serialize(obj):
        from termin.navmesh._navmesh_native import TcNavMesh
        if isinstance(obj, TcNavMesh):
            return obj.serialize()
        return None

    @staticmethod
    def deserialize(data):
        from termin.navmesh._navmesh_native import TcNavMesh
        if isinstance(data, dict):
            return TcNavMesh.deserialize(data)
        return TcNavMesh()
