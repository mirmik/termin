# ViewportRenderState

`ViewportRenderState` - это небольшой internal GPU output state helper, который `RenderingManager` использует там, где runtime output textures не принадлежат persistent scene configuration.

Исходник:

- `include/termin/render/viewport_render_state.hpp`

## Роль

Этот класс намеренно маленький: он владеет final output textures в конкретном размере и формате.

Он отслеживает:

- output color texture;
- output depth texture;
- output width/height;
- output color/depth formats;
- owning `IRenderDevice`.

## Жизненный цикл

State владеет GPU textures. Когда меняется size, format или device, старые textures освобождаются и создаются новые. При уничтожении state textures освобождаются через owning render device.

Так lifetime GPU output привязан к runtime object, которому этот output действительно нужен, а не к persistent scene configuration.

Viewport без `RenderTarget` не является владельцем output textures. Это пустой presentation slot: он может существовать в display layout, но ничего не рендерит и не презентит, пока ему явно не назначен `tc_render_target`.

## Связь с RenderingManager

`RenderingManager` хранит эти states в maps для runtime-owned output. Удаление viewport, detach scene или освобождение managed render target должны очищать соответствующий state.
