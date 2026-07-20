# Engine Loop Client and Editor Session

## Решение

`EngineCore` является самостоятельным runtime и не знает о существовании
редактора. Редактор подключается к уже созданному `EngineCore` как внешний
клиент.

Подключение оформляется одним атомарным объектом вместо независимой установки
`poll_events`, `should_continue` и `on_shutdown` callbacks. Нельзя наблюдать
состояние, в котором установлена только часть editor integration.

Владение выглядит так:

```text
application composition root
├── owns EngineCore
└── owns EditorSession
    └── connects to EngineCore
```

Composition root задаёт порядок жизни обоих объектов. `EditorSession` не
владеет `EngineCore`, а `EngineCore` не инициирует teardown редактора.
Завершение `EngineCore::run()` и закрытие editor session являются разными
событиями.

Редактор при отключении освобождает только свои объекты и снимает свои
подключения. В частности, editor shutdown не должен уничтожать принадлежащий
`EngineCore` `RenderingManager`.

## Реализованный lifecycle

`init_editor_native()` и `init_editor_tcgui()` возвращают явный
`EditorSession`. Native host удерживает его рядом с `EngineCore` и после выхода
из loop выполняет три отдельные фазы:

1. `EditorSession.prepare_engine_shutdown()` отключает loop client и освобождает
   frontend-интеграции с engine;
2. `EngineCore.shutdown()` освобождает принадлежащие engine сцены и rendering;
3. `EditorSession.close()` уничтожает принадлежащие frontend окно, backend и
   графическое устройство.

Такой порядок существенен, когда `RenderEngine` заимствует устройство у
frontend: все engine-owned потребители уничтожаются раньше владельца
устройства. При этом session по-прежнему не уничтожает `RenderingManager` и не
владеет `EngineCore`; последовательностью управляет composition root.

## Выполненная последовательность миграции

Это рабочая декомпозиция, а не часть принятого API-контракта:

1. Ввести в `termin-engine` атомарный, editor-neutral объект подключения loop
   client и покрыть attach/detach тестами.
2. Перевести на него native player, чтобы проверить контракт на чистом C++
   клиенте.
3. Добавить Python binding атомарного подключения.
4. Сделать инициализацию редактора возвращающей явный `EditorSession`, который
   native host удерживает до конца `EngineCore::run()` и затем закрывает.
5. Перенести long-lived объекты и teardown из closures в `EditorSession`, после
   чего удалить старые независимые callback setters.

Connection и обе session-фазы идемпотентны. `close()` до
`prepare_engine_shutdown()` является ошибкой контракта, чтобы backend нельзя
было случайно уничтожить раньше engine-owned rendering resources.
