# Коллбеки

`termin-modules` не должен знать про внутреннюю модель движка `termin`:

- сцены
- сущности
- экземпляры компонентов
- `UnknownComponent`
- `ComponentRegistry`
- `InspectRegistry`

Всё, что связано с интеграцией в runtime движка, должно жить в callback-ах.

## Зачем они нужны

Коллбеки нужны для двух вещей:

1. Встроить `ModuleRuntime` в конкретный движок или приложение
2. Описать backend-specific логику reload, не зашивая её в `termin-modules`

Сейчас callback-таблицы разделены по типам модулей:

- `CppModuleCallbacks`
- `PythonModuleCallbacks`

Это сделано намеренно: логика для C++ и Python модулей может быть разной.

## Что должны делать C++ коллбеки

Для C++ модуля callback-и должны заниматься интеграцией с C++ runtime движка.

Типичный смысл такой:

- `before_load`
  - подготовить runtime к появлению нового модуля
  - не должен включать owner scope для C++ registrations: на этом этапе C++
    backend ещё может выполнять `dlopen` и запускать static constructors

- `after_load`
  - обработать эффекты загрузки модуля
  - при необходимости дочитать появившиеся регистрации типов и компонентов

- `before_native_init`
  - вызывается C++ backend-ом непосредственно перед ABI v1 `descriptor.init`
  - в `termin-engine` включает owner scope для явных module-owned C++
    registrations

- `after_native_init`
  - вызывается C++ backend-ом сразу после `descriptor.init`
  - в `termin-engine` выключает owner scope
  - вызывается и при ошибке/запрещённом исключении из `descriptor.init`, если `before_native_init`
    уже успел начаться

- `before_unload`
  - выполнить cleanup перед выгрузкой
  - снять связи со сценой и runtime-объектами, если они завязаны на код модуля
  - в `termin-engine` деградирует live scene components в `UnknownComponent`

- `before_native_close`
  - вызывается только для staged C++ unload после успешного `descriptor.shutdown`, но до
    `dlclose`/`FreeLibrary`
  - должен удалить все module-owned `InspectRegistry`/`ComponentRegistry`
    registrations, чтобы не осталось callbacks/factory pointers в выгружаемый код
  - если возвращает ошибку, backend handle не закрывается, а модуль остаётся в
    fail-safe состоянии для повторной попытки cleanup

- `after_unload`
  - завершить cleanup после фактической выгрузки shared library

- `capture_reload_state`
  - собрать состояние, которое нужно пережить reload
  - например, найти все существующие экземпляры компонентов данного модуля
  - сериализовать их в opaque state object

- `restore_reload_state`
  - после повторной загрузки восстановить ранее сохранённое состояние
  - заново создать нужные экземпляры
  - перенести в них сериализованные данные

- `after_reload`
  - сделать пост-обработку после успешного восстановления

- `after_failed_load`
  - залогировать ошибку
  - пометить модуль как broken на уровне UI/runtime
  - выключить owner scope, если load упал

### Чего C++ коллбеки делать не должны

Они не должны:

- подменять backend и сами делать `dlopen`
- решать, как строится dependency graph
- напрямую вмешиваться в таблицу модулей `ModuleRuntime`
- реализовывать build system вместо `build.command`

Их задача только в интеграции runtime-логики движка.

## Что должны делать Python коллбеки

Для Python модулей логика обычно легче, но тоже может быть своей.

Типичный смысл:

- `before_load`
  - подготовить Python runtime state, если это нужно

- `after_load`
  - обработать эффекты импорта модулей
  - зарегистрировать Python-side handlers, registries, factories

- `before_unload`
  - снять runtime-ссылки на Python objects, если они мешают reload

- `before_module_remove`
  - fallible prepare-фаза перед изменением registries, `sys.modules` и `sys.path`
  - возвращает `false` и диагностическое сообщение, если хотя бы один live
    object/type нельзя безопасно подготовить
  - при отказе backend unload не вызывается, handle и loaded state сохраняются

- `after_unload`
  - завершить cleanup после удаления модулей из `sys.modules`

- `capture_reload_state`
  - сохранить Python-specific runtime state, если проекту это нужно

- `restore_reload_state`
  - восстановить Python-specific state после повторного импорта

- `after_reload`
  - пост-обработка после успешного reload

- `after_failed_load`
  - логирование и UI-диагностика

В интеграции `termin-engine` Python callbacks используются так же, как C++
callbacks для scene component migration: перед unload module-owned components
деградируют в `UnknownComponent`, после load/reload выполняется upgrade по
типам, которыми владеет модуль в runtime `ComponentRegistry`.

### Чего Python коллбеки делать не должны

Они не должны:

- вручную импортировать пакеты вместо backend-а
- вручную править dependency graph
- смешивать свою логику с C++ lifecycle

## Dependency-aware reload

`ModuleRuntime` сам отвечает за dependency graph. Если нужно перезагрузить
модуль вместе с уже загруженными dependents, хост должен вызывать
`reload_module_with_dependents(...)`, а не пытаться повторить graph traversal в
callbacks или UI-слое.

Для каждого affected-модуля runtime вызывает обычную lifecycle-цепочку:

- `capture_reload_state`
- `before_unload`
- backend unload
- `after_unload`
- `before_load`
- backend load
- `after_load`
- `restore_reload_state`
- `after_reload`

Порядок между модулями остаётся обязанностью runtime: unload идёт от dependents
к dependencies, load идёт от dependencies к dependents.

## Какой объект состояния передавать

Для reload используется opaque object:

- `IModuleReloadState`

Смысл в том, что `termin-modules` не знает формат этого состояния.

Это позволяет:

- для C++ модулей хранить сериализованные компоненты
- для Python модулей хранить Python-side runtime snapshot
- не тащить engine-specific типы в `termin-modules`

## Рекомендуемая граница ответственности

`termin-modules` отвечает за:

- discover
- dependency order
- lifecycle orchestration
- вызов backend-а
- вызов callback-ов в правильные моменты

Интеграционный слой движка отвечает за:

- сериализацию состояния
- cleanup runtime-объектов
- восстановление экземпляров после reload
- интеграцию с registries, scene и UI
