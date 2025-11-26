<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/inspect.py</title>
</head>
<body>
<pre><code>
# termin/visualization/inspect.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class InspectField:
    &quot;&quot;&quot;
    Описание одного поля для инспектора.

    path      – путь к полю (&quot;enabled&quot;, &quot;material.color&quot; и т.п.)
    label     – подпись в UI
    kind      – тип виджета: 'float', 'int', 'bool', 'vec3', 'color', 'string', 'enum', ...
    min, max  – ограничения
    step      – шаг (для спинбоксов)
    choices   – для enum: список (value, label)
    getter, setter – если нужно обращаться к полю вручную.
    &quot;&quot;&quot;
    path: str | None = None
    label: str | None = None
    kind: str = &quot;float&quot;
    min: float | None = None
    max: float | None = None
    step: float | None = None
    choices: list[tuple[Any, str]] | None = None
    getter: Optional[Callable[[Any], Any]] = None
    setter: Optional[Callable[[Any, Any], None]] = None

    def get_value(self, obj):
        if self.getter:
            return self.getter(obj)
        if self.path is None:
            raise ValueError(&quot;InspectField: path or getter must be set&quot;)
        return _resolve_path_get(obj, self.path)

    def set_value(self, obj, value):
        if self.setter:
            self.setter(obj, value)
            return
        if self.path is None:
            raise ValueError(&quot;InspectField: path or setter must be set&quot;)
        _resolve_path_set(obj, self.path, value)


def _resolve_path_get(obj, path: str):
    cur = obj
    for part in path.split(&quot;.&quot;):
        cur = getattr(cur, part)
    return cur


def _resolve_path_set(obj, path: str, value):
    parts = path.split(&quot;.&quot;)
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
    except Exception:
        pass

    setattr(cur, last, value)


class InspectAttr:
    &quot;&quot;&quot;
    Дескриптор: хранит значение на инстансе и регистрирует себя как InspectField
    в классе компонента.

    Использование:
        class Foo(Component):
            bar = inspect(42, label=&quot;Bar&quot;, kind=&quot;int&quot;)
    &quot;&quot;&quot;

    def __init__(
        self,
        default: Any = None,
        *,
        label: str | None = None,
        kind: str = &quot;float&quot;,
        min: float | None = None,
        max: float | None = None,
        step: float | None = None,
        choices: list[tuple[Any, str]] | None = None,
        getter: Optional[Callable[[Any], Any]] = None,
        setter: Optional[Callable[[Any, Any], None]] = None,
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
        fields = getattr(owner, &quot;inspect_fields&quot;, None)
        if fields is None:
            fields = {}
            setattr(owner, &quot;inspect_fields&quot;, fields)
        fields[name] = self._field

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        return instance.__dict__.get(self._name, self.default)

    def __set__(self, instance, value):
        instance.__dict__[self._name] = value


def inspect(default: Any = None, **meta) -&gt; InspectAttr:
    &quot;&quot;&quot;
    Сахар: aaa = inspect(42, label=&quot;AAA&quot;, kind=&quot;int&quot;).

    meta → параметры для InspectField (label, kind, min, max, step, ...)
    &quot;&quot;&quot;
    return InspectAttr(default, **meta)

</code></pre>
</body>
</html>
