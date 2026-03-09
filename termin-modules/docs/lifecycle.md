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
- `__pycache__`
- скрытые директории

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

- импортированные модули удаляются из `sys.modules`
- добавленные пути удаляются из `sys.path`

## 7. reload

`ModuleRuntime::reload_module(name)` сейчас реализован как orchestration-операция:

1. публикуется событие `Reloading`
2. если модуль был загружен, выполняется `unload_module(name)`
3. затем выполняется `load_module(name)`
4. после успешной перезагрузки вызывается integration hook `after_reload`

То есть сейчас у backend-ов нет отдельного специализированного `reload`; runtime собирает его из `unload + load`.
