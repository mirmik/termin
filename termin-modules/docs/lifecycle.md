# Жизненный цикл

Ниже описан текущий жизненный цикл модуля в `termin-modules`.

## Владение runtime и shutdown

`ModuleRuntime` является единственным владельцем backend handles в своих
records и поэтому намеренно не копируется и не перемещается. Перед удалением
runtime или повторным discovery хост вызывает `shutdown()`. Операция выгружает
активные records в обратном порядке зависимостей, включая records в состоянии
`Failed`, если они всё ещё держат backend handle. Ошибка возвращается как
`false` с диагностикой; records и неосвобождённые handles сохраняются, чтобы
причину можно было устранить и повторить shutdown.

`discover()` отказывает при наличии активных handles и не заменяет текущие
records. Деструктор выполняет ту же попытку shutdown без исключений и пишет
ошибку в лог, если очистка невозможна: молчаливое удаление native/Python handle
потеряло бы единственный оставшийся путь корректной выгрузки.

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
4. если в `ModuleEnvironment.sdk_prefix` доступен
   `bin/termin_module_native_validator`, запускает отдельный helper-процесс,
   который делает clean-process `dlopen(..., RTLD_NOW | RTLD_LOCAL)` /
   `LoadLibrary` для artifact
5. на Linux при провале validation добавляет отфильтрованный `ldd -r | c++filt`
   вывод в diagnostics
6. создаёт уникальную backend-owned load directory под системным temp root и
   копирует туда artifact вместе с соседними dynamic libraries, сохраняя
   loader-origin dependency lookup без загрязнения project build tree
7. загружает shared library через `dlopen` или `LoadLibrary`
8. ищет символ `module_init`
9. если символ найден, вызывает его внутри native-init callback scope
10. сохраняет native handle в `CppModuleHandle`

Shadow artifact удаляется только после `dlclose`/`FreeLibrary`. Все failure
paths после копирования также удаляют его; ошибка удаления логируется и при
обычном unload оставляет record retryable. Каждый backend получает отдельную
collision-safe session directory, поэтому параллельные runtimes не используют
общие имена. При создании новой session удаляются только directories старше 24
часов, владеющий PID которых уже не существует. Для тестов или host policy root
можно явно задать через `ModuleEnvironment::native_shadow_root`.

Важно:

- глобальные статические конструкторы shared library вызываются загрузчиком ОС при `dlopen`/`LoadLibrary`
- `module_init` это дополнительная явная точка входа поверх static initialization
- integration layer включает owner scope регистрации только на время
  `module_init`; C++ component/inspect registrations, сделанные в static
  constructors при `dlopen`/`LoadLibrary`, считаются legacy side effects и не
  получают module ownership
- project C++ artifact должен быть самодостаточным на уровне DT_NEEDED/RUNPATH;
  уже загруженные editor/SDK библиотеки и Python-side preload не должны быть
  обязательным условием для успешного native load

## 5. load для Python модуля

`PythonModuleBackend`:

1. инициализирует embedded Python, если он ещё не поднят
2. добавляет `root` в `sys.path`
3. импортирует все пакеты из `packages`
4. сохраняет список импортированных модулей и добавленных путей в `PythonModuleHandle`

## 6. unload

`ModuleRuntime::unload_module(name)`:

1. проверяет, что модуль находится в состоянии `Loaded` или всё ещё держит backend handle
2. вызывает integration hook `before_unload`
3. для staged backend-ов вызывает `begin_unload(...)`
4. вызывает integration hook, который должен очистить регистрации до закрытия native handle
5. вызывает `finish_unload(...)`
6. очищает `handle`
7. переводит модуль в `Unloaded`
8. публикует событие

Для C++:

- если найден `module_shutdown`, он вызывается
- затем `termin-engine` снимает module-owned `InspectRegistry` и `ComponentRegistry`
  registrations по `module_id`
- затем shared library выгружается
- если owner cleanup падает, native handle остаётся загруженным, модуль получает
  `Failed`, а следующий unload может повторить cleanup без повторного закрытия
  уже выгруженной библиотеки

Для Python:

- импортированный package subtree удаляется из `sys.modules`
- добавленные пути удаляются из `sys.path`
- регистрации, выполненные под module import context, снимаются по `module_id`

Python backend включает `termin_modules.module_context` на время импорта
пакетов из `.pymodule`. Компоненты, inspect-типы, Python kind handlers и
editor-side class registries, которые умеют читать этот context, помечают
регистрации владельцем модуля. При unload backend сначала вызывает owner
cleanup, затем удаляет package subtree из `sys.modules`.

Unowned C++ registrations считаются допустимыми для встроенных engine/component
libraries. Project C++ modules, которые участвуют в hot reload, должны грузиться
через module runtime owner scope; иначе runtime не сможет гарантированно снять
factory/accessor callbacks перед `dlclose`/`FreeLibrary`.

## 7. reload

`ModuleRuntime::reload_module(name)` сейчас реализован как orchestration-операция:

1. публикуется событие `Reloading`
2. если модуль был загружен, выполняется `unload_module(name)`
3. затем выполняется `load_module(name)`
4. после успешной перезагрузки вызывается integration hook `after_reload`

То есть сейчас у backend-ов нет отдельного специализированного `reload`; runtime собирает его из `unload + load`.

`reload_module(name)` остаётся одиночной операцией. Если у модуля есть
загруженные dependents, сработает обычный unload guard и reload завершится
ошибкой. Для hot reload dependency-модулей используется отдельная операция
`ModuleRuntime::reload_module_with_dependents(name)`:

1. runtime собирает `name` и все транзитивные dependents, которые сейчас
   находятся в `Loaded` или всё ещё держат backend handle
2. выгружает affected-модули в обратном dependency order: сначала самые верхние
   dependents, затем их dependencies
3. загружает affected-модули обратно в dependency order
4. вызывает reload-state callbacks для каждого affected-модуля

Dependents, которые не были загружены к моменту reload, не включаются в graph и
не поднимаются автоматически.

Если восстановление state после reload падает, runtime переводит модуль в
`Failed` и публикует `Failed` event. Старую версию модуля runtime не пытается
автоматически оживлять; scene state должен оставаться в безопасном degraded
состоянии (`UnknownComponent`) до следующего успешного reload или ручного
восстановления.

Если cascade reload падает на unload/load/restore одного из affected-модулей,
операция останавливается на первом сбое. Уже выгруженные модули остаются
выгруженными, уже успешно загруженные остаются загруженными, а failing module
получает `Failed` и диагностическое сообщение. Runtime намеренно не делает
автоматический rollback, потому что после закрытия native handle старую версию
модуля нельзя считать безопасно восстанавливаемой.

Editor watcher не выполняет module reload прямо на filesystem-событии. Изменения
Python `.pymodule`, `.py` файлов внутри `packages`, C++ `.module` и native
input-файлов помечают владеющий модуль dirty. Initial scan не пачкает уже
существующие native inputs; live create/change/remove события помечают модуль
dirty.

Применение изменений выполняется явным действием (`Reload Changed` /
`Build & Reload Changed`) или Play-gate перед входом в Game Mode. Play-gate
вызывает editor-level `prepare_changed_modules_for_play()`: dirty/stale модули
reload-ятся через dependency-aware cascade, а C++ backend при load выполняет
build command. Если build/reload падает, Play не стартует, модуль остаётся в
`Failed`/degraded состоянии с диагностикой.

Loose `.py` файлы вне `.pymodule` являются поддерживаемой editor policy, а не
случайным fallback: проектное Python-пространство рассматривается как единый
package-like namespace для scripts, editor extensions и быстрых runtime
компонентов. Watcher передаёт такие файлы в legacy `ComponentFileProcessor`,
`ResourceManager.scan_components()` исполняет их, а `ComponentClassRegistry.scan()`
регистрирует найденные `PythonComponent` subclasses. Initial scan загружает loose
components при открытии проекта; live create/change события только помечают файл
dirty до явного reload или Play-gate. Файлы, которые не объявляют компоненты, всё
равно могут быть helper/editor-extension scripts и остаются частью этого
проектного Python-пространства.
В editor watcher path loose `.py` файлы живут в synthetic namespace
`termin_project`: `Scripts/player.py` загружается как
`termin_project.Scripts.player`. Это позволяет использовать relative imports
между соседними loose-файлами (`from .helpers import X`) и absolute imports от
проектного корня (`from termin_project.Shared.values import X`) без добавления
project root в глобальный `sys.path`. Части пути должны быть валидными Python
module identifiers; файлы с невалидным import path продолжают грузиться через
private generated module name.
Если проектному Python-коду нужен явный стабильный package ownership,
requirements или module lifecycle, его нужно оформить как пакет и подключить
через `.pymodule`.
Повторная загрузка loose-файла читает source напрямую, без `.pyc` cache, и
заменяет классы, найденные в том же generated module.
Если изменённый loose `.py` не регистрирует компонентов, explicit reload
выполняет conservative refresh уже отслеженных loose component scripts. Это
покрывает типичный helper-only сценарий: `Scripts/helper.py` меняется, а ранее
загруженный `Scripts/player.py` или `termin_project.Shared.values` dependent
пересканируется и получает новые imports. Это не полноценный dependency graph и
не заменяет `.pymodule` lifecycle, но сохраняет текущую удобную editor-политику
свободных scripts.

## 8. Smoke-проверки

Для проверки editor-process explicit reload есть два headless smoke-скрипта:

- `scripts/smoke-python-module-hot-reload` проверяет Python `.pymodule` explicit
  reload, failed reload degradation в `UnknownComponent` и последующее
  восстановление.
- `scripts/smoke-cpp-module-cascade-hot-reload` проверяет C++ dependency cascade
  explicit reload внутри editor process: `native_leaf` зависит от `native_core`,
  reload `native_core` должен выгрузить dependent раньше dependency, загрузить
  обратно в dependency order и восстановить live C++ scene component.

Оба скрипта используют `scripts/termin-editor-mcp`; на headless Linux они
автоматически запускают editor через `xvfb-run`, если нет активного display.
Они также входят в центральный `./run-tests.sh` после C++ и Python тестов.
Для окружений без editor SDK/editor MCP можно временно пропустить эту стадию
через `./run-tests.sh --no-editor-smoke`.
