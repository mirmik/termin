# Готовность Termin к free-threaded Python

Дата: 2026-07-24.

Статус: cutover на pinned CPython 3.14t выполнен в build/runtime contract.
Linux SDK и полный import graph проверены; Windows build/test smoke остаётся
обязательной platform-проверкой перед закрытием release-карточки.

Связанные документы:

- [Python runtime and threading contract](../architecture/2026-07-24-python-runtime-contract.md);
- [Запрет owner-thread restrictions](../architecture/2026-07-24-no-owner-thread-restrictions.md);
- [Готовность движка к многопоточной обработке](2026-07-21-engine-multithreading-readiness.md);
- [Асинхронная подготовка ассетов](2026-07-21-async-asset-pipeline.md);
- [Аудит использования NumPy](2026-07-07-numpy-usage-inventory.md).

## Резюме

Termin использует один bundled runtime: exact-pinned CPython 3.14.6t. Все
first-party packages требуют Python 3.14, native-модули собираются против
единого `libnanobind-ft`, а import-graph gate проверяет исходно выключенный GIL
и состояние после каждого native и product-level импорта.

Free-threaded Python не делает API движка автоматически пригодным для
параллельного доступа. Текущий engine contract остаётся последовательным:
приложение само определяет фазу применения изменений. Worker может публиковать
completion через `termin-dispatch`, а host вызывает `drain` в выбранной точке
своего цикла. Сам dispatcher не назначает owner thread и не встраивается в
engine/UI автоматически.

Параллельный доступ к конкретной подсистеме разрешается только её отдельным
контрактом. До появления такого контракта speculative mutexes, owner-thread
checks и скрытый `defer` внутрь Termin не добавляются.

В соответствии с архитектурной политикой Termin решение не должно вводить
`owner_thread`, `defer-to-owner` или отказы API на основании identity
вызывающего потока. Запрет `thread_local` также остаётся в силе.

## Текущее состояние SDK

Runtime SDK формируется из
`build-system/python-runtime-lock.txt`. В нём зафиксированы:

- `numpy==2.5.1`;
- `PyYAML==6.0.3`;
- `watchdog==6.0.0`;
- `glfw==2.10.0`;
- pure-Python test/tooling dependencies.

Build frontend отдельно использует `nanobind==2.13.0`, а тестовое окружение —
`scipy==1.18.0`.

Фактически установленный Linux SDK содержит Python C extensions только у
NumPy, PyYAML, tomli и собственных модулей Termin. `glfw` и Linux backend
watchdog обращаются к native-библиотекам через `ctypes`.

## Матрица внешних зависимостей

| Компонент | Текущая версия | Состояние | Требуемое действие |
| --- | ---: | --- | --- |
| CPython | 3.14.6t | Pinned free-threaded toolchain | Сохранять exact source hash и ABI verification |
| NumPy | 2.5.1 | Опубликованы `cp314t` wheels | Проверять supported tags и import smoke |
| PyYAML | 6.0.3 | Опубликованы `cp314t` wheels | Оставить версию и добавить install/import smoke |
| SciPy | 1.18.0, test-only | Опубликованы `cp314t` wheels | Устанавливать test overlay целевым build Python |
| watchdog | 6.0.0 | Linux/Windows paths — Python/`ctypes`; macOS имеет отдельный native-риск | Проверить все целевые платформы; обновить macOS package при необходимости |
| glfw | 2.10.0 | Python wrapper использует `ctypes` и не является CPython extension | Оставить, добавить callback/concurrency smoke |
| colorama, exceptiongroup, iniconfig, packaging, pluggy, Pygments, pytest, tomli, typing_extensions | exact lock | Pure Python | Проверить install/import/test на 3.14t |
| nanobind | 2.13.0, build-only | Поддерживает free-threaded CPython | Перестроить общий SDK runtime и все модули с `FREE_THREADED` |

Источники:

- [CPython: Python support for free threading](https://docs.python.org/3/howto/free-threading-python.html);
- [CPython: C API Extension Support for Free Threading](https://docs.python.org/3.14/howto/free-threading-extensions.html);
- [nanobind: Free-threaded Python](https://nanobind.readthedocs.io/en/latest/free_threaded.html);
- [NumPy thread safety](https://numpy.org/doc/stable/reference/thread_safety.html);
- [SciPy thread safety](https://docs.scipy.org/doc/scipy-1.15.0/tutorial/thread_safety.html);
- [PyYAML 6.0.3 files](https://pypi.org/project/PyYAML/6.0.3/);
- [ctypes thread safety without the GIL](https://docs.python.org/3/library/ctypes.html#thread-safety-without-the-gil);
- [Assimp threading](https://the-asset-importer-lib-documentation.readthedocs.io/en/latest/usage/use_the_lib.html#threading);
- [GLFW thread safety](https://www.glfw.org/docs/latest/intro_guide.html#thread_safety).

## Общий nanobind runtime

nanobind умеет собирать free-threaded extensions начиная с версии 2.2.0. Для
этого `nanobind_add_module()` получает `FREE_THREADED`. Параметр:

- отмечает extension как не требующий глобального GIL;
- включает free-threaded реализацию внутренних структур nanobind;
- меняет ABI tag внутренних nanobind structures.

В одном процессе нельзя смешивать обычные и free-threaded nanobind modules,
которые должны обмениваться типами. Все Termin extensions обязаны использовать
один вариант общего `libnanobind`.

Реализован отдельный согласованный SDK configuration без локального добавления
флага в каждый модуль:

1. Python runtime всегда является CPython 3.14t.
2. SDK строит единственный `libnanobind-ft.so`.
3. Канонический CMake wrapper применяет профиль ко всем `NB_SHARED` modules и
   C++ bridges; package config сверяет полный Python SOABI.
4. Автоматическая инвентаризация сопоставляет каждый `NB_MODULE` с ровно одним
   каноническим target.
5. Все Termin native wheels строятся тем же frontend и ABI.
6. Runtime lock материализует только совместимые wheels.
7. SDK smoke проверяет, что после импорта всех native-модулей
   `sys._is_gil_enabled()` остаётся `False`.

Импорт хотя бы одного extension, не объявившего поддержку free threading,
может автоматически включить GIL для процесса. Поэтому частичная миграция
бессмысленна как конечное состояние.

## Process-global state

Аудит native state не выявил блокера для последовательного engine contract.
Статическая строка inspect parent заменена каноническим `tc_intern`. Остальные
обнаруженные process-global механизмы имеют отдельные design/follow-up
карточки:

- `g_animation_python_callbacks`;
- `g_navmesh_load_callbacks`;
- callback registry в mesh bindings;
- `g_skeleton_python_callbacks`;
- `g_texture_python_callbacks`;
- глобальный `nb::callable` в `tcbase`;
- `g_ptr_extractors` в inspect bindings;
- input device registry и несколько collision scratch buffers.

Они не получают мьютексы только из-за перехода runtime. Если конкретный
публичный API впоследствии разрешит конкурентное чтение/изменение, владелец
подсистемы должен определить lifetime, reentrancy, publication и cleanup.
Недопустимы:

- проверка identity creator/owner thread;
- перенос вызова через скрытый `defer`;
- надежда на то, что nanobind или контейнер Python сериализует составную
  операцию;
- `thread_local` registry или callback state.

## Python callbacks и thread state

В free-threaded CPython отсутствие GIL не отменяет Python thread state.
Внешний C++ thread перед вызовом Python C API обязан иметь attached
`PyThreadState`. Поэтому существующие `nb::gil_scoped_acquire` нельзя
механически удалить: в free-threaded nanobind они продолжают участвовать в
правильном присоединении потока, хотя уже не должны служить глобальным
мьютексом приложения.

Следует разделить два понятия:

1. вход в Python runtime и lifetime Python objects;
2. синхронизация состояния конкретного subsystem.

Первое обеспечивается CPython/nanobind thread-state API. Второе обеспечивается
владельцем данных. Нельзя использовать `gil_scoped_acquire` как замену
subsystem lock.

Отдельный аудит нужен для:

- callbacks, хранящихся в C++ дольше одного вызова;
- C++ destructors, которые освобождают Python references;
- shutdown/finalization;
- callback reentrancy;
- module reload и замены callback registries;
- borrowed Python references и iterator lifetime.

## NumPy и массивы

Большинство числовых операций NumPy и в обычном CPython освобождают GIL.
Free-threaded runtime особенно полезен для Python-кода между такими kernels:
обхода glTF structures, построения словарей, material/mesh metadata и
координации независимых asset jobs.

Безопасная базовая модель:

- job владеет своими arrays;
- shared arrays передаются read-only;
- запись в общий array разрешена только в непересекающиеся диапазоны с явно
  доказанным lifetime;
- `dtype=object` не используется в параллельном asset path;
- после передачи buffer view в C++ Python не меняет и не освобождает backing
  storage до завершения native consumer.

Free-threading не исправит медленный per-element Python algorithm
автоматически. Для GLB по-прежнему нужны native/vectorized transforms и
уменьшение числа Python/C++ crossings.

## Embedded CPython

Product entry points больше не настраивают CPython независимо друг от друга.
`termin-python-host` предоставляет единый host contract:

- `PyConfig`/`Py_InitializeFromConfig` вместо deprecated global flags;
- явная isolated/environment policy для каждого процесса;
- ABI validation с ожидаемыми и фактическими version, SOABI и
  `Py_GIL_DISABLED`;
- общий lifecycle smoke с повторной initialize/finalize;
- fail-fast diagnostics до загрузки engine/editor state.

Raw `_termin_player_native` переведён на multi-phase module definition,
объявляет `Py_MOD_GIL_NOT_USED` и не включает GIL при импорте. Доступ к
process-global active-host pointer синхронизирован внутри owning player
boundary; owner-thread restrictions не вводились.

## ctypes-зависимости

Отсутствие CPython extension означает лишь отсутствие ABI-блокера.
Потокобезопасность foreign library и разделяемых `ctypes` objects остаётся
ответственностью вызывающего кода.

### glfw

Python wrapper совместим с 3.14t на уровне ABI. Однако GLFW налагает внешние
platform constraints: initialization, event processing и многие window
operations должны выполняться из platform main thread.

Это не оправдывает engine-wide `owner_thread`. Ограничение должно быть
локализовано внутри platform adapter: произвольный engine caller подаёт
команду через потокобезопасный контракт, а adapter исполняет её согласно
требованиям GLFW/event loop без выбрасывания `wrong owner thread` наружу.

### watchdog

Linux inotify и Windows implementations используют Python/`ctypes` и уже
работают через фоновые observer threads. Нужно проверить queue shutdown,
callback reentrancy и project close под 3.14t. macOS FSEvents implementation
должна проверяться отдельно, поскольку версия 6.0.0 распространяет
platform-specific wheel и не имеет заявленного `cp314t` artifact.

## Конфликт с прежними analysis-документами

Документы `2026-07-21-engine-multithreading-readiness.md` и
`2026-07-21-async-asset-pipeline.md` предлагают owner-thread mutation,
owner-thread commit и runtime assertions. Это прямо противоречит принятому
позже документу
`docs/architecture/2026-07-24-no-owner-thread-restrictions.md`.

При реализации миграции эти анализы нужно актуализировать:

- сохранить полезное разделение prepare/validate/publish;
- заменить owner-thread commit на internally synchronized transactional
  publication;
- удалить предложения creator-thread assertions и deferred execution;
- описывать ordering через versions, state machines, locks, snapshots и
  explicit completion, а не через identity потока.

## Выполненный cutover

- exact CPython 3.14.6t является единственным SDK toolchain/runtime;
- runtime dependencies ставятся из exact lock и offline wheelhouse;
- все native modules используют один free-threaded nanobind ABI;
- CMake и package metadata больше не предлагают старый Python runtime;
- launcher/editor/player/headless import graph входит в hard-fail gate;
- `termin-dispatch` предоставляет language-neutral publish/drain boundary;
- central Linux build/test и product smokes проверяют установленный SDK.

Parallel stress, TSAN и performance proof не являются условием этого cutover.
Они добавляются отдельными задачами только для подсистем, которым будет
официально разрешён конкурентный доступ.

## Критерий готовности

Переход можно считать завершённым, когда:

- bundled runtime основан на CPython 3.14t;
- все runtime и test dependencies устанавливаются из exact offline lock;
- все Termin native extensions импортируются без автоматического включения
  GIL;
- весь `./run-tests.sh` проходит в free-threaded SDK;
- launcher, editor, player и headless entry points запускаются из установленного
  SDK, editor выполняет module reload и корректно завершается;
- Linux gate и Windows build/test smoke проходят;
- engine API не вводит owner-thread/defer restrictions;
- документация фиксирует последовательный engine contract и application-owned
  dispatch.

## Вывод

Внешняя экосистема и native ABI больше не блокируют переход. CPython 3.14t
является runtime baseline, но это не декларация общей потокобезопасности
движка. Конкурентные сценарии расширяются по одному subsystem contract, когда
они действительно понадобятся приложению.
