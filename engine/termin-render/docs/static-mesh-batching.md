# Static mesh batching

`MeshRenderer.static_batching` — сериализуемая opt-in настройка (также Inspector
и Python API). Она разрешает объединение неподвижной геометрии; исходные entities,
components и colliders остаются отдельными. По умолчанию настройка выключена.

`RenderingManager` владеет `StaticMeshBatchCache`. Scene adapter передаёт его в
`TcSceneRenderItemSource`, который заменяет совместимые RenderItems до публикации
immutable snapshot и построения phase buckets. Standalone callers могут передать
свой cache в source или `render_scene_pipeline_offscreen`; глобального кэша нет.
Snapshot удерживает merged TcMesh, поэтому пересборка следующего snapshot не
уничтожает геометрию, ещё используемую предыдущим.

## Группировка и жизненный цикл

Объединяются треугольные submeshes по ячейкам 8×8×8 метров, материалу, набору
материальных фаз, vertex layout, component phase mask и настройкам entity
(priority, layer, flags, pickable). Сохраняются все фазы одной геометрии, но
Depth/Id не получают дублирующих draws для каждой фазы. Разные батчи имеют
различные geometry_id. Модель батча задаёт начало ячейки, вершины хранятся локально.

Проверка membership, transform, mesh/material/shader revisions и pick ID
определяет необходимость пересборки. Редактирование меша должно повышать его
штатную resource revision. Прямая запись в raw vertex buffer без revision не
является поддерживаемым протоколом изменения меша. При изменении группы
пересобираются её vertices/indices, неизменённые группы сохраняют TcMesh.
Удаление/скрытие объектов отражается в следующей публикации. Detach сцены
очищает её cache variants; разные view filters используют отдельные варианты.

Нормали преобразуются inverse transpose, тангенты — линейным преобразованием
с ортогонализацией и корректировкой handedness. Зеркальный transform корректирует
winding. UV и поддерживаемые прочие атрибуты копируются; вершины разных объектов
не свариваются. Атлас текстур не строится.

Skinned/inline-uniform/override-color items, прозрачные фазы, вырожденные
transforms и неподдерживаемые vertex layouts остаются отдельными draws.
Поддерживаются position/normal/uv/tangent/color; opt-in материал должен допускать
перенос исходных локальных вершин в координаты чанка (например UV-based PBR).
Object-space deformation/material semantics требуют отдельной поддержки.

## Picking

Merged mesh получает целочисленный `pick_id` исходного entity на каждой вершине.
`IdPass` выбирает отдельный builtin shader и contract только для batched items.
`PositionPickId` связывает атрибуты position/pick_id по reflection shader input
locations. ID передаётся `nointerpolation` и кодируется в прежний RGB-формат
`tc_picking`; декодирование и выбор отдельных исходных entities не меняются.

После перерасчёта вершин порядок операций с float отличается. Побитовая
идентичность растра на границах треугольников и coplanar поверхностях не является
гарантией batching. Pixel regression проверяет ID внутри исходных объектов
до и после объединения. Framegraph internal symbols сейчас используют имя
представителя батча; это не список всех его исходных entities.

## Проверки и измерения

CPU tests: `termin_render_static_mesh_batch_test` (reuse, invalidation,
membership, transforms, picking attributes, snapshot lifetime).
Pixel test: `termin_render_passes_id_pass_line_pixel_smoke` сравнивает два
обычных MeshRenderer и один batch, декодируя оба source IDs.
`termin_render_passes_picking_test` сверяет shader codec с CPU для 24-битных IDs.
Общий запуск: `task build`, `task test`.

Profiler sections: `Static mesh batching`, `Static batch rebuild`.
`StaticMeshBatchCache::stats()` содержит input/eligible/merged/output/rebuilt/
reused/unsupported counts. В стабильном кадре rebuild должен отсутствовать.

Пространственная группировка не добавляет frustum culling: этот отдельный
scope отслеживается в #2312. Основная задача batching — #2311.
