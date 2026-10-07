# Skinning collection: #2900 / #2902

## Результат

Выбранная локальная оптимизация уменьшила Drawable collection примерно на
0.52 мс (35%) в фиксированном CargoTerminal кадре. Изображение, фактические
model/bone matrices, phases, item order и draw counts совпали.

| Чистый CPU-профиль, мс/кадр | Old A | New A | New B | Old B |
| --- | ---: | ---: | ---: | ---: |
| Drawable collection, 3 calls | 1.475 | 0.966 | 0.953 | 1.477 |
| RenderItem publish, 3 calls | 2.077 | 1.579 | 1.567 | 2.071 |
| Static batching, 3 calls | 0.556 | 0.566 | 0.566 | 0.548 |
| CPU Render | 8.878 | 8.351 | 8.344 | 8.736 |
| Active frame | 10.361 | 9.842 | 9.830 | 10.198 |
| Encode mesh draw calls | 1535 | 1535 | 1535 | 1535 |

## Изменение и контракт

`MeshRenderer::collect_render_items` вызывает новый preparation hook лениво
один раз перед первым item. Существующий populate hook по-прежнему вызывается
для каждого submesh/material phase. Штатный SkinnedMeshRenderer вычисляет
renderer-local skinning payload в preparation hook, а populate лишь прикрепляет
его. Empty collection и material enumeration skinning не готовят.

Матрицы копируются существующим `SkeletonInstance::get_bone_matrices_float`:
одна синхронизация вместо вызова `get_bone_matrix` для каждой кости.
SkeletonController заново заполняет retained world-matrix scratch для каждого
update. Capacity сохраняется, содержимое пересчитывается.

Reuse ограничен одним collection. Каждый следующий вызов получает текущую
позу и свой renderer root, в том числе при движении времени назад. Direct
collection без prepare_render и с disabled controller работает. Ошибка
обновления/копирования логируется и очищает прежнее bone payload состояние.
Custom C/Python callback contracts и per-item C++ populate hook сохранены.

Skin matrices остаются заимствованными из renderer buffer для synchronous
execution. Этот фикс не вводит межкадровое владение snapshots, общий frame epoch
или shared renderer-local matrices между разными roots. Resource versions
не объявляются полной инвалидацией произвольного producer.

## Отдельный instrumented breakdown

Средние последних 120 публикаций каждого target; producer timings исключают
sink. Они включают overhead probe и не являются чистым CPU benchmark выше.

| Target | Producer calls | Items до batching | Snapshot items | Skinned items |
| --- | ---: | ---: | ---: | ---: |
| FovHalfTarget | 14 | 44 | 42 | 0 |
| FovTarget | 505 | 1679 | 637 | 0 |
| chronosquad | 708 | 2059 | 1015 | 336 |
| Всего | 1227 | 3782 | 1694 | 336 |

Counts одинаковы до и после. Native callback timing покрывает все producers
в этих captures. Неактивные custom producers также вызываются и могут выдавать
ноль items; они не исключались ради замера.

| chronosquad, на publication | Old | New |
| --- | ---: | ---: |
| Skin payload preparations / bone updates | 336 | 168 |
| Processed bone matrices | 22692 | 11346 |
| Controller updates внутри collection | 336 | 168 |
| World-matrix scratch allocations | 336 | 0 |
| Skinned producer без sink, мс | 0.932 | 0.385 |
| Bone update, мс (вложенный) | 0.891 | 0.348 |
| Controller update, мс (вложенный) | 0.678 | 0.316 |

Последние три строки вложены; их нельзя складывать. Allocation counter учитывает
старый local vector reserve / рост capacity нового scratch, а не все process
allocations. Baseline `prepare_calls=168` считает пустой новый shim hook, не
настоящую подготовку; её счётчик — `bone_update_calls`.

| Instrumented collection, сумма 3 targets, мс | Old | New |
| --- | ---: | ---: |
| Весь collect | 1.673 | 1.113 |
| Producer callbacks без sink | 1.198 | 0.649 |
| Известный sink time | 0.326 | 0.317 |
| Остаток после callbacks и sink | 0.150 | 0.147 |

Остаток включает traversal, adapter setup и overhead instrumentation.
Обычные MeshRenderer дают 980 callbacks и 3408 emitted items: без sink около
0.167 мс до и 0.165 мс после. Это не означает неизменяемость объектов.
HearingIndicatorController даёт около 0.084 мс в двух collections при нулевом
числе emitted items. Остальные producer types и времена сохранены в JSON.

## Вывод исследования #2900

Основной найденный повтор был внутри skinning collection: он не требовал
всеобщего RenderItem cache. Для текущего кадра skinned producers присутствуют
только в главном target. Общий cross-target static cache не устраняет всю
оставшуюся цену: обычные MeshRenderer callbacks занимают около 0.17 мс во всех
targets, плюс остаются sink/traversal и динамические producers.

Persistent static contents сейчас не обоснованы измеренным выигрышем и требуют
producer ownership/invalidation contract, описанного в
[предварительном разборе](2026-10-07-render-item-collection-review.md).
Номер кадра, render-request bool и static_batching flag этим контрактом не
являются. Capacity-only reuse snapshot storage остаётся отдельным кандидатом;
его allocation cost этим probe не изолирован, внедрение здесь не выполнялось.
Дальнейшее расширение следует выбирать по новым замерам оставшегося bottleneck.

## Метод и проверки

Base `c868998c5`; новый SDK собран штатным offline `task build`. Один отдельный
агентский редактор, Vulkan offscreen 1600×1000, viewport 1052×614. Step/time=0,
Arthur selected, 39 animation players на clip time 0, projections скрыты,
editor display выключен. Сцена/проект не сохранялись; редактор закрыт штатно.

Временный LD_PRELOAD probe переключает сохранённые старые тела member methods,
скомпилированные против нового ABI, и RTLD_NEXT production implementation.
Он не установлен в SDK и не входит в repo. Baseline получает дополнительный
пустой lazy hook; это небольшой overhead сравнения. CPU-профиль снят в порядке
old/new/new/old, по 120 прогретых кадров; detailed clocks/maps/counters/hashing
выключены. Отдельные instrumented windows дают breakdown и fingerprints.

Fingerprints models/bones/phases/order стабильны на всех 120 publications
каждого target и совпадают между режимами. RGB viewport совпадает пиксель
в пиксель (645928 pixels). Это smoke одного fixed-state кадра; runtime pose/root,
rewind-like changes и error recovery проверяются native regressions.

Известные legacy TransparentShader/TimeSpirit errors (#2232) и transient RingUBO
overflow (#2300) повторились до профилирования; эта работа их не исправляет.
GPU speedup не измерялся.

Native regressions покрывают две bones, два submeshes, две phases, one preparation,
fresh/backwards pose, different/shared roots, disabled controller, empty/missing
phase, sink refusal/retry, invalid bone mapping и восстановление.

`task test`: native **268/268 passed**, Python **3687 passed**, один прежний
GLB failure #2885 (degenerate/non-finite tangent at vertex0). Также lint нашёл
B023 в существующем navmesh-тесте: callback не связывал loop variables.
Привязка исправлена default arguments; последующие `task lint:python` и
`task test:python -- physics/termin-navmesh/tests/test_navmesh_display_component.py`
прошли (3 tests). `git diff --check` прошёл. GLB runtime код не менялся.

[Полные данные](2026-10-07-skinning-collection.json),
[viewport до](skinning-collection-2026-10-07/old_a.png),
[viewport после](skinning-collection-2026-10-07/new_a.png).
Логи: `/tmp/termin-2900/{build.log,test.log,editor.log}`.
