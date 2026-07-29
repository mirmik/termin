# Texture encoding contract

Дата: 2026-07-29.

Статус: этапы graphics foundation (`#1048`) и asset/runtime propagation
(`#1049`) реализованы и проверены под Linux. Обе карточки остаются в `On Test`,
но не блокируют следующие этапы.

Связанный эпик доски: `#1045 [render] Нормализовать linear HDR и color-space тракт`.

## Контекст

Текущий рендер-тракт внешне похож на linear/HDR pipeline, но кодировка
исходных текстур в нём не является настоящей частью контракта:

- `TextureSpec` и `TextureAsset` сохраняют строковое поле `color_space` со
  значениями `srgb` и `linear`;
- это поле не доходит до `tc_texture` и native texture create info;
- `tgfx2::PixelFormat` не различает linear UNORM и sRGB-варианты форматов;
- Vulkan, OpenGL и D3D11 создают обычные UNORM-текстуры, поэтому sampling не
  выполняет sRGB EOTF;
- runtime package экспортирует `color_space`, но loader не использует его при
  создании GPU-текстуры;
- material shader property не сообщает, какую кодировку ожидает;
- texture inspector не показывает и не меняет кодировку;
- сохранение flip/transpose сейчас создаёт новый `TextureSpec` только с тремя
  полями и способно затереть остальные import-настройки.

В результате цветовые текстуры попадают в освещение в нелинейном виде, а
числовые текстуры неотличимы от цветовых. Компенсации в освещении и PBR могут
маскировать проблему, но не исправляют контракт данных.

Эта миграция создаёт фундамент для классического тракта:

```text
file bytes
    -> texture asset with explicit encoding
    -> native sRGB or linear texture format
    -> hardware decode while sampling
    -> linear lighting and blending
    -> output transform / tone mapping
    -> sRGB display output
```

Последние два этапа принадлежат более широкому эпику `#1045` и не входят в
этот план.

## Решения

### Кодировка, а не семантика

Публичное свойство texture asset называется `encoding` и имеет ровно два
значения:

- `sRGB` — RGB-каналы хранятся с sRGB transfer function и при sampling должны
  быть декодированы в linear;
- `Linear` — значения используются без transfer conversion.

`Linear` подходит и для линейного цвета, и для произвольных числовых данных.
Отдельное значение `Data` в первой версии не вводится: на уровне GPU оно не
добавляет нового поведения, зато протаскивает семантику изображения в
графическое ядро.

Normal map, albedo, roughness и другие назначения не являются свойствами файла
картинки. Эти понятия остаются на уровне importer/material contract. Графическое
ядро знает только кодировку.

### Linear lighting

Шейдер получает linear RGB независимо от способа хранения:

- sampling sRGB texture выполняет sRGB-to-linear conversion для RGB;
- sampling Linear texture возвращает нормализованные значения без conversion;
- alpha не проходит через sRGB conversion;
- освещение, PBR, интерполяция и blending выполняются в linear space.

Upload не перекодирует байты на CPU. Кодировка выбирает native image format и
тем самым поведение sampling.

### Строгий material contract

Каждое каноническое material-свойство типа `Texture2D` объявляет ожидаемую
кодировку:

```glsl
@property Texture2D u_albedo_texture = "white" encoding(srgb)
@property Texture2D u_normal_texture = "normal" encoding(linear)
```

Правила:

- `encoding(srgb|linear)` обязателен для material `Texture2D`;
- отсутствие или неизвестное значение является ошибкой парсинга;
- annotation запрещена для свойств других типов;
- transient/framegraph samplers не становятся material properties и не
  получают этот контракт;
- назначение текстуры с другой кодировкой отклоняется с диагностикой;
- при неуспешной замене материал сохраняет прежний корректный binding;
- проверка одинакова в editor, asset load, runtime package, hot reload и
  публичном material API.

Низкоуровневый материал, созданный вручную без property schema, может остаться
непроверяемым. Канонический asset/material path должен быть строгим.

### Символические defaults

`"white"` остаётся общим термином в исходнике шейдера. Parser/material builder
разрешает его с учётом `encoding(...)` в честную встроенную sRGB- или
Linear-текстуру.

`"normal"` разрешается только для `encoding(linear)`. Внутренние built-in
текстуры разных кодировок имеют разные identity и native handles, даже когда
их RGBA-байты совпадают.

### Пользовательский интерфейс

В texture inspector появляется поле `Encoding` со значениями `sRGB` и
`Linear`. Пользователь выбирает именно кодировку, а не назначение карты.

Рядом показывается краткая памятка:

> sRGB — обычные цветные изображения. Linear — линейные и числовые данные,
> включая normal maps.

Изменение:

1. обновляет существующий `TextureSpec` без потери filter/wrap/mipmap/transform;
2. сохраняет metadata;
3. переимпортирует asset;
4. увеличивает texture version и пересоздаёт native texture;
5. повторно проверяет material bindings.

Preview тоже учитывает кодировку. sRGB asset показывается как обычное SDR
изображение, а Linear asset перед выводом в SDR UI получает явное
linear-to-sRGB преобразование. Иначе linear preview будет ошибочно выглядеть
тёмным.

## Целевой контракт по слоям

### `termin-default-assets` и asset system

`TextureSpec.color_space` переименовывается в `TextureSpec.encoding`.
Допустимые serialized values: `srgb` и `linear`.

Это намеренная чистая миграция, а не поддержка двух имён:

- в репозитории нет известных project `.meta`, требующих длительной
  совместимости;
- неизвестные значения должны завершать import с понятной ошибкой;
- обычная импортированная картинка по умолчанию получает `srgb`;
- raw/procedural texture creation указывает encoding явно.

`TextureAsset` хранит encoding и передаёт его в `TcTextureCreateInfo`.
Content-derived identity включает encoding: одинаковые pixels с разной
кодировкой являются разными texture resources.

### `termin-image`

Декодер продолжает возвращать пиксельные данные без скрытой color conversion.
На первом этапе он не обязан разбирать ICC, PNG `gAMA` или wide-gamut profiles:
явный asset contract уже определяет интерпретацию данных.

Обнаружение и преобразование ICC-профилей — отдельная будущая задача. Оно не
должно блокировать честный sRGB/Linear тракт.

### `termin-graphics` / `tgfx2`

Вводится общий enum `TextureEncoding { SRGB, Linear }`, доступный C/C++ и
Python API. Его хранят `tc_texture` и texture create info. Смена encoding
увеличивает version ресурса.

В `tgfx2::PixelFormat` добавляются как минимум:

- `RGBA8_sRGB`;
- `BGRA8_sRGB`.

Linear варианты сохраняют существующие `RGBA8_UNORM`/`BGRA8_UNORM` имена или
получают однозначные эквиваленты. Отдельный `RGB8_sRGB` не вводится, если он
мешает одинаковой поддержке D3D11; importer нормализует такие изображения в
RGBA8.

Native mappings:

| Engine format | Vulkan | D3D11 | OpenGL |
|---|---|---|---|
| `RGBA8_sRGB` | `VK_FORMAT_R8G8B8A8_SRGB` | `DXGI_FORMAT_R8G8B8A8_UNORM_SRGB` | `GL_SRGB8_ALPHA8` |
| `BGRA8_sRGB` | `VK_FORMAT_B8G8R8A8_SRGB` | `DXGI_FORMAT_B8G8R8A8_UNORM_SRGB` | backend-compatible BGRA upload into `GL_SRGB8_ALPHA8` |

Format naming/parsing, byte size, validation, readback and backend tests должны
знать новые значения. Формат выбирается из storage format и texture encoding в
одном общем месте, а не независимо в каждом backend.

### Mipmaps

sRGB mip levels должны фильтроваться в linear space. Нельзя усреднять
sRGB-encoded bytes как linear числа.

Сейчас OpenGL учитывает texture mipmap policy, а Vulkan/D3D11 bridge создаёт
один level. После введения sRGB formats требуется выровнять поведение backend:

- одинаково соблюдать asset mipmap policy;
- использовать native sRGB-aware generation либо явную linear filtering path;
- тестировать не только level 0, но и выборку уменьшенных mip levels.

### `termin-materials` и shader metadata

`MaterialProperty` получает expected texture encoding. Parser разбирает
`encoding(...)` рядом с существующими modifiers и валидирует область
применимости.

Поле протягивается через:

- parsed shader metadata;
- `tc_shader_program_property_desc` / `tc_shader_program_property`;
- Python/C++ dictionaries и bindings;
- runtime shader/material package.

Parsed material construction объявляет expected encoding для texture slots.
Низкоуровневый `tc_material_phase_set_texture` проверяет его, если schema
присутствует, логирует mismatch и не портит предыдущее состояние.

Все штатные material shaders мигрируют одновременно с ужесточением parser:

- base color/albedo и emissive — `srgb`;
- normal, metallic-roughness, occlusion и другие числовые карты — `linear`;
- неоднозначные свойства разбираются по фактической математике шейдера, а не
  по имени файла.

### `termin-project-build` и runtime

Runtime texture spec хранит `encoding`, loader валидирует его и создаёт texture
с тем же encoding, что editor.

Runtime shader property schema хранит expected encoding. Package build
валидирует каждое material texture assignment до запуска приложения. Editor и
runtime не должны расходиться по default resolution и mismatch policy.

### `termin-app`

`TextureInspectorSnapshot` получает encoding. Controller использует
read-modify-write существующего `TextureSpec`, а не конструирует неполный spec.

Native inspector добавляет selector и памятку, выполняет reimport и обновляет
preview. Ошибки сохранения, import и recreation логируются и видимы
пользователю.

### `termin-glb`

glTF importer определяет encoding по стандартному material slot:

- `baseColorTexture`, `emissiveTexture` — sRGB;
- `normalTexture`, `metallicRoughnessTexture`, `occlusionTexture` — Linear.

Эта семантика остаётся внутри glTF importer и не попадает в graphics core.

Importer сначала собирает usages всех glTF textures, затем создаёт assets. Это
исключает зависимость результата от порядка обхода.

Если конкретное изображение используется только в одной кодировке, создаётся
один immutable texture asset с обычным исходным именем и UUID. Никакого
безусловного дублирования или суффикса нет.

Только при реальной коллизии, когда одно изображение требуется одновременно
как sRGB и Linear, importer создаёт две детерминированные внутренние вариации.
Их identity и при необходимости имя включают encoding. Текущая модель
image/texture/sampler glTF сохраняется: если sampler является частью identity,
варианты строятся для соответствующей пары image/sampler.

Неизвестные extension slots не угадываются по имени файла. Extension importer
должен явно объявить ожидаемую кодировку либо завершить импорт диагностикой.

## Инварианты

После миграции должны выполняться все условия:

1. У каждого texture asset есть ровно один явный encoding.
2. Encoding сохраняется от import metadata до native image format.
3. RGB sampling sRGB texture даёт linear значения; alpha не декодируется.
4. Linear texture sampling не применяет transfer function.
5. Одинаковые pixels с разным encoding не разделяют resource identity.
6. Material property знает ожидаемый encoding и отклоняет mismatch.
7. Editor preview, editor render и runtime package одинаково трактуют asset.
8. glTF не дублирует однозначные textures и детерминированно разделяет только
   реальные sRGB/Linear collisions.
9. Все graphics backends дают одинаковый результат в пределах тестового
   допуска.

## Последовательность миграции

### Этап 1. Graphics foundation

- добавить `TextureEncoding`;
- добавить sRGB pixel formats и backend mappings;
- централизовать выбор native format;
- покрыть level-0 sampling reference tests.

### Этап 2. Asset и runtime propagation

- переименовать serialized `color_space` в `encoding`;
- протянуть encoding через `TextureAsset`, `tc_texture`, create info, bindings,
  UUID/versioning;
- протянуть encoding через runtime package exporter и loader.

### Этап 3. Shader declaration contract

- добавить `encoding(...)` в parser/schema/bindings/package;
- сделать annotation обязательной для material textures;
- мигрировать штатные shaders и symbolic defaults.

### Этап 4. Material validation

- хранить expected encoding в texture slots;
- проверять editor/load/runtime/hot-reload assignment;
- отклонять mismatch транзакционно и логировать ошибку.

### Этап 5. Inspector

- добавить selector, help text и encoding-aware preview;
- исправить сохранение всего `TextureSpec`;
- обеспечить reimport и native texture recreation.

### Этап 6. glTF

- добавить pre-scan usages;
- импортировать однозначные textures без переименования;
- создавать deterministic variants только при коллизии;
- покрыть single-use, shared-same-encoding и collision fixtures.

### Этап 7. Mipmap parity и интеграционный gate

- выровнять mipmap generation между Vulkan/OpenGL/D3D11;
- добавить end-to-end editor/runtime и cross-backend проверки;
- выполнить полную SDK build и центральный test suite.

## Проверки

Минимальный reference fixture содержит RGBA byte value `128`:

- sRGB RGB sample должен быть около `0.21586`;
- Linear RGB sample должен быть около `0.50196`;
- alpha в обоих случаях должен быть около `0.50196`.

Также обязательны тесты:

- parser принимает только `encoding(srgb|linear)` у texture property и требует
  annotation;
- одинаковые pixels с разным encoding имеют разные identities/native handles;
- изменение encoding в inspector сохраняет остальные import settings,
  увеличивает version и пересоздаёт texture;
- material mismatch отклоняется и сохраняет прежний корректный binding;
- `"white"` выбирает вариант по expected encoding, `"normal"` требует Linear;
- editor и runtime package дают одинаковые texture/property contracts;
- Vulkan, OpenGL и D3D11 проходят один sampling reference;
- mipmapped sRGB fixture проверяет linear-space filtering;
- glTF collision fixture создаёт две вариации, а однозначные fixtures — одну.

Итоговая проверка по правилам репозитория:

```bash
./build-sdk.sh
./run-tests.sh
```

Для D3D11 mapping и sampling reference нужна Windows-проверка соответствующим
SDK/test скриптом.

## Не входит в этот план

- tone mapping и выбор конкретного оператора;
- output transform, swapchain sRGB policy и UI compositing;
- wide gamut, ICC color management, HDR display/scRGB/PQ/HLG;
- настоящий HDR/EXR decode и float texture import (`#1047`);
- material semantics в graphics core;
- автоматическое определение normal/albedo по имени файла;
- произвольные sRGB/Linear views одного mutable GPU image;
- сохранение старого `color_space` как бессрочного compatibility fallback.

## Разбиение по доске

План реализуется отдельными карточками:

1. `#1048` — sRGB pixel formats и backend mappings;
2. `#1049` — texture encoding в asset/native/runtime contract;
3. `#1050` — shader property encoding contract и миграция штатных shaders;
4. `#1051` — material binding validation и symbolic defaults;
5. `#1052` — texture inspector и encoding-aware preview;
6. `#1054` — glTF usage analysis и collision-only variants;
7. `#1053` — sRGB-correct mipmaps и backend parity;
8. `#1055` — итоговый editor/runtime/cross-backend integration gate.

`#1048` находится в `On Test`, её blocker-связи с последующими этапами сняты.
`#1049` реализован и переведён в `On Test`; `#1050` и `#1053` разблокированы
и находятся в `Ready`.
Остальные карточки сохраняют типизированные зависимости, соответствующие
последовательности миграции.
