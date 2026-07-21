# Асинхронная подготовка и транзакционная публикация ассетов

Дата: 2026-07-21.

Статус: архитектурный анализ и набросок целевой модели. Реализация не начата.

Связанные документы:

- [Готовность движка к многопоточной обработке](2026-07-21-engine-multithreading-readiness.md);
- [Canonical C resource layer audit](2026-07-20-canonical-c-resource-layer-audit.md);
- [Centralized frame memory](../architecture/2026-07-21-centralized-frame-memory.md).

## Резюме

Asset system — один из лучших первых кандидатов для фоновой обработки. Долгие
file I/O, decode, parse, import и validation можно выполнять вне engine owner
thread, а публикацию новой версии свести к короткой операции между кадрами.

Целевая граница:

> worker строит полностью изолированный `PreparedAsset`; owner thread проверяет
> его актуальность и транзакционно публикует payload в canonical C resource.

При hot reload следует сохранять generation handle и менять content
`version`. В текущей модели Core C эти понятия уже имеют разные обязанности:

- generation определяет identity/liveness pool slot и защищает от stale handle;
- `tc_resource_header.version` обозначает изменение данных и инвалидирует
  производные GPU caches.

Создание нового generation на каждый reload сделало бы stale все сохранённые
handles. Нужна подмена payload revision под стабильным `{index, generation}`.

## Что уже подготовлено архитектурой

### Watcher отделяет ingress от owner-thread обработки

`ProjectFileWatcher` принимает watchdog events в фоновом потоке, защищает
pending queue lock-ом, а `poll()` обрабатывает изменения из main loop:

- `termin-assets/termin_assets/project_file_watcher.py:426-456`.

Это уже естественная точка, в которой вместо синхронного reload можно принять
готовые worker results и выполнить commit.

### Import и runtime plugins различаются

`termin_assets.plugin` имеет отдельные `AssetImportPlugin` и
`AssetRuntimePlugin` contracts:

- `termin-assets/termin_assets/plugin.py:21-52`.

Пока import возвращает `PreLoadResult`, а runtime plugin сразу регистрирует или
перезагружает live asset. Граница достаточно ясна, чтобы развить её до
`prepare/commit`, не меняя весь внешний asset API.

### Candidate/publish уже появился в pipeline asset

`PipelineAsset` разделяет `_prepare_candidate()` и `_publish_candidate()`:

- `termin-default-assets/python/termin/default_assets/render/pipeline_asset.py:138`;
- `termin-default-assets/python/termin/default_assets/render/pipeline_asset.py:307`.

Это полезный прототип failure policy: неудачная подготовка не должна портить
текущий pipeline. Однако candidate пока не изолирован: десериализация обращается
к resource manager и создаёт runtime pipeline/pass objects.

## Почему существующий reload нельзя просто вызвать в worker

Текущие пути подготовки и публикации смешаны.

`DataAsset._load_content()` парсит данные, сразу записывает их в asset и вызывает
post-load hook. При ошибке он пытается восстановить предыдущее Python state, но
это не является общей транзакцией для C registries и зависимых ресурсов:

- `termin-assets/termin_assets/data_asset.py:126`.

Texture parsing создаёт `TcTexture`, то есть касается canonical runtime storage.
`tc_texture_set_data()` затем выделяет буфер, освобождает прежний, меняет поля
живого объекта и увеличивает version:

- `termin-graphics/src/resources/tc_texture_registry.c:402-434`.

Mesh API отдельно заменяет vertices, indices и submeshes; каждая операция
увеличивает version. Ошибка посередине такой последовательности способна
оставить смешанное состояние.

Shader reload после публикации синхронно обновляет материалы и при изменении
интерфейса перезагружает зависимые pipelines. Эта цепочка предполагает доступ
к live resource manager и определённый порядок mutations.

Наконец, C resource pools, UUID maps, intern storage и Python asset registries
не имеют общего concurrent-mutation contract. Добавление mutex в один GPU cache
не делает весь путь thread-safe.

## Целевой plugin contract

Условный контракт может выглядеть так:

```python
class AssetPreparePlugin(Protocol):
    def prepare(self, request: AssetPrepareRequest) -> PreparedAsset | Failure:
        ...

class AssetCommitPlugin(Protocol):
    def commit(self, context: AssetCommitContext, candidate: PreparedAsset) -> CommitResult:
        ...
```

`AssetPrepareRequest` должен содержать owned/immutable входы:

- canonical source path и UUID;
- source revision/fingerprint;
- содержимое файла или право прочитать конкретный snapshot;
- import settings;
- dependency descriptors с ожидаемыми versions;
- cancellation token и diagnostic context.

`PreparedAsset` должен:

- владеть всеми буферами результата;
- иметь явный destroy/deleter path;
- не содержать borrowed pointers на live assets;
- не быть зарегистрированным в process-global pool;
- содержать полный набор данных для короткого commit;
- быть безопасным для уничтожения без owner-thread publication.

## Prepared payloads в Core C

Для resource types полезны пассивные структуры, не являющиеся registry entries:

```c
typedef struct tc_prepared_texture {
    void* pixels;
    size_t pixels_size;
    uint32_t width;
    uint32_t height;
    uint8_t channels;
    uint8_t format;
    /* import metadata and owned strings as needed */
} tc_prepared_texture;

bool tc_texture_commit_prepared(
    tc_texture_handle target,
    tc_prepared_texture* candidate
);
```

Worker может декодировать изображение и заполнить `tc_prepared_texture`, но не
вызывать `tc_texture_declare`, `tc_texture_set_data` или UUID-map operations.

Для composite resources желательно заменить набор независимых setters одной
полной заменой payload:

```c
typedef struct tc_mesh_payload {
    void* vertices;
    uint32_t* indices;
    tc_submesh* submeshes;
    size_t vertex_count;
    size_t index_count;
    size_t submesh_count;
    tc_vertex_layout layout;
} tc_mesh_payload;
```

Commit меняет payload один раз и один раз увеличивает `header.version`. На
первом этапе это не обязана быть lock-free atomic pointer operation: если
workers не читают live resources, достаточно гарантировать owner-thread safe
point.

## Generation, version и source revision

Это три разных счётчика:

| Значение | Что означает | Когда меняется |
| --- | --- | --- |
| Handle generation | Жизнь identity в pool slot | Destroy и повторное использование slot |
| Resource version | Опубликованная версия payload | Успешный commit нового содержимого |
| Source revision/request token | Актуальность фоновой работы | Каждое принятое изменение source |

На reload generation остаётся прежним. Version меняется только после полного
успеха. Source revision позволяет отбросить устаревший job, даже если он
завершился позже нового.

## Очередь и commit point

```text
watchdog events
  -> debounce/coalesce by canonical source
  -> assign source revision
  -> prepare queue
  -> worker read/decode/parse/validate
  -> completed candidate queue
  -> owner-thread validation at frame boundary
  -> dependency-ordered commit batch
  -> reload notifications
  -> retire old CPU/GPU payloads
```

Предпочтительный safe point — начало logical frame до построения scene/render
snapshot. Тогда весь кадр видит либо старую, либо новую согласованную версию.
Не следует применять commits между отдельными passes одного framegraph.

Первоначальная регистрация, reload, rename и removal должны проходить через ту
же owner-owned commit queue. Иначе появятся два режима с разными гарантиями.

## Зависимости и пакетные транзакции

Одиночный asset reload недостаточен для цепочек вида:

```text
shader -> material -> pipeline
texture -> material
mesh/material -> prefab or scene-derived data
```

Candidate должен записывать dependency UUIDs и versions, против которых он был
подготовлен. Перед commit owner проверяет stamps:

- если source revision устарел, candidate уничтожается;
- если dependency version изменилась, candidate переподготавливается либо
  откладывается;
- если все stamps совпадают, candidates публикуются в топологическом порядке;
- notifications отправляются только после успеха всего согласованного batch.

Для batch, который затрагивает несколько live resources, нужны либо rollback
records, либо двухфазная схема: сначала полная validation/reservation, затем
набор неотказных pointer swaps. Второй вариант предпочтительнее.

Неудачный import обязан оставить текущую опубликованную версию рабочей и
выдать полноценную diagnostic. Нельзя сначала инвалидировать asset, а затем
надеяться успешно построить замену.

## Reclamation

### CPU payload

Если workers никогда не получают pointers на live resource payload, старые CPU
данные можно освободить после owner-thread commit. Более гибкая модель — retire
queue по frame epoch, особенно если позднее появятся snapshots, удерживающие
payload несколько кадров.

Prepared candidates не являются однокадровыми данными: job может завершиться
через несколько кадров. Их нельзя размещать в обычной frame arena без
retention contract. Допустимы owned allocation, cross-frame arena/region или
перенос в commit-owned storage.

### GPU payload

После bump `header.version` backend cache создаёт новое GPU-представление. Старое
может всё ещё использоваться уже отправленным command buffer.

Vulkan backend уже имеет frame-slot/fence deferred destruction:

- `termin-graphics/include/tgfx2/vulkan/vulkan_render_device.hpp:194-233`;
- version-aware texture replacement находится в
  `termin-graphics/src/tgfx2/vulkan/vulkan_tc_bridge.cpp:143-187`.

Эту семантику следует оформить как общую backend guarantee: новый кадр больше
не получает старый handle, но фактическое уничтожение происходит только после
завершения всех использующих его GPU submissions.

## Python и количество workers

Asset orchestration и многие importers написаны на Python. Большой Python
thread pool сам по себе не даст пропорционального CPU speedup из-за GIL.

Например, native `decode_rgba8` сейчас вызывается binding-ом без явного
`nb::gil_scoped_release`:

- `termin-image/python/bindings/image_module.cpp:26-66`.

Рациональный порядок:

1. Один asset worker для I/O, hashing, coalescing и подготовки там, где это уже
   безопасно.
2. Native CPU-heavy bindings освобождают GIL и принимают/возвращают пассивные
   values.
3. Небольшой worker pool обрабатывает независимые candidates.
4. Python-heavy либо потенциально аварийные importers могут исполняться в
   subprocess, как уже делается для module build/validation.
5. GPU upload/compile проходит через отдельную owner/render-thread budgeted
   queue.

Один worker уже убирает blocking I/O из кадра и проверяет архитектурный
контракт. Размер пула имеет смысл подбирать после измерения queue latency и
длительности jobs.

## Что не следует делать

- Не вызывать существующие `Asset.reload()` и registry setters напрямую из
  worker thread.
- Не делать все C registries конкурентными ради одного сценария.
- Не использовать generation bump как content reload.
- Не публиковать каждый независимо завершившийся dependency без проверки
  batch consistency.
- Не хранить cross-frame candidate в обычной однокадровой arena.
- Не выполнять GPU upload или shader module creation в произвольном worker без
  явной backend-wide гарантии.
- Не скрывать неудачный reload: live version сохраняется, но ошибка обязательно
  логируется и видна tooling/UI.

## Предлагаемая миграция

### Этап 1. Асинхронный preload без runtime mutations

- ввести source revision и completed-result queue;
- вынести file read, hashing и безопасный parsing;
- commit существующего `PreLoadResult` оставить на owner thread;
- измерить stalls, queue depth, discarded stale jobs и memory high-water.

Это даст ограниченный выигрыш, но проверит lifecycle, cancellation и shutdown.

### Этап 2. Prepared texture как вертикальный срез

- добавить пассивный decoded texture payload;
- не создавать `TcTexture` в worker;
- добавить owner-thread `commit_prepared` под стабильным handle;
- проверить version invalidation на Vulkan, OpenGL и D3D11;
- покрыть repeated save, failed decode, delete-during-load и shutdown.

Texture удобна как первый тип: зависимости минимальны, а decode и upload хорошо
видны в профиле.

### Этап 3. Mesh и shader candidates

- сделать целостную замену mesh payload;
- разделить shader source preprocessing/compile artifact и runtime/GPU commit;
- ввести dependency stamps и rejection устаревших результатов.

### Этап 4. Dependency transaction

- строить commit graph для shader/material/pipeline chains;
- выполнять validate/reserve до публикации;
- отправлять события после завершения batch;
- добавить epoch/fence reclamation и budgeted GPU warming.

### Этап 5. Унификация plugin API

После проверки нескольких asset types заменить монолитный runtime reload
общим prepare/commit contract. Не следует сначала проектировать универсальную
иерархию candidates без работающих вертикальных срезов: texture и shader
покажут необходимые различия владения.

## Критерии готовности

- Worker не касается live resource/type registries.
- Один logical frame видит согласованный набор asset versions.
- Старый/отменённый job не может затереть новый.
- Failed candidate не меняет live asset и оставляет diagnostic.
- Handle identity сохраняется при reload; version меняется ровно один раз на
  commit.
- Dependency batch не публикует частичное состояние.
- Shutdown отменяет или дожидается jobs по явной политике и освобождает все
  candidates.
- CPU и GPU old payloads уничтожаются только после завершения читателей.
- Поведение одинаково проверено на поддерживаемых graphics backends.
- Telemetry показывает prepare time, queue delay, commit time, stale rejects и
  retained memory.

## Вывод

Асинхронная asset preparation хорошо соответствует существующему направлению
Core C resource layer. Для неё не требуется делать live engine state свободно
многопоточным. Напротив, строгая owner-thread публикация позволяет сохранить
простые C structs, stable generation handles и детерминированный кадр.

Основная архитектурная работа состоит не в запуске `reload()` в другом потоке,
а в создании пассивных prepared payloads, source/dependency revisions,
неотказного commit и корректного reclamation.
