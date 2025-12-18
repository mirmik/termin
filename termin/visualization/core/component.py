"""Base Component class for entity components (Unity-like architecture)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Optional

if TYPE_CHECKING:
    from termin.visualization.core.entity import Entity
    from termin.visualization.core.scene import Scene
    from termin.visualization.render.render_context import RenderContext
    from termin.visualization.render.shader import ShaderProgram

from termin.editor.inspect_field import InspectField


class Component:
    """
    Base class for all entity components.

    IMPORTANT: Do NOT override serialize_data() or deserialize() methods!
    Serialization is handled automatically via inspect_fields.
    Define inspect_fields in your component class to control serialization.
    """

    # Если None → компонент не сериализуется
    serializable_fields = None

    # Поля, которые инспектор может редактировать.
    # Заполняется либо руками, либо через дескриптор InspectAttr.
    inspect_fields: dict[str, InspectField] = {
        "enabled": InspectField(
            path="enabled",
            label="Enabled",
            kind="bool",
        ),
    }

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Базовый класс сам себя не регистрирует
        if cls is Component:
            return
        from termin.visualization.core.resources import ResourceManager

        manager = ResourceManager.instance()
        manager.register_component(cls.__name__, cls)

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.entity: Optional["Entity"] = None
        self._started = False

    def required_shaders(self) -> Iterable["ShaderProgram"]:
        """Return shaders that must be compiled before rendering."""
        return ()

    def on_added(self, scene: "Scene"):
        """Called immediately when the component is added to an active scene."""
        pass

    def start(self, scene: "Scene"):
        """Called once before the first update, after all components are added."""
        self._started = True

    def update(self, dt: float):
        """Called every frame."""
        return

    def draw(self, context: RenderContext):
        """Issue draw calls."""
        return

    def on_removed(self):
        """Called when component is removed from its entity."""
        return

    def on_editor_start(self):
        """Called when scene starts in editor mode."""
        return

    def serialize_data(self):
        fields = self.serializable_fields

        # Собираем inspect_fields из всей иерархии классов
        inspect_fields = {}
        for klass in reversed(type(self).__mro__):
            if hasattr(klass, 'inspect_fields') and klass.inspect_fields:
                inspect_fields.update(klass.inspect_fields)

        if fields is None and not inspect_fields:
            return None

        result = {}
        if isinstance(fields, dict):
            for key, typ in fields.items():
                value = getattr(self, key)
                result[key] = typ.serialize(value) if typ else value
        elif fields is not None:
            for key in fields:
                result[key] = getattr(self, key)

        if inspect_fields:
            for name, field in inspect_fields.items():
                if field.non_serializable:
                    continue
                key = field.path if field.path is not None else name
                if key in result:
                    continue

                value = field.get_value(self)
                kind = field.kind

                # Конвертация ресурсов в uuid (с fallback на имя для совместимости)
                if kind in ("mesh", "material", "voxel_grid", "navmesh", "skeleton"):
                    if value is not None:
                        from termin.visualization.core.resources import ResourceManager
                        rm = ResourceManager.instance()

                        uuid = None
                        if kind == "material":
                            uuid = rm.find_material_uuid(value)
                        elif kind == "mesh":
                            uuid = rm.find_mesh_uuid(value)
                        elif kind == "voxel_grid":
                            uuid = rm.find_voxel_grid_uuid(value)
                        elif kind == "navmesh":
                            uuid = rm.find_navmesh_uuid(value)
                        elif kind == "skeleton":
                            uuid = rm.find_skeleton_uuid(value)

                        if uuid:
                            value = {"uuid": uuid}
                        elif hasattr(value, "name") and value.name:
                            # Fallback to name if no uuid found
                            value = value.name
                        else:
                            value = None
                    else:
                        value = None
                # Конвертация tuple/list для JSON
                elif kind in ("color", "vec3", "vec4") and isinstance(value, (tuple, list)):
                    value = list(value)
                elif kind == "vec3_list" and isinstance(value, (tuple, list)):
                    value = [list(v) for v in value]
                # entity_list: List[EntityHandle] → list of UUID strings
                elif kind == "entity_list" and isinstance(value, (tuple, list)):
                    from termin.visualization.core.entity_handle import EntityHandle
                    uuids = []
                    for item in value:
                        if isinstance(item, EntityHandle):
                            uuids.append(item.uuid)
                        elif isinstance(item, str):
                            uuids.append(item)
                    value = uuids
                # animation_clip_list: List[AnimationClipHandle] → list of UUIDs
                elif kind == "animation_clip_list" and isinstance(value, (tuple, list)):
                    from termin.visualization.core.animation_clip_handle import AnimationClipHandle
                    uuids = []
                    for item in value:
                        if isinstance(item, AnimationClipHandle):
                            asset = item.asset
                            if asset is not None:
                                uuids.append(asset.uuid)
                        elif isinstance(item, str):
                            uuids.append(item)
                    value = uuids

                if value is not None:
                    result[key] = value

        return result

    def serialize(self):
        data = self.serialize_data()
        return {
            "data": data,
            "type": self.__class__.__name__,
        }

    @classmethod
    def deserialize(cls, data, context):
        from termin.visualization.core.resources import ResourceManager

        obj = cls.__new__(cls)
        cls.__init__(obj)

        # Восстанавливаем поля из serializable_fields
        fields = cls.serializable_fields
        if fields is None:
            pass  # Нет полей для десериализации
        elif isinstance(fields, dict):
            for key, typ in fields.items():
                if key not in data:
                    continue
                value = data[key]
                setattr(obj, key, typ.deserialize(value, context) if typ else value)
        else:
            for key in fields:
                if key in data:
                    setattr(obj, key, data[key])

        # Восстанавливаем поля из inspect_fields (включая базовые)
        inspect_fields = {}
        for klass in reversed(cls.__mro__):
            if hasattr(klass, 'inspect_fields') and klass.inspect_fields:
                inspect_fields.update(klass.inspect_fields)
        if inspect_fields:
            rm = ResourceManager.instance()
            for name, field in inspect_fields.items():
                if field.non_serializable:
                    continue
                key = field.path if field.path is not None else name
                if key not in data:
                    continue

                value = data[key]
                kind = field.kind

                # Конвертация типов и загрузка ресурсов
                if kind == "mesh":
                    resource = None
                    if isinstance(value, dict) and "uuid" in value:
                        resource = rm.get_mesh_by_uuid(value["uuid"])
                    elif isinstance(value, str):
                        resource = rm.get_mesh(value)
                    if resource is not None and field.setter:
                        field.setter(obj, resource)
                    continue
                elif kind == "material":
                    resource = None
                    if isinstance(value, dict) and "uuid" in value:
                        resource = rm.get_material_by_uuid(value["uuid"])
                    elif isinstance(value, str):
                        resource = rm.get_material(value)
                    if resource is not None and field.setter:
                        field.setter(obj, resource)
                    continue
                elif kind == "voxel_grid":
                    resource = None
                    if isinstance(value, dict) and "uuid" in value:
                        resource = rm.get_voxel_grid_by_uuid(value["uuid"])
                    elif isinstance(value, str):
                        resource = rm.get_voxel_grid(value)
                    if resource is not None and field.setter:
                        field.setter(obj, resource)
                    continue
                elif kind == "navmesh":
                    resource = None
                    if isinstance(value, dict) and "uuid" in value:
                        resource = rm.get_navmesh_by_uuid(value["uuid"])
                    elif isinstance(value, str):
                        resource = rm.get_navmesh(value)
                    if resource is not None and field.setter:
                        field.setter(obj, resource)
                    continue
                elif kind == "skeleton":
                    resource = None
                    skeleton_uuid = None
                    if isinstance(value, dict) and "uuid" in value:
                        skeleton_uuid = value["uuid"]
                        resource = rm.get_skeleton_by_uuid(skeleton_uuid)
                    elif isinstance(value, str):
                        resource = rm.get_skeleton(value)
                    if resource is not None and field.setter:
                        field.setter(obj, resource)
                    elif skeleton_uuid is not None:
                        # Store pending UUID for lazy resolution
                        obj._pending_skeleton_uuid = skeleton_uuid
                    continue
                elif kind in ("color", "vec3", "vec4") and isinstance(value, list):
                    value = tuple(value)
                elif kind == "vec3_list" and isinstance(value, list):
                    value = [tuple(v) for v in value]
                elif kind == "entity_list" and isinstance(value, list):
                    # Convert list of UUID strings to List[EntityHandle]
                    from termin.visualization.core.entity_handle import EntityHandle
                    value = [EntityHandle(uuid=uuid_str) for uuid_str in value]
                elif kind == "animation_clip_list" and isinstance(value, list):
                    # Convert list of UUIDs to List[AnimationClipHandle]
                    # Keep all handles - they will resolve lazily when clip is available
                    from termin.visualization.core.animation_clip_handle import AnimationClipHandle
                    value = [AnimationClipHandle.from_uuid(clip_uuid) for clip_uuid in value]

                # Устанавливаем значение через setter или напрямую
                if field.setter:
                    field.setter(obj, value)
                elif field.path:
                    setattr(obj, field.path, value)

        return obj


class InputComponent(Component):
    """Component capable of handling input events."""

    def on_mouse_button(self, viewport, button: int, action: int, mods: int):
        return

    def on_mouse_move(self, viewport, x: float, y: float, dx: float, dy: float):
        return

    def on_scroll(self, viewport, xoffset: float, yoffset: float):
        return

    def on_key(self, viewport, key: int, scancode: int, action: int, mods: int):
        return
