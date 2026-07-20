# Display Render Surface Boundary

Дата: 2026-07-19

Статус: Accepted, ownership refinement implemented by #686

## Контекст

`tc_render_surface` возник как общий интерфейс оконной и offscreen-поверхности.
Из-за этого его vtable одновременно содержит:

- размер и выходную текстуру display;
- OpenGL framebuffer/context/share-group operations;
- swap/presentation и window lifecycle;
- cursor/event operations;
- хранимый `tc_input_manager`;
- resize callback и external-language adapter lifecycle.

Современная композиция этим интерфейсом окна не пользуется. Реальная production
реализация — внутренний `OffscreenRenderSurface`:
`tc_display` собирает в его текстуру viewports, после чего текстуру потребляет
`Viewport3D`, `BackendWindow` или другой presenter. В редакторе несколько таких
поверхностей могут быть встроены в один GUI, который только затем презентуется
одним `BackendWindow`.

`BackendWindow` уже выделен в `termin-window`. Он владеет native window,
per-window presentation resources и системными событиями, но не является
владельцем graphics host/device и не является выходной поверхностью
конкретного `tc_display`. Единственный владелец graphics domain —
`tgfx::GraphicsHost` из `termin-graphics`; `BackendWindowSystem` отвечает
только за platform bootstrap и создание presentation targets.
`WindowedGraphicsSession` фиксирует их совместный lifetime, не дублируя
device/context API.

## Решение

### Разделение ролей

Роли закрепляются следующим образом:

```text
input host (BackendWindow или Viewport3D)
    -> tc_display input endpoint
    -> viewport input managers

tc_display
    -> tc_render_surface
    -> результирующая tgfx texture
    -> Viewport3D / BackendWindow / WPF presenter / иной compositor
```

`tc_render_surface` остаётся в `termin-display` и является узким
языково-нейтральным C ABI выходной render surface для `tc_display`. Он не
переносится в `termin-window`, а `BackendWindow` не обязан и не должен его
реализовывать.

Целевой обязательный контракт `tc_render_surface` содержит только:

- pixel extent;
- resize request и resize notification;
- результирующую backend-neutral tgfx color texture;
- graphics-domain key;
- semantic destroy и storage deleter для enclosing native/Python/C# adapter.

Из core surface API удаляются:

- `get_framebuffer`, `make_current`, `context_key`, `share_group_key`;
- `swap_buffers` и `poll_events`;
- `get_window_size`, `should_close`, `set_should_close`, `get_cursor_pos`;
- хранимый `tc_input_manager` и его setters/getters;
- legacy FBO fallback и no-op implementations этих методов.

Соответствующие window/context delegation methods удаляются и из `tc_display`.
Физическая презентация остаётся обязанностью runtime/application host через
`BackendWindow::present()` либо иной platform presenter.

### Input ownership и координаты

Display-level input router принадлежит `tc_display`, а не surface. `tc_display`
предоставляет стабильный input endpoint либо typed dispatch operations для
pointer, wheel, key и text events. Замена surface не меняет и не
переподключает input router.

Pointer coordinates на границе `tc_display` задаются в pixel coordinates
display с origin top-left. Host adapter отвечает за перевод своей системы
координат в этот формат:

- `BackendWindow` использует framebuffer position;
- embedded `Viewport3D` переводит widget-local position в pixel extent
  прикреплённого display;
- WPF и другие hosts выполняют эквивалентное DPI-aware преобразование.

Window logical size не является свойством render surface.

### Ownership и graphics domain

Одна `tc_render_surface` одновременно прикреплена не более чем к одному
`tc_display`. Повторное attach без detach должно диагностироваться, а не
перетирать единственный resize subscriber.

Успешные `tc_display_new` и `tc_display_set_surface` передают surface в
эксклюзивное владение display. Неуспешная операция не меняет ownership caller.
Replacement сначала полностью принимает и публикует новую surface, затем
вызывает semantic `destroy` и storage deleter старой. Явное уничтожение display
тем же способом уничтожает текущую surface до teardown graphics device.
Wrapper destructors, Python GC и C# finalizers не являются authority native
lifetime.

Surface texture обязана принадлежать тому же graphics-device domain, которым
`RenderingManager` выполняет clear/blit. Несовпадение должно обнаруживаться
fail-fast до GPU operation. C ABI не раскрывает `IRenderDevice*` только ради
этой проверки; конкретный domain token/validation mechanism определяется при
реализации вместе с single graphics domain work.

### Имена

Имя `tc_render_surface` сохраняется: после очистки оно соответствует роли
объекта. Отдельная публичная Python/C++ identity offscreen surface удалена;
backend создаётся через `create_offscreen_display` / `Display.offscreen`, а
texture, size, resize и input доступны через один display handle.

## Обоснование

Превращение `BackendWindow` в `tc_render_surface` оптимизировало бы только
прямой player/runtime path ценой смешения embeddable output и swapchain window.
Редактор, WPF hosting, headless rendering, post-processing и composition всё
равно требуют offscreen texture.

Узкий C ABI сохраняет удобную границу для C#, Python и других языков, не
заставляя их реализовывать C++ `BackendWindow`. Удаление optional no-op методов
делает отсутствие capability структурным, а не скрытым возвратом нулей.

## Рассмотренные альтернативы

### Сделать BackendWindow реализацией tc_render_surface

Отвергнуто как базовая модель. Физическое окно является input/presentation
host, а не обязательным render output одного display. В редакторе это отношение
имеет multiplicity many-displays-to-one-window.

### Перенести tc_render_surface в termin-window

Отвергнуто. Основная реализация — offscreen output `tc_display`; она не является
оконной инфраструктурой. `termin-window` должен оставаться lightweight и не
зависеть от engine display/input integration.

### Разделить текущий vtable на набор optional capability interfaces

Отвергнуто для core surface. У window/context/event capabilities нет живого
потребителя через `tc_render_surface`, поэтому их следует удалить, а не
перепаковать. Отдельные capabilities могут появиться на соответствующей
границе `BackendWindow` или graphics device при наличии реального consumer.

### Сразу рендерить player в backbuffer

Отложено как измеряемая оптимизация. Если fullscreen present pass станет
значимой стоимостью, presenter сможет временно выдать acquired backbuffer как
render target. Это не требует делать `BackendWindow` разновидностью
`tc_render_surface` и не меняет базовый offscreen contract.

## Последствия и риски

- C/Python/C# vtable и bindings меняются несовместимо; миграция должна удалить
  старые поля и adapters в одном контролируемом проходе.
- WPF scene examples с raw GL framebuffer и нулевой tgfx texture уже не
  соответствуют текущему presenter и должны быть переведены либо удалены.
- `EditorInteractionSystem` больше не может получать logical window size из
  display; input bridge должен нормализовать координаты до display pixels.
- `Viewport3D` получает texture/size/resize и input через один copyable display
  facade; удержание facade не влияет на native lifetime.
- display должен быть явно уничтожен раньше graphics device.

## Последующая работа

1. #679 — перевести C#/WPF scene hosting на обязательную D3D11 tgfx texture и
   display input endpoint без `BackendWindow` и OpenGL.
2. Для #679 дополнительно
   требуется именованный Windows D3D11/WPF smoke.

## Ссылки

- Kanboard: #637, #677, #678, #679, #684, #685, #686;
- [целевой display surface contract](../architecture/2026-07-19-display-render-surface-contract.md);
- `termin-display/include/render/tc_render_surface.h`;
- `termin-display/src/tc_display_input_router.c`;
- `termin-display/src/platform/offscreen_render_surface.cpp`;
- `termin-engine/src/display_presenter.cpp`;
- `termin-window/include/termin/platform/backend_window.hpp`.
