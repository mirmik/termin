# termin-graphics: архитектурный review

Дата: 2026-06-21

## Краткий Вердикт

`termin-graphics` в целом построен правильно как GPU substrate для остального
рендеринга. Граница модуля описана в `docs/modules.md` и локальных документах,
а фактические зависимости в основном соответствуют этой границе: модуль не
тащит внутрь frame graph, editor UI или application policy. Это хороший знак:
`termin-graphics` выглядит как нижний backend-neutral слой, а не как случайно
выросшая часть `termin-app`.

Главная сильная сторона текущей архитектуры - новая модель shader resource
binding:

```text
shader semantic resources
  -> BackendBindingPlan
  -> BoundResourceSetDesc
  -> backend-native command execution
```

Она правильно разделяет semantic resource contract и backend placement. Shader
source и pass code должны мыслить именованными ресурсами и scopes, а backend
получает уже рассчитанный placement для Vulkan, OpenGL или D3D11.

При этом модуль находится в середине активной миграции. Архитектура уже имеет
правильное направление, но несколько публичных контрактов пока не доведены до
жесткого состояния.

## Что Построено Хорошо

### Границы Модуля

`termin-graphics` владеет backend-neutral GPU API, tgfx/tgfx2 device/context,
texture pools, canvas/line/text utilities и low-level `tc_*` GPU resource
bridges. Это совпадает с описанием в `docs/modules.md` и
`termin-graphics/docs/index.md`.

Важный плюс: frame graph/debugger/render pipeline policy остается выше, в
`termin-render` / `termin-render-passes`. Использование `tgfx2` типов в этих
модулях выглядит нормальной зависимостью сверху вниз.

### Backend Binding Plan

Документы `termin-graphics/docs/architecture/pipeline-layout.md`,
`shader-resource-contracts.md` и `backend-binding-plan.md` описывают здоровую
модель ownership:

- shader source владеет resource names, kinds, scopes и stage IO;
- `termin_shaderc` владеет backend placement и sidecar metadata;
- runtime биндует ресурсы по имени;
- backend применяет уже resolved placement.

Это правильная архитектурная линия. Она особенно важна для D3D11, потому что
там нет Vulkan-style descriptor sets, и попытка сделать "один общий API,
похожий на Vulkan" быстро начинает ломаться.

### Backend Isolation

В CMake Vulkan dependency держится private для `termin_graphics2`, D3D11
включается опцией, OpenGL остается отдельным backend path. Downstream-модули
могут линковаться к `tgfx::termin_graphics2`, не становясь напрямую зависимыми
от Vulkan SDK.

Тестовый контур тоже неплохой: есть smoke tests для device factory, OpenGL,
Vulkan, D3D11, shader compiler Python tests и resource binding tests.

## Основные Архитектурные Риски

### 1. Shader Placement Policy Все Еще Переходная

Целевая модель говорит, что backend placement должен приходить из явной
metadata/policy модели.

Статус 2026-06-27:

- runtime built-in catalog path больше не хранит resources/layout/contract;
- compiler-side name table (`per_frame`, `material`, `shadow_maps`,
  `bone_block` и т.п.) удалена;
- `termin_shaderc` пока назначает transitional `set/binding` через
  deterministic allocator по `scope + resource kind + stable resource name`;
- D3D11 placement уже живет отдельной `d3d11` metadata в sidecar.

Исторически похожая таблица существовала и в runtime built-in catalog path, но
этот путь удален: built-in registry больше не хранит resources/layout/contract,
а runtime берет layout из artifact-adjacent sidecar.

Оставшийся источник истины:

1. artifact/layout sidecar, сгенерированный `termin_shaderc`;

Проблема уже не в magic names, а в том, что generic `set/binding` в sidecar
все еще несет backend placement до финального `backend binding plan` слоя.
Это приемлемо как переходная форма, но не должно разрастаться обратно в
ручные таблицы или catalog metadata.

Уже заведено: Kanboard #85 `[graphics/shaders] Убрать magic names из shader compilation paths`.

### 2. IRenderDevice Слишком Широкий

`IRenderDevice` сейчас совмещает несколько разных ролей:

- обязательные GPU operations: create/destroy/upload/read/submit/present;
- resource set creation, включая legacy numeric и migrated bound paths;
- external native resource wrapping;
- blit/clear helpers;
- sync/state hooks;
- single-pixel и full-texture readback;
- transient vertex ring;
- dynamic UBO ring;
- `tc_texture` / `tc_mesh` / `tc_shader` per-device cache adapters.

Это выглядит удобно как один "device object", но архитектурно размывает
mandatory и optional capabilities. Из-за этого в публичном интерфейсе много
default `false`, no-op или `throw not supported`. Такой стиль скрывает
capability boundary: caller видит метод как часть общего контракта, хотя на
самом деле это optional feature.

Лучше разделить:

- минимальный обязательный `IRenderDevice`;
- readback capability;
- external interop capability;
- transient/ring allocator capability;
- presentation/blit helper;
- canonical `tc_*` materialization adapter.

Уже заведено: Kanboard #95
`[graphics] Разделить IRenderDevice на capability-specific interfaces`.

### 3. Capability Contract Местами Переобещает

Конкретный пример: D3D11 backend выставляет `supports_compute=true` для feature
level 11, но `D3D11RenderDevice::create_command_list(QueueType::Compute)`
бросает исключение: поддержаны только graphics command lists. При этом
`ICommandList` уже содержит `dispatch()`, но полноценного compute pipeline
contract для D3D11 нет.

Похожий пример: editor interaction path вызывает
`IRenderDevice::read_pixel_depth_float()`, OpenGL/Vulkan переопределяют этот
метод, а D3D11 реализует только `read_texture_depth_float()`. Для single-pixel
depth picking D3D11 фактически получает default `false`.

Это не просто backend TODO, а нарушение публичного capability contract:
capabilities должны описывать реализованные runtime paths, а не нативные
возможности API.

Уже заведено: Kanboard #93
`[graphics/d3d11] Fix capability/readback contract mismatches`.

### 4. Backend Parity После D3D11 Еще Не Закрыт

D3D11 уже встроен в `tgfx2/device_factory`, shader artifact paths,
`BackendWindow` и smoke tests. Но вокруг него остались следы двухbackendовой
модели и incomplete parity:

- public build/runtime policy всё еще в основном Vulkan/OpenGL-oriented;
- default compiled backend prefers Vulkan, then OpenGL, then D3D11;
- `D3D11CommandList` логирует unsupported dynamic offsets и storage buffers;
- shader/package/export paths не везде считают D3D11 равноправной целью.

Это нормально для активной миграции, но до стабилизации D3D11 нельзя считать
tgfx2 backend contract полностью закрытым.

Уже заведено: Kanboard #89
`[graphics/d3d11] Закрыть backend parity после добавления D3D11`.

### 5. Legacy Numeric Binding Все Еще В Горячем Пути

`ResourceBinding` и `ResourceSetDesc` сохранены как compatibility path, а
`RenderContext2` одновременно поддерживает numeric bindings и symbolic
bindings. Документы честно называют numeric API legacy side channel.

Риск в том, что новый код может продолжить добавлять numeric slots, потому что
API остается рядом и работает. Для миграции это допустимо, но нужно удерживать
правило: production migrated shader/material code должен идти через
bind-by-name + `BackendBindingPlan`, а numeric API должен оставаться только для
низкоуровневых smoke tests и явно legacy paths.

## Рекомендованный Порядок Работ

1. Закрыть #85: убрать magic-name placement из `termin_shaderc` и
   `builtin_shader_sources`, оставить один явный источник layout policy.
2. Закрыть #95: сузить `IRenderDevice`, вынести optional operations в
   capability-specific interfaces или adapter services.
3. Закрыть #93 и часть #89: capabilities должны отражать только реально
   реализованные backend paths.
4. После этого делать #94 по `FrontFace::CCW` / winding convention. Winding
   migration лучше не смешивать с shader binding и backend parity, иначе
   визуальные регрессии будет трудно локализовать.

## Итоговая Оценка

Архитектурное направление у `termin-graphics` хорошее. Самое важное уже
сформулировано правильно: semantic shader resources отделены от backend
placement, а backend-ы должны применять metadata, а не угадывать смысл по
слотам.

Главная проблема не в неправильной модели, а в незавершенности миграции:
старые numeric paths, magic-name placement, широкий device interface и
неполная D3D11 parity пока делают систему хрупкой. Если закрыть эти хвосты в
порядке выше, `termin-graphics` может стать устойчивой и масштабируемой базой
для Vulkan/OpenGL/D3D11, Android/OpenXR и будущих backend-ов.
