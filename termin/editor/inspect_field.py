# termin/visualization/inspect.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from termin._native import log


@dataclass
class InspectField:
    """
    Описание одного поля для инспектора.

    path      – путь к полю ("enabled", "material.color" и т.п.)
    label     – подпись в UI
    kind      – тип виджета: 'float', 'int', 'bool', 'vec3', 'color', 'string', 'enum', 'button', ...
    min, max  – ограничения
    step      – шаг (для спинбоксов)
    choices   – для enum: список (value, label)
    getter, setter – если нужно обращаться к полю вручную.
    non_serializable – при True поле не попадает в сохранённые данные
    action    – для kind='button': callable, вызывается при нажатии (принимает объект)
    read_only – виджет будет только для чтения
    """
    path: str | None = None
    label: str | None = None
    kind: str = "float"
    min: float | None = None
    max: float | None = None
    step: float | None = None
    choices: list[tuple[Any, str]] | None = None
    getter: Optional[Callable[[Any], Any]] = None
    setter: Optional[Callable[[Any, Any], None]] = None
    non_serializable: bool = False
    action: Optional[Callable[[Any], None]] = None
    read_only: bool = False

    def get_value(self, obj):
        if self.getter:
            return self.getter(obj)
        if self.path is None:
            raise ValueError("InspectField: path or getter must be set")
        return _resolve_path_get(obj, self.path)

    def set_value(self, obj, value):
        if self.setter:
            self.setter(obj, value)
            return
        if self.path is None:
            raise ValueError("InspectField: path or setter must be set")
        _resolve_path_set(obj, self.path, value)


def _resolve_path_get(obj, path: str):
    cur = obj
    for part in path.split("."):
        cur = getattr(cur, part)
    return cur


def _resolve_path_set(obj, path: str, value):
    parts = path.split(".")
    cur = obj
    for part in parts[:-1]:
        cur = getattr(cur, part)
    last = parts[-1]

    # небольшой хак: если там numpy-вектор, обновляем по месту
    try:
        import numpy as np
        arr = getattr(cur, last)
        if isinstance(arr, np.ndarray):
            arr[...] = value
            return
    except Exception as e:
        log.debug(f"[InspectField] numpy in-place update failed for '{path}': {e}")

    setattr(cur, last, value)


class InspectAttr:
    """
    Дескриптор: хранит значение на инстансе и регистрирует себя как InspectField
    в классе компонента.

    Использование:
        class Foo(Component):
            bar = inspect(42, label="Bar", kind="int")
    """

    def __init__(
        self,
        default: Any = None,
        *,
        label: str | None = None,
        kind: str = "float",
        min: float | None = None,
        max: float | None = None,
        step: float | None = None,
        choices: list[tuple[Any, str]] | None = None,
        getter: Optional[Callable[[Any], Any]] = None,
        setter: Optional[Callable[[Any, Any], None]] = None,
        non_serializable: bool = False,
        action: Optional[Callable[[Any], None]] = None,
        read_only: bool = False,
    ):
        self.default = default
        self._field = InspectField(
            path=None,      # узнаем позже, в __set_name__
            label=label,
            kind=kind,
            min=min,
            max=max,
            step=step,
            choices=choices,
            getter=getter,
            setter=setter,
            non_serializable=non_serializable,
            action=action,
            read_only=read_only,
        )
        self._name: str | None = None

    def __set_name__(self, owner, name: str):
        self._name = name

        # если путь не задан — считаем, что поле лежит прямо на компоненте
        if self._field.path is None:
            self._field.path = name
        # если label не задан – используем имя
        if self._field.label is None:
            self._field.label = name

        # регистрируем поле в owner.inspect_fields
        # Важно: проверяем, что dict принадлежит именно этому классу, а не унаследован
        if "inspect_fields" not in owner.__dict__:
            fields = {}
            setattr(owner, "inspect_fields", fields)
        else:
            fields = owner.__dict__["inspect_fields"]
        fields[name] = self._field

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        return instance.__dict__.get(self._name, self.default)

    def __set__(self, instance, value):
        instance.__dict__[self._name] = value


def inspect(default: Any = None, **meta) -> InspectAttr:
    """
    Сахар: aaa = inspect(42, label="AAA", kind="int").

    meta → параметры для InspectField (label, kind, min, max, step, non_serializable, ...)
    """
    return InspectAttr(default, **meta)
