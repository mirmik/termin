# Foliage / Scatter System Design Note

Дата: 2026-05-26

Статус: черновая архитектурная заметка. Это не финальный API, а фиксация текущих размышлений перед будущей реализацией.

## Контекст

Нужна система, похожая на foliage painting в игровых движках: пользователь кистью размечает поверхность объекта, а движок размещает траву, камни или другие мелкие инстансы по этой разметке.

Первичный сценарий:

- пользователь ведет кистью по mesh/terrain объекту во viewport;
- редактор делает raycast в сцену;
- по hit position/normal добавляются или удаляются scatter-точки;
- runtime рисует траву через instancing;
- точки привязаны к объекту и хранятся в local-space объекта.

## Основное решение

Foliage следует делать не частью `termin-render`, а отдельной компонентной библиотекой:

```text
termin-components/
  termin-components-foliage/
    termin/foliage/foliage_layer_component.hpp
    termin/foliage/foliage_instance.hpp
    termin/foliage/foliage_renderer.hpp
    src/foliage_layer_component.cpp
    src/foliage_renderer.cpp
```

`termin-render` должен оставаться инфраструктурой рендера: `Drawable`, passes, frame graph, render context. Foliage - предметная сценовая система: данные размещения, кисти, варианты мешей, сериализация, culling/LOD. Поэтому она не должна разрастаться внутри render-core.

`termin-components-render` технически может принять такой компонент, но это нежелательно: пакет уже содержит базовые render-компоненты вроде `MeshRenderer`, `LineRenderer`, `CameraComponent`, `LightComponent`. Foliage тяжелее и специфичнее, поэтому его лучше подключать отдельно.

## Компонент

Минимальный компонент:

```text
Entity: TerrainChunk_01
  MeshComponent
  MeshRenderer
  ColliderComponent
  FoliageLayerComponent
```

`FoliageLayerComponent`:

- хранит ссылку на foliage data asset;
- хранит настройки слоя: mesh/material variants, density, min spacing, scale range, slope limit;
- держит runtime cache загруженных точек;
- реализует `Drawable`;
- рисует через `draw_tgfx2()`.

В текущем render-контракте это ложится естественно: `ColorPass` уже умеет вызывать direct tgfx2 hook для drawable, у которого `get_mesh_for_phase()` возвращает `nullptr`. Для foliage это удобнее, чем притворяться одним обычным `tc_mesh`.

## Данные инстанса

Черновой debug-friendly layout:

```cpp
struct FoliageInstance {
    Vec3 local_position;
    Vec3 local_normal;
    float yaw;
    float scale;
    uint32_t variant;
    uint32_t seed;
};
```

Это около 40 байт на точку на CPU, и обычно 48 байт в GPU-friendly layout:

```text
vec4 position_scale
vec4 normal_yaw
uvec4 meta
```

Важно: одна точка - это не обязательно одна травинка. Практичнее считать ее одним пучком травы, где mesh содержит несколько cards/blades.

Паковать до 16-24 байт имеет смысл позже, когда появятся большие сцены и реальные профили.

## Поведение кисти

MVP-режимы:

- `Add`: добавляет точки до целевой плотности;
- `Erase`: удаляет точки в радиусе кисти;
- `Repaint`: пересоздает область текущими настройками, позже;
- `Smooth/Relax`: выравнивает плотность/scale/variant, позже.

Повторный мазок по насыщенной области не должен плодить дубликаты. Нужен spatial lookup, хотя бы uniform grid/hash в local-space:

```text
cell = floor(local_position / min_spacing)
```

При добавлении новой точки проверяются текущая и соседние ячейки.

## Почему точки, а не texture mask

UV/density mask подходит для terrain и хорошо размеченных mesh, но имеет проблемы:

- зависит от UV;
- ломается на mirrored/overlapped UV;
- швы и разная texel density дают неожиданные эффекты;
- смена UV ломает paint data.

Для первого foliage tool лучше хранить точки в local-space. Это проще отлаживать, не зависит от UV и сразу является почти готовым runtime instance buffer.

Texture/weight mask можно добавить позже как authoring-слой для процедурной регенерации, сглаживания и больших terrain-сцен.

## Сериализация

Писать десятки тысяч точек прямо в scene json - плохая идея. Scene-файл станет большим, шумным, плохо диффабельным и дорогим для merge.

Решение: foliage точки должны жить как отдельный asset/blob, а сцена хранит только ссылку и легкие параметры.

Пример scene data компонента:

```json
{
  "type": "FoliageLayerComponent",
  "data": {
    "asset": {
      "uuid": "...",
      "source_path": "Assets/Foliage/terrain_01_grass.tfoliage"
    },
    "layer_name": "grass",
    "mesh_variants": [],
    "material": null,
    "density": 1.0,
    "min_spacing": 0.25
  }
}
```

Файл рядом с проектом:

```text
Assets/Foliage/terrain_01_grass.tfoliage
Assets/Foliage/terrain_01_grass.tfoliage.meta
```

`.tfoliage` лучше делать бинарным чанковым форматом:

```text
magic/version
coordinate_space = local
bounds
instance_count
instances[]
optional chunks
optional compression
```

Плюсы:

- scene-файл остается читаемым;
- foliage можно lazy-load;
- asset можно hot-reload;
- runtime может грузить/стримить чанки независимо от сцены;
- формат можно переупаковывать без миграции scene json.

## Asset Layer

Нужен новый asset type, но не в legacy `termin-app/termin/assets`. Этот каталог сейчас
мигрирует наружу и не должен принимать новые предметные asset-типы.

Правильная граница:

```text
termin-components/termin-components-foliage/
  termin/foliage/foliage_data.hpp
  termin/foliage/foliage_data_registry.hpp
  termin/foliage/foliage_file.hpp
  python/termin/foliage/asset_plugin.py
```

Native C++ часть владеет `FoliageData`, registry/handle и чтением/записью `.tfoliage`.
Python часть в `termin.foliage` должна оставаться package-side glue: import plugin,
metadata helpers и тонкий binding к native handle для editor-команд. Она зависит от
общего `termin-assets` contract package, но не от `termin-app`.

Подключение к editor/build registry должно идти через package entry points:

```text
termin.asset_import_plugins:
  foliage_data = termin.foliage.asset_plugin:create_import_plugin
```

`termin-app` при этом вызывает общий discovery helper из `termin-assets` для asset
plugins. Предметный tcgui-инструмент кисти живет в `termin-app`, потому что это
часть интерфейса редактора, а не asset package.

Важно отделить:

- runtime C++ компонент и renderer в `termin-components-foliage`;
- editor/project asset integration как внешний plugin/adapter, подключаемый editor-ом;
- editor UI tools (`FoliageLayerEditorExtension`) в `termin-app/termin/editor_tcgui`;
- сам формат файла так, чтобы C++ runtime мог читать его без Python, если потребуется standalone.

## Rendering

Начальный вариант:

- `FoliageLayerComponent::get_mesh_for_phase()` возвращает `nullptr`;
- `FoliageLayerComponent::draw_tgfx2()` делает instanced draw;
- instance buffer строится из загруженных точек;
- shader разворачивает grass card/blade из mesh vertex + per-instance data;
- ветер и variation берутся из `seed`.

Текущий tgfx2 уже поддерживает instanced draw через `RenderContext2::draw_arrays_instanced(...)` и per-instance vertex layouts.

Текущая реализация color path:

- `FoliageLayerComponent::get_geometry_draws()` возвращает один draw на material phase, а не один draw на instance;
- `get_mesh_for_phase()` всегда возвращает `nullptr`, чтобы `ColorPass` ушел в direct `draw_tgfx2()`;
- tgfx2 расширен indexed instanced draw path, поэтому `draw_tgfx2()` рисует prototype mesh через cached `ensure_tc_mesh(...)` и отдельный per-instance vertex stream;
- выбранный `TcMaterial` теперь применяется через shader variant: `FoliageLayerComponent::override_shader()` строит
  `TC_SHADER_VARIANT_FOLIAGE`, заменяя vertex stage на foliage-instanced вариант и сохраняя fragment stage,
  material UBO layout, features и textures исходного material phase;
- текущий foliage vertex variant покрывает стандартные varyings `v_world_pos`, `v_normal`, `v_uv`, `v_TBN`, `v_tangent`,
  что подходит для `StandardShader`/`CookTorrancePBR`; нестандартные vertex/fragment contracts потребуют отдельного
  механизма адаптации;
- parent scale намеренно отбрасывается: model matrix собирается из global translation + rotation и unit scale;
- `FoliageInstance::scale` пока не применяется, чтобы не смешивать масштаб кисти/вариантов с исправлением базовой отрисовки;
- default normal у `FoliageInstance` - Z-up (`0, 0, 1`) по общей координатной системе Termin.

Foliage shadows идут через тот же direct `draw_tgfx2()` подход, что и color path:
`ShadowPass` теперь вызывает direct hook для drawable без `tc_mesh*`, а
`FoliageLayerComponent` создает отдельный `TC_SHADER_VARIANT_FOLIAGE_SHADOW`.
Shadow variant использует instanced foliage layout и shadow-pass UBO contract
(`PerFrame` на binding 0), поэтому prototype mesh остается одним instanced draw
call на слой/phase и не превращается в draw call на травинку.

Плохой запах, который надо закрыть следующей итерацией: instance stream сейчас строится/заливается в `draw_tgfx2()`. Это уже правильная draw-call модель и prototype mesh идет через device cache, но для больших сцен instance buffer стоит кэшировать по `FoliageData::version`.

## Editor Tool

Кисть должна жить в editor/tcgui слое, не в runtime-компоненте.

Схема:

```text
FoliageBrushTool
  -> viewport click interceptor after surface pick
  -> hit mesh point + normal
  -> selected FoliageLayerComponent
  -> selected/created FoliageData asset
  -> native TcFoliageData add/remove/save
```

Сохранение проекта должно записывать `.tfoliage`, а не раздувать scene json.

Текущий MVP: `FoliageLayerEditorExtension` регистрируется для `FoliageLayerComponent`,
перехватывает клики в режимах Paint/Erase, редактирует native `TcFoliageData` через
binding и рисует overlay-точки/радиус кисти через `ImmediateRenderer`. У кисти есть явный
режим Off; `Esc` выключает активную кисть и возвращает viewport к обычному selection.
Активный viewport tool сообщает editor window о захвате инструмента, и окно скрывает transform
gizmo до возврата в Off.
Это stamp brush: непрерывный drag потребует отдельного mouse-move surface callback в
`EditorInteractionSystem`.

Для ручной проверки добавлен source asset pack `examples/foliage-assets`: дешевый
opaque cross-card `Models/LowPolyBush.obj` с sidecar UUID и материал
`Materials/LowPolyBush.material`. Это не package/runtime asset и не новый builtin;
его можно копировать или импортировать в editor project как обычные проектные
source assets.

## Generic Large Payload Pattern

Foliage - не единственный случай больших данных компонента. Имеет смысл завести общий паттерн:

```text
Component scene data:
  settings
  external_payload_ref

External payload:
  dense arrays / binary / generated data
```

Такой подход позже пригодится для baked nav data, voxel chunks, procedural caches, lightmaps или других больших данных.

## Открытые вопросы

- Нужен ли общий `ExternalPayloadRef` в `termin-scene`, или достаточно asset refs на уровне конкретных компонентов?
- Должен ли `.tfoliage` быть полностью runtime-readable C++ форматом с первого дня?
- Где держать dirty/save lifecycle для sidecar assets: в ResourceManager или отдельном project save service?
- Как связывать foliage asset с owner entity: только через component field или дополнительно хранить owner uuid внутри `.tfoliage`?
- Нужен ли scene-level manifest для всех sidecar payloads?
- Как мигрировать foliage при изменении mesh topology, transform или scale?
- Как поддерживать chunking и culling: в asset format сразу или отложить?

## Замеченные риски в текущей базе

`TcSceneRef::serialize()` сейчас сериализует компоненты через `tc_inspect_serialize(...)` напрямую, а не через виртуальный `CxxComponent::serialize_data()`. Если foliage-компонент будет полагаться только на override `serialize_data()`, scene save может его обойти. Перед реализацией foliage это надо либо исправить, либо убедиться, что все поля компонента выражены через inspect/`SERIALIZABLE_FIELD`.

`tc_scene_extension_ids.h` сейчас имеет hardcoded `TC_SCENE_EXT_TYPE_COUNT 3`. Для foliage это не блокер, потому что стартовый дизайн не требует scene extension. Но если появится `SceneExternalDataManifest`, придется расширять механизм scene extensions аккуратнее, чем просто добавлять очередной fixed id.

## Предлагаемый MVP

1. Создать `termin-components-foliage`.
2. Добавить `FoliageLayerComponent` с asset ref и runtime points cache.
3. Добавить простой `.tfoliage` формат без compression/chunking.
4. Реализовать tgfx2 instanced draw без теней.
5. Добавить editor brush: Add/Erase, local-space points, min spacing.
6. Сериализовать в scene только asset ref и настройки.
7. Отдельно проверить и при необходимости поправить путь scene serialization для virtual `serialize_data()`.
