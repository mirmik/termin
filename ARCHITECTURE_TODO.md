# Architecture TODO

Список открытых архитектурных вопросов и направлений на рефакторинг.

## Scene extensions

- [ ] Перенести регистрацию builtin scene extensions на максимально высокий уровень API: из `termin-engine` в `termin`.
  Сейчас `EngineCore` регистрирует `render_mount`, `render_state` и `collision_world`, но это слишком низкий слой для глобальной registration/bootstrap-логики.
  Ожидаемое направление: `termin-engine` должен работать с уже зарегистрированными extension types, а orchestration регистрации должна жить в верхнем слое `termin`, рядом с high-level созданием сцен.

## Dependency graph

- [ ] Автоматизировать генерацию графа зависимостей для документации вместо ручного `docs/library-dependencies.dot`.
  Граф должен покрывать и C/C++ зависимости, и Python-зависимости.
  Сейчас диаграмма поддерживается вручную и может расходиться с реальными зависимостями из `CMakeLists.txt` и Python-пакетов/модулей.
