# C++ Class Layout Migration Map

Дата baseline: 2026-07-10.

Нормативное правило описано в [C++ Style Guide](../cpp-style.md). Карта построена
по Python/nanobind compilation profile, который является наиболее полным
текущим профилем: 139 классов, 118 файлов и 852 поля в 18 модулях.

## Как вести карту

- Единица владения — файл. Два агента не работают с одним файлом одновременно.
- Статусы: `pending`, `in_progress`, `done`, `blocked`.
- Статусы обновляет координатор после отчёта исполнителя и повторного AST-check.
- JSONL-отчёт checker остаётся источником истины для списка нарушений; эта карта
  хранит ownership и прогресс batches.
- После каждого batch запускается checker с `--path` для затронутого модуля.
  `--path` фильтрует определения классов, но checker разбирает всю compilation
  database, поэтому headers, найденные через внешние модули-потребители, не
  теряются.
- После завершения всех batches проверяются обычный и Python/nanobind profiles
  целиком.

```bash
./run-cpp-class-layout-check.sh --python-bindings --path termin-base --no-fail
./run-cpp-class-layout-check.sh --python-bindings --format jsonl --no-fail
./run-cpp-class-layout-check.sh --format jsonl --no-fail
```

## Модули

| Status | Module | Classes | Files | Fields | Owner | Last check |
|---|---|---:|---:|---:|---|---|
| pending | `termin-gui-native` | 66 | 58 | 467 | — | baseline |
| pending | `termin-base` | 13 | 3 | 20 | — | baseline |
| pending | `termin-graphics` | 9 | 9 | 110 | — | baseline |
| pending | `termin-engine` | 7 | 7 | 29 | — | baseline |
| pending | `termin-navmesh` | 7 | 7 | 44 | — | baseline |
| pending | `tcplot` | 6 | 6 | 88 | — | baseline |
| pending | `termin-render` | 5 | 3 | 8 | — | baseline |
| pending | `termin-render-passes` | 5 | 5 | 24 | — | baseline |
| pending | `termin-components` | 4 | 4 | 26 | — | baseline |
| done | `termin-display` | 4 | 4 | 8 | `ClassLayout-1` | 2026-07-10, Python profile: 0 |
| pending | `termin-collision` | 3 | 3 | 11 | — | baseline |
| pending | `termin-scene` | 3 | 2 | 4 | — | baseline |
| pending | `termin-voxels` | 2 | 2 | 8 | — | baseline |
| pending | `termin-app` | 1 | 1 | 1 | — | baseline |
| pending | `termin-csg` | 1 | 1 | 1 | — | baseline |
| pending | `termin-input` | 1 | 1 | 1 | — | baseline |
| pending | `termin-materials` | 1 | 1 | 1 | — | baseline |
| pending | `termin-player` | 1 | 1 | 1 | — | baseline |
| **Total** | | **139** | **118** | **852** | | |

Небольшие модули можно выдавать агенту целиком. `termin-gui-native` разбит ниже
на непересекающиеся file-owned batches.

## GUI-1: models and documents

Status: `pending`. Baseline: 15 classes, 13 files, 58 fields.

- `termin-gui-native/include/termin/gui_native/collection_model.hpp`
- `termin-gui-native/include/termin/gui_native/color_picker_model.hpp`
- `termin-gui-native/include/termin/gui_native/command_model.hpp`
- `termin-gui-native/include/termin/gui_native/document.hpp`
- `termin-gui-native/include/termin/gui_native/document_builder.hpp`
- `termin-gui-native/include/termin/gui_native/document_snapshot.hpp`
- `termin-gui-native/include/termin/gui_native/file_dialog_model.hpp`
- `termin-gui-native/include/termin/gui_native/rich_text_model.hpp`
- `termin-gui-native/include/termin/gui_native/selection_model.hpp`
- `termin-gui-native/include/termin/gui_native/signal.hpp`
- `termin-gui-native/include/termin/gui_native/table_model.hpp`
- `termin-gui-native/include/termin/gui_native/tree_model.hpp`
- `termin-gui-native/src/rich_text_model.cpp`

## GUI-2: complex views and widgets

Status: `pending`. Baseline: 14 classes, 12 files, 186 fields.

- `termin-gui-native/include/termin/gui_native/canvas.hpp`
- `termin-gui-native/include/termin/gui_native/draw_list_renderer.hpp`
- `termin-gui-native/include/termin/gui_native/file_dialog_overlay.hpp`
- `termin-gui-native/include/termin/gui_native/file_grid_widget.hpp`
- `termin-gui-native/include/termin/gui_native/frame_time_graph.hpp`
- `termin-gui-native/include/termin/gui_native/graphics_scene.hpp`
- `termin-gui-native/include/termin/gui_native/image_widget.hpp`
- `termin-gui-native/include/termin/gui_native/rich_text_view.hpp`
- `termin-gui-native/include/termin/gui_native/scene_view.hpp`
- `termin-gui-native/include/termin/gui_native/table_widget.hpp`
- `termin-gui-native/include/termin/gui_native/tree_widget.hpp`
- `termin-gui-native/include/termin/gui_native/viewport3d.hpp`

## GUI-3: Python bindings

Status: `pending`. Baseline: 5 classes, 1 file, 10 fields.

- `termin-gui-native/python/bindings/gui_native_module.cpp`

## GUI-4: controls A

Status: `pending`. Baseline: 16 classes, 16 files, 130 fields.

- `termin-gui-native/include/termin/gui_native/box_layout.hpp`
- `termin-gui-native/include/termin/gui_native/button.hpp`
- `termin-gui-native/include/termin/gui_native/checkbox.hpp`
- `termin-gui-native/include/termin/gui_native/color_dialog.hpp`
- `termin-gui-native/include/termin/gui_native/color_picker.hpp`
- `termin-gui-native/include/termin/gui_native/combo_box.hpp`
- `termin-gui-native/include/termin/gui_native/dialog.hpp`
- `termin-gui-native/include/termin/gui_native/grid_layout.hpp`
- `termin-gui-native/include/termin/gui_native/group_box.hpp`
- `termin-gui-native/include/termin/gui_native/icon_button.hpp`
- `termin-gui-native/include/termin/gui_native/input_dialog.hpp`
- `termin-gui-native/include/termin/gui_native/label.hpp`
- `termin-gui-native/include/termin/gui_native/list_widget.hpp`
- `termin-gui-native/include/termin/gui_native/menu.hpp`
- `termin-gui-native/include/termin/gui_native/menu_bar.hpp`
- `termin-gui-native/include/termin/gui_native/message_box.hpp`

## GUI-5: controls B

Status: `pending`. Baseline: 16 classes, 16 files, 83 fields.

- `termin-gui-native/include/termin/gui_native/native_widget.hpp`
- `termin-gui-native/include/termin/gui_native/progress_bar.hpp`
- `termin-gui-native/include/termin/gui_native/scroll_area.hpp`
- `termin-gui-native/include/termin/gui_native/separator.hpp`
- `termin-gui-native/include/termin/gui_native/slider.hpp`
- `termin-gui-native/include/termin/gui_native/slider_edit.hpp`
- `termin-gui-native/include/termin/gui_native/spin_box.hpp`
- `termin-gui-native/include/termin/gui_native/splitter.hpp`
- `termin-gui-native/include/termin/gui_native/status_bar.hpp`
- `termin-gui-native/include/termin/gui_native/swatch.hpp`
- `termin-gui-native/include/termin/gui_native/tab_view.hpp`
- `termin-gui-native/include/termin/gui_native/text_area.hpp`
- `termin-gui-native/include/termin/gui_native/text_input.hpp`
- `termin-gui-native/include/termin/gui_native/tool_bar.hpp`
- `termin-gui-native/include/termin/gui_native/widget.hpp`
- `termin-gui-native/src/combo_box.cpp`

## Отдельная ручная проверка

Следующие классы содержат поля, объявленные через макросы инспекции. Их следует
выдать отдельным batch и проверить вручную после перестановки:

- `termin::DepthPass` — `termin-components/termin-components-render/termin/render/depth_pass.hpp`;
- `termin::MaterialPass` — `termin-components/termin-components-render/termin/render/material_pass.hpp`;
- `termin::NormalPass` — `termin-components/termin-components-render/termin/render/normal_pass.hpp`;
- `termin::ColorPass` — `termin-render-passes/include/termin/render/color_pass.hpp`.

Дополнительного внимания требуют `termin-base/include/tcbase/tc_trent.hpp` с 11
вложенными классами, anonymous union в `termin-base/include/tcbase/trent/trent.h`
и классы с двадцатью и более перемещаемыми полями в GUI, `tcplot` и line
renderers.

## Параллельное выполнение

Одновременно работают не более трёх implementation workers и один координатор.
Каждый worker получает точный список файлов из одного batch. Координатор:

Проектный custom agent `cpp_class_layout_migrator` определён в
`.codex/agents/cpp-class-layout-migrator.toml`. Он использует `gpt-5.6-luna` с
`medium` reasoning effort. Проектный `.codex/config.toml` ограничивает workflow
тремя непосредственными workers и root-координатором без рекурсивного spawn.

1. Назначает ownership и переводит batch в `in_progress`.
2. Проверяет, что списки параллельных workers не пересекаются.
3. Принимает отчёт об изменённых файлах и неоднозначных случаях.
4. Последовательно запускает AST-check, сборку и тесты в общих build-каталогах.
5. Обновляет карту и только после проверки ставит `done`.

Workers не запускают полную сборку одновременно. Они могут параллельно менять
разные файлы и выполнять read-only анализ; общие проверки оркестрирует root
agent.
