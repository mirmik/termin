# Аудит termin-modules, reload библиотек и UnknownComponent roundtrip

Дата: 2026-07-10.

## Статус устранения замечаний

- **#287 закрыта (2026-07-10):** `ModuleRuntime` получил explicit fallible
  `shutdown()`, non-throwing destructor policy и запрет discovery поверх
  активных backend handles. Shutdown обрабатывает `Failed` records с handles в
  обратном порядке зависимостей; `ProjectModulesRuntime` использует этот
  контракт вместо собственного state-based обхода. Regression coverage
  проверяет retry retained C++ handles, normal/error cleanup Python imports и
  безопасное добавление нового descriptor через полный lifecycle boundary.
- **#288 реализована (2026-07-10):** native shadow copies перенесены из project
  build tree в отдельные backend-owned session directories. Collision-safe
  naming работает между параллельными runtimes; файлы удаляются после native
  close и на post-copy failure paths, а abandoned sessions очищаются только
  после проверки возраста и завершения владеющего PID. Linux regression tests
  покрывают repeated reload, injected init failure, concurrent runtimes и
  scoped abandoned cleanup; Windows gate остаётся обязательным перед закрытием.

## Резюме

`termin-modules` уже пригоден как developer/editor hot-reload beta. Основные
сценарии не являются заглушками: dependency-aware reload работает для Python и
C++, live-компоненты деградируют в `UnknownComponent` при неудачной загрузке и
восстанавливаются после исправления модуля. Эти пути покрыты native tests,
Python tests и editor-process smoke tests.

До production-grade plugin/runtime subsystem система пока не доведена. Главные
риски находятся не в happy path, а в контрактах вокруг него:

- live reload выполняется из worker thread без scene owner-thread boundary;
- Python unload не может атомарно отказаться при ошибке cleanup;
- descriptor refresh работает fail-open и может использовать устаревший graph;
- `UnknownComponent` upgrade не умеет доказать успешное применение payload;
- runtime может потерять активные backend handles при rediscovery/shutdown;
- у C++ модулей отсутствует versioned ABI handshake;
- shadow-копии native libraries не удаляются.

Практическая оценка готовности:

| Область | Оценка | Вывод |
| --- | ---: | --- |
| Python/editor happy path | 7/10 | Полезен для разработки, есть e2e coverage |
| `UnknownComponent` для совместимых схем | 7/10 | Известная `enabled`-регрессия исправлена |
| C++ hot reload happy path | 6/10 | Cascade и staged unload работают |
| Failure safety и concurrency | 3/10 | Есть production blockers |
| Публичный native plugin ABI | 2/10 | ABI/version contract отсутствует |

Итог: архитектурный фундамент сохранять и развивать имеет смысл. Переписывать
систему целиком не требуется, но объявлять её production-ready до закрытия
threading, unload atomicity, lifecycle ownership, ABI и migration integrity
нельзя.

## Область и методика

Проверены:

- `termin-modules`: runtime, descriptor parser, C++/Python backends и bindings;
- `termin-engine::TermModulesIntegration`;
- component/inspect/runtime type ownership;
- `UnknownComponent` degrade/upgrade и scene deserialization paths;
- `termin-project-modules::ProjectModulesRuntime`;
- editor file watcher, Modules panel и module operation dialog;
- headless player и editor-process reload smoke tests;
- документация `termin-modules` и релевантные Kanboard-карточки.

Аудит выполнялся по `HEAD` `6ed044e2` при чистом рабочем дереве. Изменения в
код не вносились; результаты аудита зафиксированы в Kanboard и в этом отчёте.

## Что в архитектуре сделано хорошо

### 1. Правильная граница между orchestration и engine integration

`ModuleRuntime` отвечает за discovery, dependency order, состояния и вызовы
backend-ов. Scene-specific поведение вынесено в `TermModulesIntegration` через
callbacks. Поэтому `termin-modules` не зависит напрямую от `SceneManager`,
`Entity` или `UnknownComponent`.

Это хорошая основа для headless/tooling hosts и будущих backend-ов. Engine
integration можно усиливать, не превращая core runtime в editor monolith.

### 2. Явный dependency-aware reload

Runtime строит topological order, запрещает одиночный unload загруженной
dependency и имеет отдельную операцию cascade reload. Unload идёт от dependents
к dependencies, load — в обратном порядке.

Сценарий с `native_leaf -> native_core` проверяется настоящей shared library в
editor process, а не только fake backend-ом.

### 3. Staged C++ unload

Для C++ уже существует важная safety boundary:

1. `module_shutdown`;
2. fallible cleanup module-owned runtime registrations;
3. `dlclose`/`FreeLibrary` только после успешного cleanup.

Если registry cleanup отказывается, handle сохраняется и модуль остаётся в
retryable failed state. Это существенно лучше безусловного `dlclose`.

### 4. Общий ownership runtime-типов

Component и inspect registrations получают owner module id. Общий runtime type
registry хранит facets и live instance count, благодаря чему unload может найти
все module-owned типы и подготовить живые экземпляры до снятия callbacks и
factory pointers.

Этот механизм уже используется для C++ и Python. Он же создаёт основу для
pass/widget/other runtime types, хотя parity пока не завершён.

### 5. UnknownComponent действительно сохраняет рабочее состояние

Live degrade сериализует inspect fields и дополнительно сохраняет core fields:

- `enabled`;
- `active_in_editor`;
- `display_name`.

Placeholder, созданный из scene data, не переносит собственный служебный
`enabled=false` в восстановленный component. Поэтому отсутствие поля сохраняет
constructor default, а явно сериализованное значение применяется.

Конкретная регрессия из карточки #172 закрыта тестами для C++ и Python.

### 6. Explicit dirty/apply policy

Filesystem watcher не перезагружает модули автоматически посреди обработки
события. Изменения помечаются dirty и применяются явным `Reload Changed` или
Play gate. Это лучше неуправляемого auto-reload и даёт место для build,
diagnostics и отказа от входа в Play.

### 7. Тесты и документация выше уровня прототипа

Документация честно описывает отсутствие автоматического rollback и partial
state после cascade failure. Тесты покрывают dependency order, missing/cyclic
dependencies, staged cleanup failure, failed Python import, native cascade и
последующее восстановление сцены.

## Production blockers и подтверждённые дефекты

### 1. Live reload выполняется вне scene owner thread

Editor dialog запускает всю переданную module operation в daemon
`threading.Thread`. В этот action входят не только build subprocesses, но и:

- обход сцен через `SceneManager`;
- замена компонентов в entities;
- вызовы component lifecycle;
- изменение process-global Component/Inspect/RuntimeType registries;
- `dlclose`/`FreeLibrary`.

Ни scene API, ни registries не имеют synchronization/owner-thread contract,
который делал бы такую операцию безопасной параллельно update/render/editor UI.
Modules panel временно не читает runtime records во время операции, но это не
останавливает остальные scene/render consumers.

Дополнительный process-global race: C++ build/validator helpers временно меняют
`std::filesystem::current_path()` вокруг `popen`. Из worker thread это меняет CWD
всего editor process и может влиять на file watcher, asset loading и другой код.

Целевая архитектура должна разделить:

- долгий build/validation process work, допустимый в worker;
- короткий reload commit, выполняемый на scene owner thread или explicit safe
  point при остановленном update/render;
- cancellation/shutdown policy для незавершённой операции.

Трекинг: **#285** `[editor/modules] Confine live module reload to owner thread`.

### 2. Python unload не является fallible и атомарным

У C++ есть возвращающий `bool` `before_native_close`. У Python
`before_unload` имеет тип `void`.

`TermModulesIntegration` обнаруживает ошибку `cleanup_module_registrations`, но
может только записать её в лог. После этого Python backend продолжает unload и
вызывает `module_context.unregister_module_owner()`.

Python cleanup дополнительно:

- ловит исключения отдельных registry operations;
- логирует их;
- не возвращает failure в backend;
- повторно снимает runtime types без live-scene context;
- после этого удаляет package subtree из `sys.modules`.

В результате возможен incoherent state: живой Python component/pass object ещё
существует, а его factory, inspect metadata или Python module уже удалены.

Нужен staged Python unload с prepare/commit semantics:

1. fallible scene degradation и проверка всех registries;
2. отсутствие мутаций при prepare failure;
3. commit removal из registries и `sys.modules` только после успешной подготовки;
4. сохранение retryable loaded handle/state при ошибке.

Трекинг: **#286** `[modules/python] Make unload failure atomic`.

### 3. Descriptor refresh работает fail-open

Статус 2026-07-10: **исправлено в #290**. Runtime теперь сначала разбирает все
известные descriptors во временный snapshot, проверяет identity, duplicate ids,
missing dependencies и cycles и только затем единым commit обновляет specs.
Reload closure строится уже по новому graph. Любая ошибка возвращается до
unload/build/clean, сохраняет последний валидный graph и dirty state; диагностика
содержит путь проблемного descriptor. Ниже оставлен исходный риск как контекст
решения.

`refresh_spec()` возвращает `void`. Если descriptor не читается, содержит
невалидный YAML или нарушает schema, runtime публикует `Failed` event, но
продолжает build/unload/reload со старым cached `ModuleSpec`.

Editor-level runtime затем может получить `true` и очистить dirty flag. Для
пользователя сломанный descriptor выглядит успешно применённым, хотя фактически
остались старые command, packages и dependencies.

Cascade planning имеет дополнительную проблему: перед построением affected
closure обновляется только target. Dependency lists других loaded records могут
быть устаревшими. Если dependent получил новую связь на native dependency, его
можно не включить в ABI reload и оставить работающим против заменённой library.

Требуется атомарный validated graph snapshot до первой live mutation:

- parse всех релевантных descriptors;
- duplicate id, missing dependency и cycle validation;
- построение affected closure по новому graph;
- commit specs только после полной проверки;
- failure до unload и сохранение dirty state.

Трекинг: **#290** `[modules/runtime] Fail closed on descriptor refresh errors`.

### 4. UnknownComponent upgrade может молча потерять payload

Текущий upgrade:

1. создаёт target component;
2. сразу присоединяет его к entity;
3. применяет core fields;
4. вызывает `tc_inspect_deserialize`;
5. безусловно удаляет `UnknownComponent` и возвращает success.

`tc_inspect_deserialize` возвращает `void`. Ошибки kind conversion и результат
`tc_inspect_set` не агрегируются в fallible status. Поэтому после schema drift,
невалидного resource handle или setter failure может остаться частично
инициализированный component, а единственная точная копия `original_data` будет
удалена. `UnknownComponentStats.upgraded` при этом увеличится.

Attach-before-deserialize создаёт отдельный lifecycle defect: `on_added` видит
constructor defaults, а не восстановленное состояние. Для components, которые
создают runtime resources в `on_added`, это может изменить поведение даже при
валидном payload. C++ scene deserialization в другом пути применяет data до add,
то есть lifecycle semantics сейчас различаются.

Нужны:

- fallible field-level deserialize diagnostics;
- unattached/staged candidate;
- удаление placeholder только после принятого migration result;
- explicit policy для unknown/removed fields и schema evolution;
- одинаковый lifecycle order для C++ и Python.

Трекинг: **#289** `[scene/unknown] Keep placeholder on restore errors`.

### 5. ModuleRuntime не владеет shutdown lifecycle

`ModuleRuntime::discover()` начинает с `_records.clear()`. Он не запрещает
rediscovery при активных handles и не выгружает предыдущие records.

Handles сами не являются RAII owners backend cleanup:

- уничтожение `CppModuleHandle` не вызывает `dlclose`;
- уничтожение `PythonModuleHandle` не очищает `sys.modules`/`sys.path`;
- runtime не имеет explicit `close()`/`shutdown()`.

`ProjectModulesRuntime` обычно выполняет ручной shutdown перед recreation, но:

- public `load_descriptor()` вызывает `discover()` на существующем runtime;
- native API также публично выставляет `discover()`;
- `_shutdown_runtime()` выгружает только state `Loaded` и пропускает `Failed`
  records, всё ещё содержащие handle.

Rediscovery или exceptional shutdown могут потерять единственный путь к
корректной выгрузке library/module registrations.

Трекинг: **#287** `[modules/runtime] Make discovery and shutdown handle-safe`.

### 6. У native module API отсутствует versioned ABI

Native validator доказывает только, что library можно открыть и разрешить её
relocations. `module_init` и `module_shutdown` являются optional `void()`
symbols. Library вообще без `module_init` считается успешно загруженным модулем.

Не определены:

- ABI/API version;
- SDK build identity;
- compiler/runtime compatibility;
- structured module descriptor/capabilities;
- fallible init result;
- host function table/context;
- обязательность и идемпотентность shutdown.

Так как module code обменивается с host C++ types и registry callbacks, успешный
`dlopen` не доказывает ABI compatibility. Несовместимый SDK/compiler может дать
process corruption вместо понятной ошибки.

Production contract должен иметь узкую versioned C ABI entry point, explicit
host API table и проверку compatibility до in-process registrations.

Трекинг: **#291** `[modules/cpp] Define versioned native module ABI`.

### 7. Shadow-loaded native artifacts не удаляются

Чтобы обойти loader cache, backend копирует artifact рядом с оригиналом под
именем `<artifact>.loaded.<counter>`. Копия не удаляется:

- после успешного unload;
- после `dlopen` failure;
- после exception из `module_init`;
- после crash editor process.

Counter является process-global неатомарным `int`, а имя не содержит session
identity. Долгие editor sessions будут накапливать binaries в project build
tree.

Копии должны жить в runtime-owned temp/cache directory, иметь collision-safe
имена и удаляться после library close и на всех failure paths. Cleanup failure
должен логироваться.

Трекинг: **#288** `[modules/cpp] Clean shadow-loaded library artifacts`.

## Известные архитектурные хвосты

### Static registration

Owner scope для C++ включается непосредственно перед `module_init`, то есть
static constructors, выполняемые во время `dlopen`, намеренно остаются unowned.
Это защищает случайно притянутые engine header side effects от удаления, но не
решает саму проблему неявной регистрации.

Проектные модули должны использовать explicit `TC_MODULE_*` registration из
`module_init`, а SDK/bootstrap постепенно уходить от header/static side effects.

Трекинг: **#138** `[arch/bootstrap] Уйти от static registration`.

### Нет UnknownPass parity

Component instances могут перейти в `UnknownComponent`, но frame/pass pipeline
не имеет симметричного placeholder contract. При failed module reload render
graph state защищён хуже scene component state.

Трекинг: **#139** `[render/modules] Добавить UnknownPass для reload failures`.

### Cascade failure и recovery

Runtime намеренно не пытается rollback после `dlclose`: уже загруженные модули
остаются загруженными, уже выгруженные — выгруженными, failing module получает
`Failed`. Это разумнее опасной попытки оживить старый native handle, но UI и
runtime contract должны явно показывать coherent/degraded closure и безопасный
путь повторного восстановления.

### Python dependency delivery

Project Python environment создаётся и requirements могут устанавливаться при
load. Это удобно для разработки, но production delivery требует exact lock,
offline/package validation и полноценной проверки version specifiers. Простое
наличие distribution недостаточно для воспроизводимости.

### Package/type identity

Module id и component original type являются строками без namespace/schema
version. Не запрещены пересекающиеся Python package subtrees между modules.
Для долгоживущих production scenes нужны module/type identity, schema evolution
и сохранение неизвестных полей.

## Проверка

Перед Python tests test-only SDK environment был обновлён штатным
`./setup-sdk-python-env.sh`.

Успешно прошли native tests:

```text
ctest --test-dir build/Release-tests \
  -R '^(termin_modules_runtime_test|termin_scene_unknown_component_test|termin_engine_cpp_module_hot_reload_test)$' \
  --output-on-failure

3/3 passed
```

Успешно прошли editor/player Python tests:

```text
./run-tests-python.sh \
  termin-app/tests/test_project_file_watcher.py \
  termin-app/tests/test_modules_panel_operations.py \
  termin-player/tests/test_headless_runtime.py

46 passed
```

Отдельно проверены Python default-state regressions:

```text
./run-tests-python.sh termin-scene/tests/test_unknown_component_enabled.py

2 passed
```

Успешно прошли editor-process smokes:

```text
scripts/smoke-python-module-hot-reload --timeout 30
scripts/smoke-cpp-module-cascade-hot-reload --timeout 45
```

Python smoke подтвердил последовательность:

1. исходный component загружен;
2. syntax error при reload переводит live instance в `UnknownComponent`;
3. module остаётся `Failed` и dirty;
4. после исправления source повторный reload восстанавливает component type и
   serialized value.

C++ smoke подтвердил unload dependent до dependency, обратный load order и
сохранение live component value.

Полные `./build-sdk.sh --no-wheels` и `./run-tests.sh` в рамках аудита не
запускались. Выводы основаны на focused native/Python tests и двух настоящих
editor-process reload smokes.

После выбранного Python прогона nanobind сообщил leaked instances/types/functions
из geometry bindings. Это не связано непосредственно с `termin-modules` и уже
отражено существующей карточкой **#213**.

## Состояние Kanboard после аудита

Активные задачи по module runtime, reload, registration ownership и degraded
placeholders собраны в отдельном swimlane **Modules & Hot Reload**.

- **#172** закрыта: конкретная `UnknownComponent -> enabled=false` регрессия
  исправлена и повторно проверена C++/Python tests.
- **#105** оставлена On Test и дополнена owner-thread/GIL/C++ reload рисками.
- **#287** закрыта: discovery/shutdown больше не теряют активные handles.
- **#288** реализована и находится On Test: shadow artifacts изолированы и
  очищаются backend-ом; остаётся Windows DLL verification.
- **#290** закрыта: descriptor refresh стал fail-closed atomic graph snapshot.
- Созданы отдельные недублирующиеся задачи:

| Карточка | Назначение |
| --- | --- |
| #285 | Owner-thread/safe-point architecture для editor reload |
| #286 | Fallible atomic Python unload |
| #287 | Handle-safe discovery и shutdown ownership |
| #288 | Cleanup shadow-loaded libraries |
| #289 | Lossless/fallible UnknownComponent restore |
| #290 | Fail-closed descriptor refresh и consistent graph snapshot |
| #291 | Versioned native module ABI |

## Рекомендуемый порядок работ

1. Закрыть **#285** и **#286**: сейчас это прямые crash/corruption boundaries.
2. Закрыть **#290**: не начинать live mutation по невалидному/stale graph.
3. Закрыть **#289**: сделать scene migration доказуемо lossless или явно
   degraded.
4. Закрыть **#287**: установить единое ownership/close правило для handles.
5. Спроектировать **#291** до расширения публичного C++ module ecosystem.
6. Закрыть локальный cleanup **#288**.
7. Продолжить **#138** и **#139** как системные parity/migration направления.

После первых пяти пунктов систему можно повторно оценивать как production
candidate. До этого зелёные happy-path smokes доказывают полезность hot reload,
но не его безопасность при конкурентной работе и ошибках.
