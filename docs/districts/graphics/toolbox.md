# Карта механизмов

Graphics состоит из восемнадцати пакетов. Это не восемнадцать способов
нарисовать треугольник: часть хранит переносимые данные, часть разговаривает с
GPU, часть строит retained composition, а несколько модулей существуют ровно
для того, чтобы соседние слои не начали знать друг о друге лишнее.

Канонический roster задаёт
[`build-system/districts.json`](https://github.com/mirmik/termin/blob/master/build-system/districts.json).

## Переносимые данные и импорт

| Package | Ответственность | Публичная поверхность |
|---|---|---|
| `termin-image` | Decode, encode и image values | `termin.image`, `termin_image::termin_image` |
| `termin-tween` | Чистые easing и tween primitives | `termin.tween` |
| `termin-mesh` | Canonical mesh/resource data | `tmesh`, `tmesh::termin_mesh` |
| `termin-skeleton` | Skeleton hierarchy и bulk publication | `termin.skeleton`, `termin_skeleton::termin_skeleton` |
| `termin-animation` | Clips, tracks, sampling и serialization | `termin.animation`, `termin_animation::termin_animation` |
| `termin-glb-native` | Компактный cgltf-backed document boundary | `termin.glb.native` |
| `termin-glb` | Portable GLB/glTF data и loading | `termin.glb`, `termin_glb::termin_glb` |

Эти пакеты не должны приобретать Entity или AssetManager только потому, что
данные однажды окажутся в сцене. Engine adapters живут выше.

Animation runtime уверенно обрабатывает LINEAR и STEP TRS tracks. CUBICSPLINE
и morph-weight tracks сохраняются и проходят round trip, но их sampling пока
завершается явной ошибкой. Документация предпочитает честный отказ
воображаемой поддержке.

## GPU и render execution

| Package | Ответственность | Публичная поверхность |
|---|---|---|
| `termin-graphics` | GPU API, device/context, resources, `GraphicsHost` | `tgfx`, `tgfx::termin_graphics2` |
| `termin-shader-runtime` | Поиск shader tools и source-project runtime config | `termin.shader_runtime`, `termin.shader_tools` |
| `termin-materials` | Shader, material и surface contracts | `termin.materials`, `termin_materials::termin_materials` |
| `termin-render-core` | Framegraph, pipelines, snapshots и task planning | `termin_render_core::termin_render_core` |
| `termin-graphics-mcp` | Texture readback и PNG screenshot helpers | `termin.graphics.mcp` |

`termin-graphics` всё ещё содержит legacy resource surface рядом с современным
tgfx2 API. Для нового native GPU-кода предпочтителен target
`tgfx::termin_graphics2`; существование старого target не является приглашением
строить новый compatibility layer.

`termin-render-core` намеренно не имеет Python package. Его контракт —
scene-neutral C/C++ execution, а не второй high-level renderer binding.

## Presentation и инструменты

| Package | Ответственность | Публичная поверхность |
|---|---|---|
| `termin-window` | Native windows, events и texture presentation | `termin.window`, `termin_window::termin_window` |
| `termin-visual-scene` | Retained 2D/3D object trees и interaction | `termin.visual_scene`, `termin_visual_scene::termin_visual_scene` |
| `termin-gui-native` | Retained widget/document core и offscreen UI | `termin.gui_native`, `termin_gui_native::termin_gui_native` |
| `termin-nodegraph` | Headless graph core и optional UI projection | `tcnodegraph`, `termin_nodegraph::core` |
| `tcplot` | Toolkit-neutral 2D/3D plotting | `tcplot`, `tcplot::tcplot` |
| `tcplot-gui-native` | Leaf bridge: готовые Plot widgets для native GUI | `tcplot_gui_native`, `tcplot_gui_native::tcplot_gui_native` |

`termin-window` включается для SDL-enabled desktop usage. Headless document
composition использует GUI offscreen targets без окна.

`tcplot` не зависит от GUI. Готовый `Plot2D` или `Plot3D` появляется только в
leaf bridge `tcplot-gui-native`; обратная зависимость из plot core запрещена.

## Детальные паспорта

- [termin-graphics](https://github.com/mirmik/termin/blob/master/graphics/termin-graphics/docs/index.md)
- [termin-render-core](https://github.com/mirmik/termin/blob/master/graphics/termin-render-core/docs/index.md)
- [termin-visual-scene](https://github.com/mirmik/termin/blob/master/graphics/termin-visual-scene/docs/index.md)
- [termin-window](https://github.com/mirmik/termin/blob/master/graphics/termin-window/docs/index.md)
- [termin-gui-native](https://github.com/mirmik/termin/blob/master/graphics/termin-gui-native/README.md)
- [termin-nodegraph](https://github.com/mirmik/termin/blob/master/graphics/termin-nodegraph/docs/index.md)
- [tcplot](https://github.com/mirmik/termin/blob/master/graphics/tcplot/docs/index.md)
- [termin-mesh](https://github.com/mirmik/termin/blob/master/graphics/termin-mesh/docs/index.md)
- [termin-glb](https://github.com/mirmik/termin/blob/master/graphics/termin-glb/docs/index.md)
- [termin-skeleton](https://github.com/mirmik/termin/blob/master/graphics/termin-skeleton/docs/index.md)
- [termin-animation](https://github.com/mirmik/termin/blob/master/graphics/termin-animation/docs/index.md)

Package passports описывают детали. Эта страница отвечает на другой вопрос:
почему они находятся в одном районе и где между ними должна проходить стена.
