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
&#9;&quot;&quot;&quot;<br>
&#9;Описание одного поля для инспектора.<br>
<br>
&#9;path      – путь к полю (&quot;enabled&quot;, &quot;material.color&quot; и т.п.)<br>
&#9;label     – подпись в UI<br>
&#9;kind      – тип виджета: 'float', 'int', 'bool', 'vec3', 'color', 'string', 'enum', ...<br>
&#9;min, max  – ограничения<br>
&#9;step      – шаг (для спинбоксов)<br>
&#9;choices   – для enum: список (value, label)<br>
&#9;getter, setter – если нужно обращаться к полю вручную.<br>
&#9;&quot;&quot;&quot;<br>
&#9;path: str | None = None<br>
&#9;label: str | None = None<br>
&#9;kind: str = &quot;float&quot;<br>
&#9;min: float | None = None<br>
&#9;max: float | None = None<br>
&#9;step: float | None = None<br>
&#9;choices: list[tuple[Any, str]] | None = None<br>
&#9;getter: Optional[Callable[[Any], Any]] = None<br>
&#9;setter: Optional[Callable[[Any, Any], None]] = None<br>
<br>
&#9;def get_value(self, obj):<br>
&#9;&#9;if self.getter:<br>
&#9;&#9;&#9;return self.getter(obj)<br>
&#9;&#9;if self.path is None:<br>
&#9;&#9;&#9;raise ValueError(&quot;InspectField: path or getter must be set&quot;)<br>
&#9;&#9;return _resolve_path_get(obj, self.path)<br>
<br>
&#9;def set_value(self, obj, value):<br>
&#9;&#9;if self.setter:<br>
&#9;&#9;&#9;self.setter(obj, value)<br>
&#9;&#9;&#9;return<br>
&#9;&#9;if self.path is None:<br>
&#9;&#9;&#9;raise ValueError(&quot;InspectField: path or setter must be set&quot;)<br>
&#9;&#9;_resolve_path_set(obj, self.path, value)<br>
<br>
<br>
def _resolve_path_get(obj, path: str):<br>
&#9;cur = obj<br>
&#9;for part in path.split(&quot;.&quot;):<br>
&#9;&#9;cur = getattr(cur, part)<br>
&#9;return cur<br>
<br>
<br>
def _resolve_path_set(obj, path: str, value):<br>
&#9;parts = path.split(&quot;.&quot;)<br>
&#9;cur = obj<br>
&#9;for part in parts[:-1]:<br>
&#9;&#9;cur = getattr(cur, part)<br>
&#9;last = parts[-1]<br>
<br>
&#9;# небольшой хак: если там numpy-вектор, обновляем по месту<br>
&#9;try:<br>
&#9;&#9;import numpy as np<br>
&#9;&#9;arr = getattr(cur, last)<br>
&#9;&#9;if isinstance(arr, np.ndarray):<br>
&#9;&#9;&#9;arr[...] = value<br>
&#9;&#9;&#9;return<br>
&#9;except Exception:<br>
&#9;&#9;pass<br>
<br>
&#9;setattr(cur, last, value)<br>
<br>
<br>
class InspectAttr:<br>
&#9;&quot;&quot;&quot;<br>
&#9;Дескриптор: хранит значение на инстансе и регистрирует себя как InspectField<br>
&#9;в классе компонента.<br>
<br>
&#9;Использование:<br>
&#9;&#9;class Foo(Component):<br>
&#9;&#9;&#9;bar = inspect(42, label=&quot;Bar&quot;, kind=&quot;int&quot;)<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(<br>
&#9;&#9;self,<br>
&#9;&#9;default: Any = None,<br>
&#9;&#9;*,<br>
&#9;&#9;label: str | None = None,<br>
&#9;&#9;kind: str = &quot;float&quot;,<br>
&#9;&#9;min: float | None = None,<br>
&#9;&#9;max: float | None = None,<br>
&#9;&#9;step: float | None = None,<br>
&#9;&#9;choices: list[tuple[Any, str]] | None = None,<br>
&#9;&#9;getter: Optional[Callable[[Any], Any]] = None,<br>
&#9;&#9;setter: Optional[Callable[[Any, Any], None]] = None,<br>
&#9;):<br>
&#9;&#9;self.default = default<br>
&#9;&#9;self._field = InspectField(<br>
&#9;&#9;&#9;path=None,      # узнаем позже, в __set_name__<br>
&#9;&#9;&#9;label=label,<br>
&#9;&#9;&#9;kind=kind,<br>
&#9;&#9;&#9;min=min,<br>
&#9;&#9;&#9;max=max,<br>
&#9;&#9;&#9;step=step,<br>
&#9;&#9;&#9;choices=choices,<br>
&#9;&#9;&#9;getter=getter,<br>
&#9;&#9;&#9;setter=setter,<br>
&#9;&#9;)<br>
&#9;&#9;self._name: str | None = None<br>
<br>
&#9;def __set_name__(self, owner, name: str):<br>
&#9;&#9;self._name = name<br>
<br>
&#9;&#9;# если путь не задан — считаем, что поле лежит прямо на компоненте<br>
&#9;&#9;if self._field.path is None:<br>
&#9;&#9;&#9;self._field.path = name<br>
&#9;&#9;# если label не задан – используем имя<br>
&#9;&#9;if self._field.label is None:<br>
&#9;&#9;&#9;self._field.label = name<br>
<br>
&#9;&#9;# регистрируем поле в owner.inspect_fields<br>
&#9;&#9;fields = getattr(owner, &quot;inspect_fields&quot;, None)<br>
&#9;&#9;if fields is None:<br>
&#9;&#9;&#9;fields = {}<br>
&#9;&#9;&#9;setattr(owner, &quot;inspect_fields&quot;, fields)<br>
&#9;&#9;fields[name] = self._field<br>
<br>
&#9;def __get__(self, instance, owner=None):<br>
&#9;&#9;if instance is None:<br>
&#9;&#9;&#9;return self<br>
&#9;&#9;return instance.__dict__.get(self._name, self.default)<br>
<br>
&#9;def __set__(self, instance, value):<br>
&#9;&#9;instance.__dict__[self._name] = value<br>
<br>
<br>
def inspect(default: Any = None, **meta) -&gt; InspectAttr:<br>
&#9;&quot;&quot;&quot;<br>
&#9;Сахар: aaa = inspect(42, label=&quot;AAA&quot;, kind=&quot;int&quot;).<br>
<br>
&#9;meta → параметры для InspectField (label, kind, min, max, step, ...)<br>
&#9;&quot;&quot;&quot;<br>
&#9;return InspectAttr(default, **meta)<br>
<!-- END SCAT CODE -->
</body>
</html>
