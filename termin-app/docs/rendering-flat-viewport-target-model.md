# Плоская модель Viewport / RenderTarget

## Цель

Вернуть владение render-ресурсами к плоской модели:

- `RenderTarget` — рендеримая единица: сцена, камера, пайплайн, layer mask,
  флаг enabled, текстуры и политика разрешения.
- `Viewport` ссылается на `RenderTarget`, но не владеет им.
- `Viewport` определяет, где и как результат `RenderTarget` презентуется на
  display.
- `RenderingManager` умеет независимо attach/detach render target-ы и
  viewport-ы.

Модель должна одинаково работать для editor displays и scene displays, без
дублирования lifecycle-логики.

## Основные Контракты

### RenderTarget

`RenderTarget` владеет входами рендера и выходными render-ресурсами:

- scene
- camera
- pipeline
- layer mask
- enabled flag
- color/depth textures
- width/height
- dynamic resolution flag

Если включен dynamic resolution, `width` и `height` являются runtime-значениями,
которые задаются pixel rect-ом viewport-а, презентующего этот target. Эти
значения не должны записываться обратно в постоянное состояние сцены при
сериализации.

Если dynamic resolution выключен, `width` и `height` являются авторскими
значениями и сериализуются через `RenderTargetConfig`.

### Viewport

`Viewport` владеет состоянием презентации:

- display region
- pixel rect
- depth
- input mode
- enabled flag
- editor input blocking flag
- handle связанного render target-а
- optional internal editor entities
- optional scene-pipeline management marker

`Viewport` не выделяет и не освобождает связанный `RenderTarget`. Удаление
viewport-а удаляет только презентацию. Связанный render target остается живым,
пока владелец render target-а или `RenderingManager` явно не detach/free его.

### RenderingManager

`RenderingManager` отслеживает live render-ресурсы сцены:

- registered displays
- registered render targets
- registered viewports
- compiled scene pipelines
- runtime render states

Attach сцены должен быть разбит на явные фазы:

1. attach render targets из `render_target_configs`
2. attach viewports из `viewport_configs`
3. bind viewport references к render targets
4. compile scene pipelines
5. mark pipeline-managed viewports

Detach сцены должен быть зеркальным:

1. detach viewports этой сцены
2. detach render targets этой сцены
3. clear render states
4. clear scene pipelines
5. auto-remove empty scene displays, если display так сконфигурирован

Editor displays используют те же primitives, но регистрируются в editor scope и
пропускаются при scene detach.

## Сериализация

Постоянное render-состояние сцены:

- `RenderTargetConfig`: авторские настройки render target-а.
- `ViewportConfig`: display/region/input/presentation settings плюс ссылка на
  render target.

`ViewportConfig` должен ссылаться на render target по стабильной идентичности,
предпочтительно по name или UUID. После переноса владения в `RenderTargetConfig`
он не должен дублировать camera/pipeline settings.

Для совместимости миграции старые inline-поля `ViewportConfig.render_target`
можно продолжать читать и преобразовывать в неявный render target config. Новые
сохранения должны писать плоскую модель.

Render target с dynamic resolution должен сериализовать policy flag, а не
текущий runtime size. Fixed-size render target сериализует `width` и `height`.

## Editor И Scene Scopes

Сейчас код разошелся на две параллельные ветки:

- editor display / editor viewport / editor render target
- scene display / scene viewport / scene render target

Повторяющуюся реализацию нужно схлопнуть в общий helper для attach/detach.

Предлагаемое разбиение:

- `RenderDisplayScope`: определяет, к какому scope относятся ресурсы —
  `editor` или `scene`, и отвечает за регистрацию в `RenderingManager`.
- `RenderAttachment`: attach/detach группы render targets и viewports для одной
  сцены и одного scope.
- `EditorSceneAttachment`: хранит editor-specific camera/tools/state, но
  делегирует attach/detach viewport/render-target ресурсов в `RenderAttachment`.
- `RenderingModel`: остается UI-agnostic и делегирует native resource lifecycle
  в `RenderingManager`/`RenderAttachment`.

Так editor-specific поведение остается в editor-коде, но lifecycle
display/viewport/render-target перестает существовать во второй копии.

## Headless Инварианты

После открытия editor scene:

- существует один editor display
- существует один editor viewport
- существует один editor render target
- editor render target ссылается на editor scene, editor camera и editor pipeline
- scene display не существует, если его не требуют scene configs

После входа в game mode:

- editor scene mode равен inactive
- game scene mode равен play
- editor display все еще содержит ровно один editor viewport
- editor render target теперь ссылается на game scene и editor camera
- scene displays содержат только viewports game scene
- scene render targets принадлежат game scene
- render targets/viewports editor scene detach-нуты
- compiled pipelines существуют только для attached render scenes

После выхода из game mode:

- game scene закрыта
- editor scene mode равен stop
- editor display все еще содержит ровно один editor viewport
- editor render target ссылается на editor scene и editor camera
- game-scene viewports/render targets/pipelines удалены
- editor scene viewports/render targets/pipelines восстановлены из configs
- глобальные counts viewport/render-target/pipeline вернулись к baseline до Play

## Этапы Миграции

1. [x] Перенести `override_resolution` из `Viewport` в `RenderTarget` как
   `dynamic_resolution`.
2. [x] Изменить `tc_viewport_set_render_target()` так, чтобы он только менял
   ссылку. Он не должен free-ить старый render target и не должен lock/free-ить
   новый.
3. [x] Прекратить выделять render target внутри `tc_viewport_pool_alloc()`.
4. [x] Научить `RenderingManager` явно создавать/регистрировать render target-ы до
   создания viewport-ов.
5. [x] Расширить `ViewportConfig` ссылкой на render target и перенести inline
   camera/pipeline fields в `RenderTargetConfig`.
6. [x] Обновить render paths так, чтобы render target resize выполнялся только при
   включенном `dynamic_resolution`.
7. [x] Вынести общую attach/detach логику для editor и scene display scopes.
8. [x] Добавить C++ headless tests на native manager counts и Python headless tests
   на game-mode orchestration.
