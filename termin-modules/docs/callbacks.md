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
  - подготовить runtime к появлению нового модуля, если это нужно

- `after_load`
  - обработать эффекты загрузки модуля
  - при необходимости дочитать появившиеся регистрации типов и компонентов

- `before_unload`
  - выполнить cleanup перед выгрузкой
  - снять связи со сценой и runtime-объектами, если они завязаны на код модуля

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

### Чего Python коллбеки делать не должны

Они не должны:

- вручную импортировать пакеты вместо backend-а
- вручную править dependency graph
- смешивать свою логику с C++ lifecycle

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
