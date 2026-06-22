# Жизненный цикл

Ниже описан текущий жизненный цикл модуля в `termin-modules`.

## 1. discover

`ModuleRuntime::discover(project_root)` рекурсивно обходит дерево проекта и ищет:

- `*.module`
- `*.pymodule`

Для каждого файла:

- дескриптор парсится через `ModuleDescriptorParser`
- создаётся `ModuleSpec`
- в runtime добавляется `ModuleRecord` со статусом `Discovered`

Во время поиска пропускаются служебные директории:

- `build`
- `dist`
- `__pycache__`
- скрытые директории

Хост-приложение может дополнительно передать корни, исключаемые из discovery,
через `ModuleRuntime::set_discovery_ignored_roots(...)`. В editor/player туда
попадают проектные `ignored_resource_paths`, `.termin` и `build_output_dir`.

## 2. построение порядка загрузки

Перед `load_all()` runtime строит порядок загрузки по `dependencies`.

Сейчас используется обычная topological sort:

- если зависимость отсутствует, загрузка завершается ошибкой
- если найден цикл, загрузка завершается ошибкой
- модуль грузится только после всех своих зависимостей

## 3. load

`ModuleRuntime::load_module(name)` делает следующее:

1. находит `ModuleRecord`
2. проверяет, что все зависимости уже загружены
3. выбирает backend по `ModuleKind`
4. вызывает integration hook `before_load`
5. вызывает backend `load(...)`
6. переводит модуль в `Loaded` или `Failed`
7. публикует событие

## 4. load для C++ модуля

`CppModuleBackend`:

1. читает `CppModuleConfig`
2. если указан `build.command`, запускает сборку в директории дескриптора
3. проверяет наличие `build.output`
4. загружает shared library через `dlopen` или `LoadLibrary`
5. ищет символ `module_init`
6. если символ найден, вызывает его
7. сохраняет native handle в `CppModuleHandle`

Важно:

- глобальные статические конструкторы shared library вызываются загрузчиком ОС при `dlopen`/`LoadLibrary`
- `module_init` это дополнительная явная точка входа поверх static initialization

## 5. load для Python модуля

`PythonModuleBackend`:

1. инициализирует embedded Python, если он ещё не поднят
2. добавляет `root` в `sys.path`
3. импортирует все пакеты из `packages`
4. сохраняет список импортированных модулей и добавленных путей в `PythonModuleHandle`

## 6. unload

`ModuleRuntime::unload_module(name)`:

1. проверяет, что модуль находится в состоянии `Loaded`
2. вызывает integration hook `before_unload`
3. вызывает backend `unload(...)`
4. очищает `handle`
5. переводит модуль в `Unloaded`
6. публикует событие

Для C++:

- если найден `module_shutdown`, он вызывается
- затем shared library выгружается

Для Python:

- импортированный package subtree удаляется из `sys.modules`
- добавленные пути удаляются из `sys.path`
- регистрации, выполненные под module import context, снимаются по `module_id`

Python backend включает `termin_modules.module_context` на время импорта
пакетов из `.pymodule`. Компоненты, inspect-типы, Python kind handlers и
editor-side class registries, которые умеют читать этот context, помечают
регистрации владельцем модуля. При unload backend сначала вызывает owner
cleanup, затем удаляет package subtree из `sys.modules`.

## 7. reload

`ModuleRuntime::reload_module(name)` сейчас реализован как orchestration-операция:

1. публикуется событие `Reloading`
2. если модуль был загружен, выполняется `unload_module(name)`
3. затем выполняется `load_module(name)`
4. после успешной перезагрузки вызывается integration hook `after_reload`

То есть сейчас у backend-ов нет отдельного специализированного `reload`; runtime собирает его из `unload + load`.

Если восстановление state после reload падает, runtime переводит модуль в
`Failed` и публикует `Failed` event. Старую версию модуля runtime не пытается
автоматически оживлять; scene state должен оставаться в безопасном degraded
состоянии (`UnknownComponent`) до следующего успешного reload или ручного
восстановления.

В editor auto-reload сейчас подключен для Python `.pymodule`: изменение
дескриптора вызывает load/reload descriptor, а изменение `.py` файла внутри
пакета из `packages` перезагружает владеющий Python-модуль. Loose `.py` файлы
вне `.pymodule` продолжают обрабатываться legacy component scanner-ом.
