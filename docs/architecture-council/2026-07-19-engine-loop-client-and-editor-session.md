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

## Текущее расхождение

Сейчас `init_editor_native()` возвращает `None`, lifetime редактора удерживается
closures, а teardown вызывается из engine shutdown callback. Native host не
владеет явным объектом editor session. Это скрывает порядок разрушения и
оставляет engine callbacks живыми после окончания главного цикла.

## Предлагаемая последовательность миграции

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

Точные форма connection object, обработка callback exceptions, политика
повторного `close()` и внутренняя декомпозиция `EditorSession` требуют отдельных
инженерных решений при подготовке соответствующих задач.
