# RenderItem collection: разбор направления #2900

## Что измерено

После #2898/#2899 (`c868998c5`) Drawable collection остаётся отдельной ценой:
1.517 мс за три target collections в фиксированном CargoTerminal кадре.
В том же A/B-прогоне соседние варианты дают 1.447 и 1.538 мс. Эта секция
не включает static batching, bounds/phase index и draw submission.
Источник: [профиль](2026-10-07-skinned-bounds-and-static-batching.json).

До batching три collections имеют 849, 22 и 1039 input geometry groups;
batch-eligible — 830, 10 и 840. Суммарные 1680/1910 (88%) отражают
пригодность для batching, **не неизменяемость** этих объектов. Отдельные
producer counts и времена стадий этим замером не снимались.

В основном target подтверждены 168 skinned object/geometry pairs и 336
items для двух phases. На их emitted items приходится 22692 bone matrices,
то есть 363072 float entries при текущей упаковке. Это подсчёт по snapshot
identities и коду, не отдельный замер затрат skinning в миллисекундах.

## Конкретные повторы в коде

`MeshRenderer::collect_render_items` (mesh_renderer.cpp:733) лениво вычисляет
model один раз, затем вызывает `populate_mesh_render_item` для каждого
submesh × material phase. Skinned override каждый раз обновляет skeleton
в пространстве этого renderer и копирует все bone matrices в float buffer
(skinned_mesh_renderer.cpp:69,109).

`SkeletonController::update_skeleton_instance` каждый раз выделяет локальный
vector для bone world matrices (skeleton_controller.cpp:296).
`get_bone_matrix(i)` синхронизирует SkeletonInstance на каждой кости;
существующий `get_bone_matrices_float(out)` делает это один раз для всего
buffer (graphics/termin-skeleton/src/skeleton_instance.cpp:321,350).

Model transform уже имеет dirty world-affine cache. Предположение, что каждый
collection заново вычисляет всю transform hierarchy, неверно. Стандартный
MeshRenderer здесь прикрепляет material/phase handles и pointers; подготовка
material resources и uniform upload относятся к последующему submission.

Другой кандидат: `scene_render_execution.cpp:30` создаёт snapshots локально
для каждого execution. Их buffers уничтожаются после вызова, хотя collection
поддерживает clear с сохранением capacity. Хранение scratch storage между
вызовами может убрать аллокации при сохранении полного свежего сбора данных.
Нужно отдельно измерить эту долю, учесть reentrancy/несколько targets и очищать
payload owners после execution, не удерживая старое содержимое как cache.

## Рекомендуемый порядок

1. Разделить измерения: traversal/producer вызовы; emitted items и phase visits;
   model preparations; skin preparations/controller updates/processed bones;
   sink copying и allocations. Временные probes выполнять отдельно от общего
   CPU-профиля либо оценивать накладные расходы инструментирования.
2. Первым ограниченным экспериментом готовить skinning payload лениво один раз
   за вызов штатного `collect_render_items`, затем прикреплять его ко всем items.
   Использовать существующий bulk float copy и retained world-matrix scratch.
   При отсутствии items подготовка не нужна. Прямой collect без prepare_render
   должен продолжать работать; нельзя зависеть от enabled SkeletonController.
3. Проверить эффект и затем отдельно оценить reuse capacity snapshots. Результат
   должен сохранять order/phases/model/bone matrices, draw counts и картинку
   при multi-submesh/multi-phase, разных renderer roots, animation/rewind,
   прямых collections и разных target masks/cameras. Custom C/Python producers
   продолжают вызываться с прежним контекстом.
4. Решать вопрос о shared preparation между targets по оставшемуся breakdown.
   Persistent static contents требуют полноценного producer contract и
   проверяемой инвалидации; оснований вводить его сейчас недостаточно.

## Почему срок reuse следует ограничить одним collection

Snapshot уже собирается один раз на target и доступен всем его passes.
Каждый target передаёт собственные primary camera, masks и debug name;
произвольный producer вправе учитывать их. Category mask обрабатывается самим
producer. Callbacks не имеют контракта pure; например WorldText меняет uniform
в phase при collection. Одинаковых masks недостаточно для общего cache.

Skinning matrices заимствованы из изменяемого renderer vector, material phase
является pointer, scene adapter_data содержит сырой component pointer. Sink
копирует line/text/foliage payloads, но не все эти данные и не удерживает обычные
mesh/material resources. Комментарий collection «Owns every borrowed payload»
шире фактического владения. Текущий synchronous execution не даёт основания
продлевать lifetime таких snapshots на другие кадры.

Нет render epoch или полной producer revision. Render-request bool — scheduling,
а resource versions не покрывают transforms, кости, renderer fields, removal,
arbitrary Python state и rewind. Один SkeletonController может обслуживать
renderers с разными roots: его итоговые renderer-local matrices нельзя шарить
между ними без root-aware подготовки. Даже per-frame sharing требует явной
границы состояния сцены, внутри которой render callbacks не меняют её.

Первый выбранный эксперимент реализован в #2902. Измерения показали collection
1.48 → 0.95–0.97 мс, preparation calls 336 → 168 и scratch allocations 336 → 0;
картинка и bone/item fingerprints совпали. Подробный breakdown и вывод об общем
cache приведены в [итоговом отчёте](2026-10-07-skinning-collection.md).
