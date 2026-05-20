# Architecture TODO

Список открытых архитектурных вопросов и направлений на рефакторинг.

## Scene extensions

- [ ] Перенести регистрацию builtin scene extensions на максимально высокий уровень API: из `termin-engine` в `termin`.
  Сейчас `EngineCore` регистрирует `render_mount`, `render_state` и `collision_world`, но это слишком низкий слой для глобальной registration/bootstrap-логики.
  Ожидаемое направление: `termin-engine` должен работать с уже зарегистрированными extension types, а orchestration регистрации должна жить в верхнем слое `termin`, рядом с high-level созданием сцен.
