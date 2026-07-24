# Готовность Termin к free-threaded Python

Дата: 2026-07-24.

Статус: статический анализ зависимостей и Python/C++ boundary. Миграция не
начата.

Связанные документы:

- [Запрет owner-thread restrictions](../architecture/2026-07-24-no-owner-thread-restrictions.md);
- [Готовность движка к многопоточной обработке](2026-07-21-engine-multithreading-readiness.md);
- [Асинхронная подготовка ассетов](2026-07-21-async-asset-pipeline.md);
- [Аудит использования NumPy](2026-07-07-numpy-usage-inventory.md).

## Резюме

Переход Termin на free-threaded CPython технически реалистичен. Большинство
внешних runtime-зависимостей уже совместимы с Python 3.14t либо требуют
обычного обновления версии. Основной блокер находится внутри Termin:

- SDK использует CPython 3.10, в котором free-threaded build отсутствует;
- `termin-nanobind-sdk` намеренно отвергает параметр `FREE_THREADED`;
- около 40 native-модулей Termin должны быть пересобраны в одном согласованном
  free-threaded ABI;
- глобальные callback registries и другое process-global mutable state местами
  полагаются на неявную сериализацию GIL;
- нет систематического parallel stress/TSAN-покрытия Python/C++ boundary.

Free-threaded Python не делает движок автоматически потокобезопасным. Он лишь
убирает глобальную сериализацию Python bytecode. Корректность общего mutable
state после этого должна обеспечиваться внутренней синхронизацией,
immutable/copy-on-write snapshots, транзакционными публикациями и явным
владением данными.

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

1. Python runtime выбирается как обычный CPython или CPython 3.14t.
2. SDK строит `libnanobind.so` либо отдельный `libnanobind-ft.so`.
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

## Native-код, который нельзя просто объявить безопасным

`FREE_THREADED` является обещанием потокобезопасности, а не способом её
получить. В binding layer уже видны process-global mutable containers:

- `g_animation_python_callbacks`;
- `g_navmesh_load_callbacks`;
- callback registry в mesh bindings;
- `g_skeleton_python_callbacks`;
- `g_texture_python_callbacks`;
- глобальный `nb::callable` в `tcbase`;
- `g_ptr_extractors` в inspect bindings;
- input device registry и несколько collision scratch buffers.

Для каждого такого объекта требуется определить:

- является ли состояние immutable после module initialization;
- допускаются ли concurrent read/write и iteration;
- кто владеет содержащимися Python objects;
- как выполняются clear/reload/shutdown;
- может ли callback удалить или заменить текущую запись reentrantly.

Допустимые решения:

- immutable snapshot с atomic publication;
- mutex/reader-writer lock внутри owning subsystem;
- copy-on-write registry;
- request-local state, передаваемый явным context;
- транзакционный prepare/validate/publish с version validation.

Недопустимые решения:

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

## Предлагаемая программа миграции

### Этап 1. Отдельный 3.14t SDK profile

- добавить выбор free-threaded CPython runtime;
- обновить NumPy и test-only SciPy до версий с `cp314t` wheels;
- проверить exact offline lock и wheelhouse для Linux и Windows;
- добавить platform inventory для macOS, если она входит в поддерживаемые
  targets;
- запускать pure-Python import/test smoke до native opt-in.

### Этап 2. Free-threaded nanobind build

- научить `termin-nanobind-sdk` строить отдельный `FREE_THREADED` shared
  runtime;
- передать режим всем `nanobind_add_module` централизованно;
- запретить смешение ABI на configure/package validation;
- импортировать все extensions в smoke-процессе и проверять, что GIL не
  включился.

### Этап 3. Аудит и исправление native state

- инвентаризировать global/static mutable state;
- отдельно проверить callback registries и Python object lifetime;
- устранить зависимость корректности от GIL;
- добавить явные synchronization/immutable publication contracts;
- проверить reload, shutdown и destruction under contention.

### Этап 4. Parallel correctness gates

- прогонять Python tests в нескольких потоках через подходящий parallel test
  runner;
- добавить targeted stress tests для registries, asset loading, scene
  serialization, callbacks и module reload;
- собрать CPython и native modules с TSAN в отдельном диагностическом profile;
- проверять повторяемость shutdown и отсутствие hangs/use-after-free;
- логировать автоматическое включение GIL как hard failure.

### Этап 5. Performance validation

- сравнить ordinary CPython 3.14 и 3.14t на одинаковых сценариях;
- снять GLB/scene load profile при 1, 2, 4 и 8 asset jobs;
- отделить Python scheduling, NumPy/native kernels, IO и publication;
- не принимать миграцию только по synthetic benchmark: нужны editor scene
  load и hot reload scenarios.

## Критерий готовности

Переход можно считать завершённым, когда:

- bundled runtime основан на CPython 3.14t;
- все runtime и test dependencies устанавливаются из exact offline lock;
- все Termin native extensions импортируются без автоматического включения
  GIL;
- весь `./run-tests.sh` проходит в free-threaded SDK;
- parallel stress и TSAN gates не находят гонок на поддерживаемых сценариях;
- editor открывает representative projects, загружает GLB assets, выполняет
  reload и корректно завершается;
- engine API не вводит owner-thread/defer restrictions;
- профили подтверждают реальный параллелизм Python asset jobs и отсутствие
  регрессии однопоточного editor workload.

## Вывод

Внешняя экосистема переход не блокирует. PyYAML уже имеет 3.14t artifacts,
NumPy и SciPy требуют обновления, а `ctypes`-обвязки не зависят от CPython
extension ABI.

Главная работа — сделать free-threaded весь native boundary Termin:
согласованно перестроить nanobind runtime и extensions, заменить неявную
защиту GIL настоящими контрактами состояния и доказать корректность
параллельными тестами. Включение `FREE_THREADED` до такого аудита было бы
ложной декларацией безопасности.
