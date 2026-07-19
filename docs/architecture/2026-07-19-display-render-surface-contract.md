# Display Render Surface Contract

Статус реализации: принято 2026-07-19; input ownership реализован в #677,
остальные этапы миграции ещё не завершены.

Обоснование и рассмотренные альтернативы зафиксированы в
[протоколе архитектурного совета](../architecture-council/2026-07-19-display-render-surface-boundary.md).

## Границы ответственности

`tc_display` представляет логический display: набор viewports, их layout,
выходную render surface и display-level input routing.

`tc_render_surface` представляет backend-neutral texture output одного
`tc_display`. Это C ABI для native и внешних реализаций, а не абстракция окна.

`BackendWindow` представляет native window, системные события и физическую
презентацию. Он принадлежит `termin-window` и не реализует
`tc_render_surface`.

```text
                         +-> Viewport3D -> UI composition -> BackendWindow
tc_display -> surface ---+-> BackendWindow::present (simple player)
                         +-> WPF / streaming / readback presenter

BackendWindow / Viewport3D / WPF input
    -> tc_display input endpoint
    -> viewport input manager
```

## Целевой surface ABI

Обязательные данные и операции:

- размер в физических pixels;
- результирующая tgfx color texture;
- уведомление display об изменении размера;
- C adapter state и однозначный lifecycle.

Surface не предоставляет window, input, presentation или graphics-context
operations. В частности, в целевом API отсутствуют raw framebuffer, OpenGL
context/share-group, polling, cursor, close state и swap buffers.

Отсутствующая или принадлежащая другому graphics domain texture является
ошибкой контракта и диагностируется до clear/blit. Legacy FBO fallback не
поддерживается.

## Input contract

Display-level router принадлежит `tc_display` и живёт независимо от замены
surface. Host отправляет pointer, wheel, key и text events в display endpoint.

`tc_display` создаёт endpoint вместе с собой и уничтожает его в своём
lifecycle. C API `tc_display_dispatch_*`, C++ window bridge и Python `Display`
bindings предоставляют typed dispatch; внешний код не создаёт и не освобождает
router отдельно.

Pointer positions передаются в pixel coordinates display с origin top-left.
Перевод из logical window coordinates, WPF device-independent pixels или
widget-local coordinates выполняет host adapter. Благодаря этому render
surface хранит только один pixel extent и не знает о logical window size.

## Attachment и lifetime

- Surface может быть прикреплена не более чем к одному display одновременно.
- Display подписывается на resize при attach и снимает подписку при detach.
- Display не должен продолжать использовать уничтоженную surface.
- Surface texture и RenderingManager обязаны находиться в одном graphics-device
  domain.
- Конкретная offscreen surface освобождает GPU resources до уничтожения device.

RAII ownership и shutdown ordering реализуются в рамках #638; до завершения
этой миграции текущий leaked pool/manual `close()` не считается целевым
поведением.

Миграционный порядок закреплён карточками #677 (input), #678 (surface ABI),
#638 (lifetime/rename) и #679 (C#/WPF hosting).

## Presentation

После composition `tc_display` оставляет результат в surface texture. Выбор
физического presenter принадлежит application/runtime host:

- простой player передаёт texture в `BackendWindow::present()`;
- редактор рисует texture внутри `Viewport3D`, затем презентует итоговый UI;
- WPF host импортирует texture в свой D3D11/D3DImage path.

Возможный direct-to-backbuffer path является отдельной измеряемой
оптимизацией. Он не изменяет базовый surface ABI и не делает window владельцем
display input.

## Migration gate

Миграция завершена, когда:

- в `tc_render_surface_vtable` нет window/OpenGL/input/presentation методов;
- `tc_display` владеет input router и не делегирует window lifecycle surface;
- `OffscreenRenderSurface` не содержит no-op window/context methods;
- `RenderingManager` использует обязательную tgfx texture без FBO fallback,
  `make_current()` и `swap_buffers()`;
- native editor, player и Viewport3D используют display input endpoint;
- C#/WPF surface adapter предоставляет рабочую tgfx texture либо удалён как
  неподдерживаемый;
- `FBOSurface` заменён на `OffscreenRenderSurface` во внешнем API;
- tests покрывают resize/attach, input coordinates, missing/wrong-domain
  texture и deterministic shutdown.
