# Готовность движка к многопоточной обработке

Дата: 2026-07-21.

Статус: архитектурный статический анализ. Документ фиксирует возможную
целевую модель и порядок миграции; он не является утверждённым планом работ.

Связанные документы:

- [Centralized frame memory](../architecture/2026-07-21-centralized-frame-memory.md);
- [Асинхронная подготовка и транзакционная публикация ассетов](2026-07-21-async-asset-pipeline.md);
- [Аудит быстродействия render frame](2026-07-18-render-performance-audit.md);
- [Аудит canonical C resource layer](2026-07-20-canonical-c-resource-layer-audit.md);
- [Аудит module hot reload](2026-07-10-termin-modules-hot-reload-audit.md).

## Резюме

Termin сейчас принципиально устроен как owner-thread engine: scene, component
lifecycle, process-global registries, Python callbacks и render orchestration
предполагают последовательный доступ. Попытка просто запускать существующие
методы из разных потоков потребует множества локальных mutex и сделает порядок
кадра недетерминированным.

Предпочтительная модель — не `multithreaded mutable engine`, а:

> один owner thread мутирует live-state; workers получают immutable snapshots
> или изолированные candidates, производят чистую подготовительную работу и
> возвращают результаты для короткого owner-thread commit.

В первую очередь имеет смысл выносить работу, которая:

- заметно дорога или блокируется на I/O;
- имеет явные входы и выходы;
- не вызывает component/Python lifecycle;
- не меняет глобальные registry и GPU state;
- допускает публикацию результата в определённой точке кадра.

Лучший первый кандидат — asset import/reload. Следом идут подготовка render
snapshots и независимое планирование draw work. Произвольный параллельный
component update, UI и мутация scene являются плохими начальными кандидатами.

## Предлагаемый контракт поточности

### Owner thread владеет live-state

Только owner thread должен:

- создавать, удалять и перестраивать entities/components;
- вызывать component, pass и widget lifecycle callbacks;
- менять process-global resource/type registries;
- публиковать новые версии ассетов и модулей;
- менять pipeline/framegraph topology;
- выполнять Python callbacks, если для конкретного callback явно не доказана
  другая политика;
- создавать и уничтожать backend-specific GPU state, если backend contract не
  разрешает иное.

Такой контракт сохраняет существующую семантику движка и локализует будущую
синхронизацию в нескольких очередях публикации вместо всех subsystem API.

### Workers работают с замкнутыми значениями

Worker job должен получать всё необходимое через явный context:

- immutable snapshot;
- copied/owned input bytes;
- handle + ожидаемую version, но не незащищённый указатель на live resource;
- worker-local scratch arena;
- cancellation/source revision;
- явный diagnostic sink.

Job возвращает owned result. Он не должен самостоятельно публиковать его в
scene или registry. Запрет `thread_local` означает, что allocator, profiler
scope, logging context и прочее worker state передаются явно.

## Кадровая модель

Целевая последовательность может выглядеть так:

```text
owner: apply completed commits at safe point
  -> collect immutable frame/view snapshots
  -> submit dependency-aware jobs
workers: cull / classify / prepare / decode / compile
  -> join or consume completed results
owner: deterministic reduction and command publication
  -> render submit
  -> advance frame epoch and reclaim retired data
```

Не вся работа обязана завершаться в том же кадре. Asset import, shader build и
tooling jobs могут жить несколько кадров. Frame-critical jobs должны иметь
явный deadline/fallback policy; незавершённая произвольная задача не должна
останавливать shutdown навсегда.

## Оценка направлений

Оценки показывают архитектурную готовность, а не гарантированный выигрыш.
Фактический приоритет должен подтверждаться профилированием.

| Направление | Готовность | Комментарий |
| --- | ---: | --- |
| Asset read/import/decode/validation | 6/10 | Есть watcher queue, import/runtime split и местами candidate/publish; live resource creation пока смешано с prepare |
| Module build/validation | 8/10 | Уже используется isolated background preparation и owner-thread live commit |
| Render item snapshot: culling/classification/sort | 5/10 | Высокий потенциальный эффект, но collection сейчас связан с scene/components/material state |
| Framegraph CPU preparation | 5/10 | Граф и pass dependencies естественно задают jobs, но сначала выгоднее компилировать статическую metadata вне hot path |
| Image/mesh/shader CPU transforms | 5/10 | Хорошо изолируются после появления пассивных prepared payloads и освобождения GIL в native bindings |
| Animation/transform evaluation | 3/10 | Возможен parallel-for по snapshot, но hierarchy, dirty propagation и component callbacks требуют разделения фаз |
| Physics | 3/10 | Внутренний solver потенциально параллелен, однако scene synchronization и callbacks должны остаться owner-owned |
| Произвольный component update | 1/10 | Нет declared read/write sets, callbacks полиморфны и могут менять любую engine state |
| Editor/UI | 1/10 | Сильно связан с Python, widget state и platform event loop |

## Наиболее перспективный render путь

Render audit выявил многократные обходы Drawable и повторную per-pass
подготовку. Это делает render preparation потенциально выгодным направлением,
но первый шаг здесь — не потоки, а единый frame/view snapshot:

1. Owner thread один раз читает scene и собирает плотный `RenderItemSnapshot`.
2. Snapshot содержит transforms, bounds, stable resource handles, phase masks
   и прочие значения, необходимые без повторного вызова компонентов.
3. Workers выполняют culling, classification, sort и построение промежуточных
   draw packets по независимым диапазонам.
4. Owner thread детерминированно объединяет packets и передаёт их backend-у.

Нельзя отправлять в worker существующий компонент и надеяться, что его
`collect`-метод окажется read-only. Для этого нужен новый контракт данных, а не
mutex вокруг старого callback API.

Параллелизм не заменяет найденные алгоритмические оптимизации: cached compiled
pipeline metadata и один scene walk полезнее распараллеливания повторной
работы.

## Взаимодействие с общей frame arena

Единая политика однокадровых allocation хорошо сочетается с jobs, но одна
разделяемая bump arena создаст contention и неопределённый lifetime. Нужна
иерархия:

```text
engine frame memory
  +-- owner frame arena
  +-- worker 0 scratch arena
  +-- worker 1 scratch arena
  +-- ...
  `-- retained/retire storage for cross-frame results
```

Worker arena выдаётся job context или закрепляется за worker slot. Результат,
который переживает join или кадр, нельзя возвращать как произвольный указатель
в scratch arena: его надо скопировать в owner destination, передать как owned
allocation либо поместить в явно retained region.

Frame memory должна иметь telemetry по subsystem/job type, high-water mark и
overflow. Иначе централизация allocation скроет, а не устранит неконтролируемое
потребление памяти.

## Инфраструктурные пробелы

До широкого внедрения jobs потребуются:

1. Небольшой engine-owned job system с dependencies, cancellation и shutdown.
2. Явное понятие owner thread и runtime-проверки запрещённых mutations.
3. Immutable snapshot/candidate contracts для первых subsystem-ов.
4. Per-worker arenas и явное владение cross-frame results.
5. Потокобезопасный diagnostic transport с сериализацией в обычный engine log.
6. Profiler events, пригодные для нескольких потоков; один глобальный stack
   scopes для этого недостаточен.
7. Детерминированные reduction/commit points.
8. Epoch/fence reclamation для данных, которыми ещё могут пользоваться CPU или
   GPU.

Process-global registries, intern tables и callback registries нельзя считать
thread-safe только потому, что отдельный leaf cache имеет mutex. По умолчанию
workers не должны к ним обращаться.

## Предлагаемая миграция

### Этап 1. Зафиксировать границы

- ввести owner-thread assertion для mutation entry points;
- определить safe points кадра;
- добавить job/result/cancellation abstractions без миграции всех систем;
- подключить per-worker scratch arenas и telemetry.

### Этап 2. Ассеты как пилот

- отделить `prepare` от `commit` в asset plugin API;
- выполнять file read/decode/validation вне owner thread;
- публиковать стабильные resource payload versions между кадрами;
- добавить stale-job rejection и dependency-aware commit batches.

Подробности вынесены в отдельный [asset analysis](2026-07-21-async-asset-pipeline.md).

### Этап 3. Render snapshot

- заменить repeated component walks единым owner-built snapshot;
- сначала использовать snapshot последовательно и проверить семантическую
  эквивалентность;
- затем параллелить culling/classification/sort;
- измерять overhead jobs на маленьких сценах и иметь grain-size threshold.

### Этап 4. Остальные pure transforms

После стабилизации job system можно переносить animation evaluation, mesh
processing и другие независимые kernels. Системы без явных data-access
contracts остаются последовательными.

## Вывод

Кодовая база не готова к свободному параллельному исполнению существующих
engine callbacks и registry operations. Она достаточно готова к более строгой
и полезной модели: owner-thread live-state плюс worker preparation над
snapshots/candidates.

Это позволяет внедрять многопоточность постепенно, сохраняет
детерминированность и не требует превращать весь Core C API в набор локально
залоченных mutable объектов.
