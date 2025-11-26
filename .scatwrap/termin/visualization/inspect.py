<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/inspect.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
# termin/visualization/inspect.py<br>
<br>
from __future__ import annotations<br>
<br>
from dataclasses import dataclass<br>
from typing import Any, Callable, Optional<br>
<br>
<br>
@dataclass<br>
class InspectField:<br>
    &quot;&quot;&quot;<br>
    Описание одного поля для инспектора.<br>
<br>
    path      – путь к полю (&quot;enabled&quot;, &quot;material.color&quot; и т.п.)<br>
    label     – подпись в UI<br>
    kind      – тип виджета: 'float', 'int', 'bool', 'vec3', 'color', 'string', 'enum', ...<br>
    min, max  – ограничения<br>
    step      – шаг (для спинбоксов)<br>
    choices   – для enum: список (value, label)<br>
    getter, setter – если нужно обращаться к полю вручную.<br>
    &quot;&quot;&quot;<br>
    path: str | None = None<br>
    label: str | None = None<br>
    kind: str = &quot;float&quot;<br>
    min: float | None = None<br>
    max: float | None = None<br>
    step: float | None = None<br>
    choices: list[tuple[Any, str]] | None = None<br>
    getter: Optional[Callable[[Any], Any]] = None<br>
    setter: Optional[Callable[[Any, Any], None]] = None<br>
<br>
    def get_value(self, obj):<br>
        if self.getter:<br>
            return self.getter(obj)<br>
        if self.path is None:<br>
            raise ValueError(&quot;InspectField: path or getter must be set&quot;)<br>
        return _resolve_path_get(obj, self.path)<br>
<br>
    def set_value(self, obj, value):<br>
        if self.setter:<br>
            self.setter(obj, value)<br>
            return<br>
        if self.path is None:<br>
            raise ValueError(&quot;InspectField: path or setter must be set&quot;)<br>
        _resolve_path_set(obj, self.path, value)<br>
<br>
<br>
def _resolve_path_get(obj, path: str):<br>
    cur = obj<br>
    for part in path.split(&quot;.&quot;):<br>
        cur = getattr(cur, part)<br>
    return cur<br>
<br>
<br>
def _resolve_path_set(obj, path: str, value):<br>
    parts = path.split(&quot;.&quot;)<br>
    cur = obj<br>
    for part in parts[:-1]:<br>
        cur = getattr(cur, part)<br>
    last = parts[-1]<br>
<br>
    # небольшой хак: если там numpy-вектор, обновляем по месту<br>
    try:<br>
        import numpy as np<br>
        arr = getattr(cur, last)<br>
        if isinstance(arr, np.ndarray):<br>
            arr[...] = value<br>
            return<br>
    except Exception:<br>
        pass<br>
<br>
    setattr(cur, last, value)<br>
<br>
<br>
class InspectAttr:<br>
    &quot;&quot;&quot;<br>
    Дескриптор: хранит значение на инстансе и регистрирует себя как InspectField<br>
    в классе компонента.<br>
<br>
    Использование:<br>
        class Foo(Component):<br>
            bar = inspect(42, label=&quot;Bar&quot;, kind=&quot;int&quot;)<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(<br>
        self,<br>
        default: Any = None,<br>
        *,<br>
        label: str | None = None,<br>
        kind: str = &quot;float&quot;,<br>
        min: float | None = None,<br>
        max: float | None = None,<br>
        step: float | None = None,<br>
        choices: list[tuple[Any, str]] | None = None,<br>
        getter: Optional[Callable[[Any], Any]] = None,<br>
        setter: Optional[Callable[[Any, Any], None]] = None,<br>
    ):<br>
        self.default = default<br>
        self._field = InspectField(<br>
            path=None,      # узнаем позже, в __set_name__<br>
            label=label,<br>
            kind=kind,<br>
            min=min,<br>
            max=max,<br>
            step=step,<br>
            choices=choices,<br>
            getter=getter,<br>
            setter=setter,<br>
        )<br>
        self._name: str | None = None<br>
<br>
    def __set_name__(self, owner, name: str):<br>
        self._name = name<br>
<br>
        # если путь не задан — считаем, что поле лежит прямо на компоненте<br>
        if self._field.path is None:<br>
            self._field.path = name<br>
        # если label не задан – используем имя<br>
        if self._field.label is None:<br>
            self._field.label = name<br>
<br>
        # регистрируем поле в owner.inspect_fields<br>
        fields = getattr(owner, &quot;inspect_fields&quot;, None)<br>
        if fields is None:<br>
            fields = {}<br>
            setattr(owner, &quot;inspect_fields&quot;, fields)<br>
        fields[name] = self._field<br>
<br>
    def __get__(self, instance, owner=None):<br>
        if instance is None:<br>
            return self<br>
        return instance.__dict__.get(self._name, self.default)<br>
<br>
    def __set__(self, instance, value):<br>
        instance.__dict__[self._name] = value<br>
<br>
<br>
def inspect(default: Any = None, **meta) -&gt; InspectAttr:<br>
    &quot;&quot;&quot;<br>
    Сахар: aaa = inspect(42, label=&quot;AAA&quot;, kind=&quot;int&quot;).<br>
<br>
    meta → параметры для InspectField (label, kind, min, max, step, ...)<br>
    &quot;&quot;&quot;<br>
    return InspectAttr(default, **meta)<br>
<!-- END SCAT CODE -->
</body>
</html>
