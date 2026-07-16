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
   `LoadLibrary`, находит descriptor ABI v1 и проверяет identity и совместимость
   artifact, не вызывая его lifecycle
5. на Linux при провале validation добавляет отфильтрованный `ldd -r | c++filt`
   вывод в diagnostics
6. создаёт уникальную backend-owned load directory под системным temp root и
   копирует туда artifact вместе с соседними dynamic libraries, сохраняя
   loader-origin dependency lookup без загрязнения project build tree
7. загружает shared library через `dlopen` или `LoadLibrary`
8. ищет обязательный символ `termin_module_descriptor_v1` и повторяет проверку
   descriptor до открытия registration scope
9. формирует стабильную host API table/context и вызывает обязательный fallible
   `descriptor.init` внутри native-init callback scope
10. при ошибке init вызывает cleanup callback и best-effort shutdown до закрытия
    library; при успехе сохраняет descriptor, host API и native handle в
    `CppModuleHandle`

Shadow artifact удаляется только после `dlclose`/`FreeLibrary`. Все failure
paths после копирования также удаляют его; ошибка удаления логируется и при
обычном unload оставляет record retryable. Каждый backend получает отдельную
collision-safe session directory, поэтому параллельные runtimes не используют
общие имена. При создании новой session удаляются только directories старше 24
часов, владеющий PID которых уже не существует. Для тестов или host policy root
можно явно задать через `ModuleEnvironment::native_shadow_root`.

Важно:

- глобальные статические конструкторы shared library вызываются загрузчиком ОС при `dlopen`/`LoadLibrary`
- ABI v1 descriptor и обе lifecycle-функции обязательны; legacy
  `module_init`/`module_shutdown` больше не являются точками входа
- integration layer включает owner scope регистрации только на время
  `descriptor.init`; C++ component/inspect registrations, сделанные в static
  constructors при `dlopen`/`LoadLibrary`, считаются legacy side effects и не
  получают module ownership
- project C++ artifact должен быть самодостаточным на уровне DT_NEEDED/RUNPATH;
  уже загруженные editor/SDK библиотеки и Python-side preload не должны быть
  обязательным условием для успешного native load

## 5. Session environment и load для Python модуля

После успешного discovery `ModuleRuntime` один раз вызывает session-level
`PythonModuleBackend::prepare_environment` до первого импорта. Backend:

1. инициализирует embedded Python, если он ещё не поднят
2. создаёт/проверяет общий project `.venv`
3. канонизирует и добавляет его site-packages и все `root` обнаруженных
   `.pymodule` в `sys.path`, не присваивая уже существующие равные entries

Module load проверяет requirements в общем environment, импортирует все пакеты
из `packages` и сохраняет в `PythonModuleHandle` только import-transaction state.
Module unload не меняет session paths. `ModuleRuntime::shutdown` сначала
выгружает модули, затем ровно один раз снимает только добавленные этой session
entries. Ошибка prepare откатывает добавленные entries и не допускает imports.

## 6. unload

`ModuleRuntime::unload_module(name)`:

1. проверяет, что модуль находится в состоянии `Loaded` или всё ещё держит backend handle
2. вызывает integration hook `before_unload`
3. для Python вызывает fallible `before_module_remove`, который подготавливает
   все owner registrations, не удаляя их
4. для staged native backend-ов вызывает `begin_unload(...)`
5. вызывает integration hook, который должен очистить регистрации до закрытия native handle
6. вызывает backend commit (`finish_unload` либо Python registry/module removal)
7. очищает `handle`
8. переводит модуль в `Unloaded`
9. публикует событие

Для C++:

- обязательный fallible `descriptor.shutdown` вызывается ровно один раз для
  успешной попытки unload; ошибка оставляет handle и descriptor доступными для
  повторной попытки
- затем `termin-engine` снимает module-owned `InspectRegistry` и `ComponentRegistry`
  registrations по `module_id`
- затем shared library выгружается
- если owner cleanup падает, native handle остаётся загруженным, модуль получает
  `Failed`, а следующий unload может повторить cleanup без повторного закрытия
  уже выгруженной библиотеки

Для Python:

- runtime-type registry сначала вызывает prepare-unload lifecycle у всех типов
  владельца и не удаляет ни один type/facet, пока весь owner set не подготовлен
- ошибка prepare-unload прерывает операцию до Python backend: handle,
  registrations и `sys.modules` остаются на месте, state остаётся `Loaded`;
  session-owned `sys.path` при module unload не меняется
- после успешного prepare `module_context` commit-ит Python-side registries и
  runtime types; исключение не проглатывается и сохраняет retryable handle/state
- импортированный package subtree удаляется из `sys.modules`
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

1. все известные descriptors заново разбираются во временный snapshot
2. snapshot целиком проверяется на duplicate ids, missing dependencies и cycles
3. только после успешной проверки новые specs атомарно заменяют предыдущий graph
4. публикуется событие `Reloading`
5. если модуль был загружен, выполняется unload
6. затем выполняется load
7. после успешной перезагрузки вызывается integration hook `after_reload`

Descriptor identity считается стабильной на протяжении жизни runtime: изменение
`name` отклоняется и требует полного lifecycle boundary/discovery. Смена backend
kind загруженного модуля также отклоняется. Ошибка чтения или validation любого
descriptor завершает операцию до unload/build/clean, оставляет live handles и
последний валидный graph нетронутыми и сообщает путь через `last_error`/`Failed`
event. Editor-level dirty flag очищается только после успешного reload.

То есть сейчас у backend-ов нет отдельного специализированного `reload`; runtime собирает его из `unload + load`.

`reload_module(name)` остаётся одиночной операцией. Если у модуля есть
загруженные dependents, сработает обычный unload guard и reload завершится
ошибкой. Для hot reload dependency-модулей используется отдельная операция
`ModuleRuntime::reload_module_with_dependents(name)`:

1. после atomic descriptor snapshot runtime собирает `name` и все транзитивные dependents, которые сейчас
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

### Owner-thread boundary в editor

`TermModulesIntegration::configure_runtime()` привязывает live mutation к
потоку, на котором создана integration. `load`, `unload`, `reload`, `rebuild` и
shutdown fail-closed до backend/registry вызовов, если их вызвали с другого
потока; `last_error` содержит operation и thread-contract diagnostic.

Editor progress dialog разделяет операцию на две части:

1. build/clean/rebuild выполняется non-daemon worker-ом через отдельный
   `sdk/bin/termin_python -m termin.project_modules.warmup` process; у него свой
   runtime, CWD, Python interpreter и registries
2. live unload/load, UnknownComponent migration и registry commit ставятся через
   `UI.defer()` и выполняются после текущего UI/render compose на owner thread

Это сохраняет отзывчивость UI во время native build и исключает изменение CWD,
scene или process-global registries из module worker. Диалог нельзя закрыть до
завершения build; worker не daemon. При shutdown незавершённый build может
закончить только isolated phase, а live commit без обработки owner-thread queue
не выполняется. Play gate использует ту же prebuild/owner-commit схему.

Python wrappers на module-owned live objects, удерживаемые console/MCP/tooling
вне управляемой сцены, считаются настоящими live references и блокируют unload.
Tooling обязано отпустить такие ссылки до commit; editor smoke probe явно
очищает persistent executor globals перед запросом reload.

Editor watcher не выполняет module reload прямо на filesystem-событии. Изменения
Python `.pymodule`, `.py` файлов внутри `packages`, C++ `.module` и native
input-файлов помечают владеющий модуль dirty. Initial scan не пачкает уже
существующие native inputs; live create/change/remove события помечают модуль
dirty.

Применение изменений выполняется явным действием (`Reload Changed` /
`Build & Reload Changed`) или Play-gate перед входом в Game Mode. Play-gate
сначала запускает isolated artifact preparation, затем на owner thread вызывает
editor-level `prepare_changed_modules_for_play()`: dirty/stale модули
reload-ятся через dependency-aware cascade, а уже подготовленный C++ artifact
не требует долгого build в commit phase. Если build/reload падает, Play не стартует, модуль остаётся в
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
