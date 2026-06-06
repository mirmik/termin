# Procedural CSG Editor Refactor

Дата: 2026-06-07

Статус: план рефакторинга, выполнение начато. `csg_cad.py` уже используется как быстрый standalone-полигон, но целевая логика редактора должна жить в общем слое `termin.csg` и переиспользоваться в `termin-app`.

## Прогресс

- 2026-06-07: Phase 1 выполнена. Добавлен `termin.csg.editor_controller`, основные workflow-команды `CadApp` переведены на общий controller.
- 2026-06-07: Phase 2 начата. `ProceduralMeshEditorExtension` переведен на общий controller для mode/draft/selection/document commands; добавлены embedded-кнопки primitives и boolean operations через тот же controller.
- 2026-06-07: Phase 3 начата. Добавлен `termin.csg.operation_specs`; defaults, labels, button order, primitive param schema и tree boolean roles переведены на общий registry без изменения serialized format.
- 2026-06-07: Phase 4 начата. `DocumentTreeNode` получил metadata для boolean inputs/drop semantics; standalone CAD DnD больше не восстанавливает parent/input index через внутреннюю структуру `TreeWidget`.

## Контекст

В `termin-csg` появился рабочий мини-редактор процедурного CSG-документа:

- sketch plane и contours;
- outer/hole contour roles;
- extrude;
- CSG primitives;
- union/subtract/intersect;
- tree DnD для boolean inputs;
- редактирование параметров операций, primitives, plane и contour points;
- viewport dragging для contour points;
- standalone preview/rendering в `csg_cad.py`.

Реальная точка встраивания в приложение - `ProceduralMeshEditorExtension` для `ProceduralMeshComponent`:

```text
termin-app/termin/editor_tcgui/procedural_mesh_editor_extension.py
termin-components/termin-components-mesh/python/termin/mesh/procedural_mesh_component.py
```

Сейчас общая документная логика уже вынесена в `termin.csg`, но standalone editor ушел дальше embedded extension. Это снова создает риск двух несовместимых реализаций редактора.

## Цель

Сделать `csg_cad.py` shell-приложением для быстрой отладки, а не канонической реализацией editor workflow.

Канонические части должны быть общими:

- document model;
- edit commands;
- evaluation;
- selection/mode/draft state;
- tree model и DnD semantics;
- operation params metadata;
- visual/debug model.

Standalone CAD и `termin-app` должны отличаться только интеграционным shell-слоем:

- standalone: собственное окно, texture viewport, file dialogs;
- `termin-app`: component inspector, entity-local/world transforms, app viewport overlay, undo/redo integration.

## Текущее Разделение

Уже хорошие границы:

- `procedural_document.py` - сериализуемая модель документа;
- `document_edit.py` - низкоуровневые команды редактирования;
- `document_eval.py` - построение CSG solids;
- `document_tree_model.py` - проекция документа в дерево;
- `document_visual_model.py` - debug/overlay visual model;
- `document_raycast.py` - raycast по evaluated document;
- `cad_viewer.py` - standalone viewport/rendering helpers.

Проблемная зона:

- `cad_app.py` смешивает layout, commands, selection, mode, file IO, tree DnD, viewport tools, inspector panels и status handling;
- `ProceduralMeshEditorExtension` частично повторяет старую версию editor workflow и не имеет parity со standalone CAD.

## Phase 1: Общий Editor Controller

Создать общий слой:

```text
termin.csg.editor_controller
```

Controller владеет:

- `document`;
- `selection`;
- `draft`;
- `mode`;
- пользовательскими командами редактирования.

Команды первого этапа:

- `new_document`;
- `select_node`;
- `start_draw_sketch`;
- `start_add_outer_contour`;
- `start_add_hole_contour`;
- `close_contour`;
- `extrude_selected`;
- `add_boolean_operation`;
- `add_primitive`;
- `add/move/remove_boolean_input`;
- `set_contour_point`;
- `set_sketch_plane`;
- `set_operation_transform`;
- `set_extrude_vector`;
- `set_primitive_params`.

Controller должен возвращать небольшой result object, чтобы shell понимал, что обновлять:

```text
document_changed
selection_changed
tree_changed
preview_changed
fit_camera
message
```

Критерий готовности:

- `CadApp` использует controller для основных workflow-команд;
- текущие `termin-csg` тесты проходят;
- можно начать подключать тот же controller в `ProceduralMeshEditorExtension`.

## Phase 2: Перевод ProceduralMeshEditorExtension

Перевести embedded extension на тот же controller:

- selection/mode/draft больше не живут отдельно в extension;
- close contour/extrude/draw commands идут через controller;
- tree refresh использует тот же selection state;
- behavior parity со standalone CAD становится явной задачей.

После этого новые CSG workflow-фичи добавляются один раз в controller, а не отдельно в `cad_app.py` и `procedural_mesh_editor_extension.py`.

## Phase 3: Operation Registry / Schema

Сейчас operation behavior размазан между model/eval/tree/UI. Нужно ввести декларативный слой:

```text
OperationSpec
```

Минимальные поля:

- `kind`;
- `label`;
- `default_params`;
- `param_schema`;
- `input_policy`;
- `tree labels`;
- `context actions`;
- evaluator hook или dispatch metadata.

Начальные specs:

- `primitive`;
- `extrude`;
- `union`;
- `subtract`;
- `intersect`.

После этого inspector panels можно строить из schema, а не держать отдельный hardcoded UI на каждый вид операции.

## Phase 4: Богатый Tree Model

Расширить `DocumentTreeNode` metadata:

```text
parent_operation_id
input_index
input_role
is_boolean_input
accepts_drop_inside
accepts_drop_above_below
```

Это позволит убрать fragile DnD-логику, которая сейчас восстанавливает смысл через parent `TreeNode`.

Tree должен оставаться projection, но projection должна содержать достаточно семантики для UI.

## Phase 5: Component Integration

`ProceduralMeshComponent` должен остаться владельцем serialized document, но нужно формализовать:

- dirty state;
- regenerate policy;
- преобразование evaluated document в real mesh component;
- app undo/redo;
- что считается component-local координатами;
- как controller сообщает shell-у о document changes.

Минимальный путь: controller работает поверх `component.document`, а extension отвечает за преобразование local/world координат и viewport overlay.

## Тестовая Стратегия

Добавлять тесты слоями:

- unit tests на controller без UI;
- tests на tree DnD через controller;
- tests на operation params/defaults/schema;
- сохранение существующих `CadApp` regression tests;
- embedded extension smoke tests, когда controller будет подключен в `termin-app`.

## Практический Порядок

1. Вынести `CsgEditorController` и перевести на него основные команды `CadApp`.
2. Перевести `ProceduralMeshEditorExtension` на controller.
3. Ввести operation specs для текущих операций без изменения serialized format.
4. Переписать inspector panels на schema-driven generation.
5. Обогатить tree metadata и упростить DnD.
6. После стабилизации заняться mesh regeneration и undo/redo в `termin-app`.
