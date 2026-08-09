# Native cgltf Importer

Дата: 2026-08-09

Статус: Accepted

## Контекст

`termin-glb` сейчас читает GLB/glTF в Python, создаёт NumPy-представления
accessors, а затем выполняет exact deduplication через Python `dict[tuple]` для
каждого исходного индекса. На профиле `Glitch.glb` эта стадия занимает около
2.12 s из 2.29 s loader time. Geometry-only Pixal3D содержит 2,823,922
исходные вершины и 17,280,924 индекса, поэтому Python per-index path становится
непригоден для generated assets этого масштаба.

Отдельный benchmark сравнил cgltf и fastgltf на geometry-only и textured
Pixal3D, а также на skinned/animated Arthur. Обе библиотеки дали одинаковые
canonical geometry/material/texture/rig hashes. cgltf показал меньшее полное
время parse + Termin mesh build, меньший peak RSS и позволяет держать GLB BIN
chunk как view поверх read-only mapping вместо обязательной полной копии.

Параллельный `Asset.ensure_loaded()` не является действующим контрактом Termin.
Ускорение GLB не должно вводить locks, внутренний scheduler или параллельную
публикацию process-wide resource registries.

Существующий `tc_mesh_set_data()` копирует готовые vertex/index buffers. Если
native importer сначала соберёт собственный полный буфер, такой API временно
удвоит owned geometry и не позволит достигнуть требуемого memory profile.

## Решение

`termin-glb` получает нативный C++ backend на cgltf. Он является владельцем
много-доменного glTF import contract и не переносится в `termin-app`, renderer
или graphics backend.

- cgltf закрепляется как отдельная pinned third-party dependency. Репозиторий
  зависимости может указывать на upstream либо на Termin-owned fork; выбор URL
  не меняет adapter API. Локальные изменения cgltf допустимы только как
  небольшие, документированные и upstreamable patches, а engine-specific
  conversion остаётся в `termin-glb`.
- Production GLB path остаётся последовательным: parse, discovery, подготовка
  CPU resources и детерминированная публикация. Concurrency asset loading
  является отдельным будущим решением.
- GLB path использует read-only file mapping. Mapping и `cgltf_data` живут до
  завершения всех accessor reads и освобождаются после переноса данных в owned
  Termin resources.
- `termin-mesh` предоставляет checked transactional mesh-data builder/commit
  API. Память vertices, indices и submeshes выделяется owning mesh module,
  заполняется importer-ом и атомарно передаётся целевому уже объявленному
  `tc_mesh`. Ошибка не оставляет частично обновлённый resource и не требует
  второй полной копии.
- Native document сначала раскрывает компактную структуру сцены и имена
  ресурсов. `GLBAsset` создаёт или разрешает embedded child assets и их UUID,
  после чего native backend строит meshes непосредственно в соответствующие
  declared resources.
- Один glTF mesh по возможности остаётся одним Termin mesh. Primitives
  конкатенируются без deduplication, indices получают vertex-base adjustment,
  draw sections сохраняются как `tc_submesh`. Для разных наборов attributes
  выбирается совместимый существующий superset layout с нулевой инициализацией
  отсутствующих полей.
- Y-up to Z-up conversion для geometry выполняется во время native unpacking.
  Nodes, skins и animation data проходят ту же явно выбранную conversion policy,
  поэтому опубликованный mesh и scene metadata не расходятся.
- Parser не генерирует normals/tangents и не меняет topology неявно. Такие
  операции остаются отдельными управляемыми стадиями.
- Ошибочные и unsupported assets возвращают structured diagnostics. Production
  backend не делает автоматический fallback на Python после cgltf error.
- Во время миграции backend можно выбрать явно для differential tests. JSON
  `.gltf` может временно оставаться на Python backend, пока его external buffer
  и URI contract не перенесён намеренно.

## Обоснование

cgltf уже проверен на реальных данных Termin и лучше соответствует требуемой
memory model. Он мал, имеет MIT license и отделяет parser от engine adapter.
Возможность собственного fork полезна для оперативных fixes, но vendoring
engine-specific поведения внутрь parser затруднил бы обновления и тестирование.

Двухфазный document/discovery/build contract сохраняет существующие embedded
asset UUID и lazy-loading model. Прямое создание анонимных meshes во время
parse привело бы к конфликту с уже объявленными child assets; возврат больших
NumPy arrays в Python сохранил бы лишние копии и старую границу владения.

Transactional mesh publication является необходимой foundation, а не
оптимизацией после внедрения: она закрывает overflow, allocation rollback,
atomic replacement и peak-memory contract одновременно.

## Рассмотренные альтернативы

### Оставить Python loader и только vectorize deduplication

Отвергнуто. Deduplication не требуется для корректного glTF indexed geometry,
а Python/NumPy path всё равно сохраняет промежуточные attribute arrays,
interleaved buffer и последующую копию в `tc_mesh`.

### Использовать fastgltf

Отвергнуто для текущей миграции. На проверенных fixtures он корректен, но
создаёт дополнительную копию GLB BIN chunk, использует больше RSS и проигрывает
cgltf по полному import path.

### Строить временный native buffer и вызывать `tc_mesh_set_data()`

Отвергнуто для production path. Это даёт лишнюю полную копию geometry и не
обеспечивает атомарную публикацию submeshes вместе с vertex/index data.

### Сразу сделать concurrent asset loading

Отвергнуто как несвязанный scope. Главный измеренный hotspot локален GLB
prepare, а resource registries и `Asset.ensure_loaded()` пока имеют
последовательный контракт.

### Автоматически откатываться на Python loader

Отвергнуто. Такой fallback скрывает parser regressions и unsupported features.
Старый backend используется только явным выбором на ограниченном переходном
этапе.

## Последствия и риски

- `termin-glb` становится CMake-модулем с native library/binding и записью в
  SDK native-extension manifest.
- `termin-mesh` получает новый ownership-transfer contract, который требует
  C/C++ unit tests, включая overflow и allocation/validation rollback.
- Public Python `GLBSceneData` нельзя считать вечным storage contract для
  больших geometry arrays. Runtime loading использует native document/payload;
  tooling extraction при необходимости материализует arrays явно.
- Текущая Python-генерация normals/tangents меняет поведение отсутствующих
  attributes. Переход должен иметь fixtures, которые явно закрепят выбранную
  policy, прежде чем native backend станет default.
- Primitive modes, sparse accessors, normalized integer attributes, strides и
  extension selection должны либо поддерживаться по спецификации, либо
  завершаться диагностикой с mesh/primitive/accessor context.
- Собственный cgltf fork увеличивает maintenance burden. Каждый fork-only patch
  обязан иметь причину, test и отслеживаемую связь с upstream revision.

## Последующая работа

1. Реализовать checked transactional mesh-data builder и atomic commit.
2. Закрепить cgltf и добавить native `termin-glb` build/binding skeleton.
3. Реализовать mmap GLB document и static mesh import с submeshes.
4. Перенести materials, images, samplers и `EXT_texture_webp` metadata.
5. Перенести nodes, skins и animations без per-element binding calls.
6. Выполнить differential, invalid-input, repeated load/unload и memory tests,
   затем сделать cgltf backend default и отдельно удалить старый тяжёлый path.

## Ссылки

- Kanboard: #776 и связанные implementation cards.
- `termin-glb/python/termin/glb/loader.py`.
- `termin-glb/python/termin/glb/asset.py`.
- `termin-glb/python/termin/glb/instantiator.py`.
- `termin-mesh/src/resources/tc_mesh_registry.c`.
- `/home/mirmik/project/Hunyuan3D-Omni-test/gltf_loader_benchmark`.

