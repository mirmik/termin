# termin-animation

`termin-animation` содержит animation clip/runtime API и Python bindings.

Связанные документы:

- [Module Map](../../../docs/modules.md#termin-animation)
- [canonical naming](../../../docs/architecture/2026-03-15-canonical-naming.md)

## Основные области

- Public headers в `include/`.
- Implementation в `src/`.
- Python package в `python/termin/animation`.

## Публичный API

The `termin-animation` distribution contains only the portable
`termin.animation` domain package. Entity playback and the
`termin.animation_components` wrapper are shipped by the Termin-owned
`termin-components-animation` distribution.

## Bulk track contract

`TcAnimationClip.set_tracks()` is the flat import adapter and atomically
publishes path-discriminated owned tracks. Runtime LINEAR/STEP translation and
scale values are `tc_vec3`; rotations are normalized `tc_quat` values. Cubic
vec3 keys own typed `in/value/out` triples, while cubic rotation keys keep
ordinary `tc_vec4` derivative tangents around a normalized quaternion value.
The source node index, interpolation metadata, vec3 scale and full glTF tensor
shape remain available through the flat `tracks` inspection adapter.

LINEAR and STEP translation/rotation/scale tracks return a discriminated typed
sample. Degenerate or non-finite rotation values are rejected during
publication without replacing the prior clip. Valid non-unit rotation values
are normalized during the same transaction; cubic tangents are never treated
as quaternions.
CUBICSPLINE and morph-weight tracks remain round-trippable but sampling them is
an explicit error until those player paths are implemented. The legacy
name-grouped channel API remains available only for existing assets. Its
dedicated translation and rotation fields use `tc_vec3` and `tc_quat` without
changing their packed ABI layout; channel replacement and sampling are
transactional as well.

## Файлы .tanim

`save_animation_clip()` сохраняет полное содержимое анимации в JSON UTF-8.
Это отдельный формат: `clip.serialize()` и kind-сериализация по-прежнему
записывают только ссылку `{type: "uuid", uuid, name}` для сцен и компонентов.
Такую ссылку нельзя использовать как самостоятельный файл анимации.

Пример `.tanim` версии 1:

```json
{
  "format": "termin.animation",
  "version": 1,
  "uuid": "walk-animation",
  "name": "Walk",
  "tps": 1.0,
  "loop": true,
  "tracks": [
    {
      "target_node_index": 0,
      "path": "translation",
      "interpolation": "step",
      "components": 3,
      "times": [0.0, 1.0],
      "values": [0.0, 0.0, 0.0, 1.0, 2.0, 3.0]
    }
  ]
}
```

Все поля обязательны; неизвестные поля, дубликаты JSON-ключей и неизвестные
версии отклоняются. UUID — непустая строка до 63 UTF-8 байт. Строки не должны
содержать NUL. `tps` — конечное положительное число, `loop` — JSON boolean.
`times` заданы в ticks, длительность вычисляется из ключей и `tps`, а не хранится
отдельным, потенциально рассогласованным полем.

`tracks` использует существующий плоский import/inspection adapter:

- `target_node_index` — неотрицательный int32, индекс исходного узла;
- `path` — `translation`, `rotation`, `scale` или `weights`;
- `interpolation` — `linear`, `step` или `cubic_spline`;
- `components` — 3 для translation/scale, 4 для rotation, положительная ширина
  набора morph weights;
- `times` — непустой массив конечных, строго возрастающих времён;
- `values` — плоский массив конечных чисел. Для LINEAR/STEP его длина равна
  `len(times) * components`, для CUBICSPLINE — втрое больше. На каждый cubic key
  записываются подряд входящая производная, значение и исходящая производная.

Кватернионы имеют порядок `x, y, z, w`. При native-публикации значения rotations
нормализуются; их cubic tangents остаются обычными vec4 производными без
нормализации. Сохранение CUBICSPLINE и weights поддерживается независимо от того,
реализовано ли их проигрывание. Текущие ограничения sampler описаны выше.

Вместо `tracks` допускается ровно одно поле `channels` для legacy name-based
анимации. Каждый channel содержит `target_name` (до 63 UTF-8 байт) и три
обязательных массива `translation_keys`, `rotation_keys`, `scale_keys`.
Ключ имеет вид `[time, [x, y, z]]`, `[time, [x, y, z, w]]` или `[time, scalar]`
соответственно. Пустой clip записывается как `tracks: []`; оба вида payload
одновременно запрещены.

`load_animation_clip()` и `parse_animation_content()` сначала проверяют документ
и строят detached native payload, затем публикуют его через
`tc_animation_publish_tracks/channels`. Существующий UUID, включая lazy
declaration, обновляется в том же handle; уже выданные ссылки видят новое
содержимое. Ошибка не меняет ни payload, ни metadata/version/loaded существующего
ресурса и не оставляет новую запись в registry. Наличие живого UUID не позволяет
пропустить чтение файла. GLB/FBX adapters используют тот же атомарный publisher.

Опциональный `uuid_hint` загрузчика задаёт авторитетный UUID владельца-ассета;
содержимое и исходный UUID документа всё равно валидируются. `AnimationClipAsset`
передаёт свой UUID при чтении, а при создании из готового clip наследует его UUID.

Перед сохранением lazy clip загружается через resource loader. Writer сначала
кодирует документ, затем заменяет целевой файл через временный файл в той же
директории. Ошибка загрузки или кодирования не затирает прежний файл. Ошибки I/O
и проверки формата логируются.

GLB extractor (`termin.glb.extractor.extract_animations`) пишет этот формат.
Старые `.tanim`, содержащие лишь UUID/name/type, необходимо заново извлечь из
исходного GLB/FBX: отсутствующий в них payload восстановить невозможно. Такие
файлы теперь отклоняются с диагностикой вместо создания пустой анимации.
