# ViewportRenderState

`ViewportRenderState` - это GPU output state, который `RenderingManager` использует для viewport или render target.

Исходник:

- `include/termin/render/viewport_render_state.hpp`

## Роль

Этот класс намеренно маленький: он владеет final output textures, нужными для рендера viewport/render target в конкретном размере и формате.

Он отслеживает:

- output color texture;
- output depth texture;
- output width/height;
- output color/depth formats;
- owning `IRenderDevice`.

## Жизненный цикл

State владеет GPU textures. Когда меняется size, format или device, старые textures освобождаются и создаются новые. При уничтожении state textures освобождаются через owning render device.

Так lifetime GPU output привязан к runtime object, которому этот output действительно нужен, а не к persistent scene configuration.

## Связь с RenderingManager

`RenderingManager` хранит эти states в maps, ключом которых является viewport handle или render target handle. Удаление viewport, detach scene или освобождение managed render target должны очищать соответствующий state.
