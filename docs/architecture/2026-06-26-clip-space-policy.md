# Clip Space Policy

Этот документ фиксирует целевую политику координатных преобразований для
3D-графики Termin. Это declaration of intent: новые рендеры и миграции
существующих рендеров должны двигаться к этой модели, даже если часть кода
временно остаётся на старой схеме.

## Проблема

Исторически Termin нормализовал API вокруг Vulkan-style clip space:

- `x = -1` - левый край viewport, `x = +1` - правый;
- `y = -1` - верх viewport, `y = +1` - низ viewport;
- `z = 0` - near plane, `z = 1` - far plane.

OpenGL приводится к этой модели через `glClipControl(GL_UPPER_LEFT,
GL_ZERO_TO_ONE)`. Vulkan уже совпадает с ней. Direct3D 11 отличается по
native clip-to-viewport mapping для Y: `clip_y = +1` попадает в верх viewport.

Исторический частичный workaround - адаптировать projection/view-projection на CPU
перед записью в GPU uniforms для D3D11. Он работает только для путей, которые
проходят через конкретный uniform builder, и ломает общую модель:

- CPU-код начинает получать разные матрицы в зависимости от backend-а;
- renderers с собственным MVP/VP легко выпадают из адаптации;
- screen-space shaders, которые используют clip/NDC как промежуточное
  пространство для pixel math, получают уже backend-native clip и начинают
  считать расширения в неправильной системе;
- исправления превращаются в набор частных `if (backend == D3D11)` около
  отдельных renderer-ов.

## Целевая модель

Termin различает пять пространств:

1. `World/View` - координаты сцены и камеры.
2. `TerminClip` - backend-neutral clip space движка: Y вниз, Z `[0, 1]`.
3. `NativeClip` - clip space, который конкретный graphics API ожидает в
   `SV_Position` / `gl_Position`.
4. `Pixel` - top-left origin, Y вниз.
5. `TextureUV` - `v = 0` означает визуальный верх содержимого.

Главный инвариант:

> Cameras, projection matrices, frame uniforms, public API, picking, raycast,
> CPU screen transforms and shader intermediate math use `TerminClip`.
> Conversion to `NativeClip` happens exactly once, at the final vertex shader
> output boundary.

То есть vertex shader может делать любые вычисления в `TerminClip`, но перед
записью final position обязан вызвать общий helper:

```slang
output.position = termin_to_native_clip(termin_clip);
```

Для Vulkan и OpenGL этот helper является identity. Для Direct3D 11 он
переворачивает `clip.y`.

## Shader prelude contract

`termin_prelude.slang` должен содержать единственный публичный способ
перевода final position из `TerminClip` в `NativeClip`:

```slang
float4 termin_to_native_clip(float4 clip)
{
#if TERMIN_NATIVE_CLIP_Y_UP
    clip.y = -clip.y;
#endif
    return clip;
}
```

Backend selection не должен расползаться по shader-коду. `termin_shaderc`
должен передавать capability define, например:

- `TERMIN_NATIVE_CLIP_Y_UP=0` для Vulkan;
- `TERMIN_NATIVE_CLIP_Y_UP=0` для OpenGL с `glClipControl`;
- `TERMIN_NATIVE_CLIP_Y_UP=1` для Direct3D 11.

Shader-ы не должны проверять `D3D11` напрямую, если им достаточно знать
orientation native clip Y.

## Renderer rules

### Обычные world-space vertex shaders

Mesh, tcplot 3D, world text, world lines, tubes, gizmos and similar renderers
должны считать world/view/projection transform в `TerminClip`:

```slang
let termin_clip = mul(u_view_projection, float4(world_pos, 1.0));
output.position = termin_to_native_clip(termin_clip);
```

CPU-side matrix adaptation для таких renderer-ов является legacy pattern и
не должна появляться в новых местах.

### Screen-space expansion shaders

Line billboard shaders, tcplot styled 2D lines, text/glyph placement and
прочие shader-ы, которые делают `clip -> ndc -> pixels -> clip`, должны
держать всю промежуточную математику в `TerminClip`.

Правильная форма:

```slang
let termin_clip = mul(u_view_projection, float4(world_pos, 1.0));
let pixel = termin_clip_to_pixel(termin_clip, viewport_size);
let expanded_termin_clip = termin_pixel_to_clip(pixel + offset, z, w, viewport_size);
output.position = termin_to_native_clip(expanded_termin_clip);
```

Неправильная форма:

```slang
// u_view_projection уже CPU-flipped под D3D11.
let native_clip = mul(u_view_projection, float4(world_pos, 1.0));
let pixel = clip_to_pixel(native_clip, viewport_size);
```

Такой код смешивает `NativeClip` и `TerminClip` и обычно проявляется как
вертикально перевёрнутые billboard/line/tcplot элементы на D3D11.

### Fullscreen and postprocess

Fullscreen triangles/quads and postprocess passes должны выбрать одну модель:

- preferred: vertices задаются в `TerminClip`, final vertex output проходит
  через `termin_to_native_clip`;
- допустимое исключение: pass явно документирован как backend-native и не
  использует общие fullscreen helpers.

Backend-specific fullscreen vertex arrays являются временным compatibility
path и не должны множиться.

### CPU tools

Picking, raycast, camera `screen_point_to_ray`, CPU projection helpers and
test utilities must not consume backend-native matrices. Они работают только
с `TerminClip`.

## Запреты

- Не добавлять новые `adapt_projection_for_backend()` /
  `adapt_view_projection_for_backend()` вызовы в renderer-specific code.
- Не передавать D3D11-flipped projection в public API или CPU picking/math.
- Не делать pixel-space expansion из backend-native clip.
- Не добавлять backend branches в user-facing examples ради координатного
  flip-а.
- Не использовать raw D3D11 checks в shader-ах, если достаточно capability
  define из prelude.

## Migration plan

### Phase 0: audit and guardrails

- Зафиксировать этот документ как source of truth.
- Добавить target/capability defines в `termin_shaderc`.
- Расширить `termin_prelude.slang` helper-ами:
  - `termin_to_native_clip(float4)`;
  - `termin_clip_to_pixel(float4, float2)`;
  - `termin_pixel_to_clip(float2, float, float, float2)`.
- Добавить shader compile tests для Vulkan/OpenGL/D3D11 target defines.
- Добавить grep/lint check для builtin Slang vertex shaders: final assignment
  to `SV_Position` должен проходить через `termin_to_native_clip`, кроме
  явно помеченных backend-native exceptions.

### Phase 1: migrate builtin world-space shaders

- Mesh/material vertex paths.
- tcplot 3D.
- world text/text3D.
- world line billboard renderer.
- world tube line renderer.
- debug/gizmo/solid primitive/immediate renderer shaders.

Эта фаза внедрена для основных builtin world-space paths: final vertex output
проходит через `termin_to_native_clip`, а CPU-side D3D11 projection adaptation
не должна возвращаться в эти renderer-ы.

### Phase 2: migrate screen-space and 2D pixel shaders

- screen-space line renderer;
- tcplot 2D line and styled line shaders;
- canvas2d solid/texture shaders;
- text2d bitmap/SDF shaders;
- glyph/text placement shaders, если они делают clip/pixel roundtrip;
- any billboard shaders with viewport-size uniforms.

Эта фаза внедрена для текущих builtin 2D pixel paths. CPU projection builders
создают canonical TerminClip matrices, вся промежуточная pixel math остаётся
в `TerminClip`, helper вызывается только на final output.

### Phase 3: remove CPU-side clip adaptation

- `termin-render` frame uniforms загружают canonical projection and
  view-projection.
- `tgfx2` immediate/primitive/line renderers не адаптируют VP на CPU.
- `tcplot` не держит backend-specific MVP state.
- `clip_space.hpp/cpp` adapter helpers удалены.

После этой фазы `TerminClip -> NativeClip` для scene и 2D pixel paths
существует только в shader prelude или в явно задокументированных
backend-native exceptions. Fullscreen/postprocess paths мигрируются отдельной
фазой и не должны возвращать CPU-side projection adaptation.

### Phase 4: fullscreen/postprocess cleanup

- Перевести fullscreen helpers на canonical `TerminClip` vertices.
- Убрать backend-specific fullscreen vertex arrays, если они больше не нужны.
- Проверить present/blit/postprocess passes на отсутствие второго Y-flip.

### Phase 5: tests and examples

- Добавить asymmetric 3D reference scene: верх/низ должны совпадать на
  Vulkan/OpenGL/D3D11.
- Добавить D3D11 regression для billboard/world lines.
- Добавить D3D11 regression для screen-space line expansion near top-left.
- Добавить tcplot 3D helix screenshot/reference smoke.
- Обновить examples так, чтобы они не передавали backend-adapted matrices.

## Completion criteria

Миграция считается завершённой, когда:

- `docs/coord_system.md` описывает shader-boundary conversion как текущую
  политику, а не как план;
- builtin Slang vertex shaders используют `termin_to_native_clip` для final
  position;
- production renderers не вызывают D3D11 projection adapters на CPU;
- D3D11, Vulkan and OpenGL проходят одинаковые orientation tests для 3D/2D,
  billboard lines and screen-space expansion;
- examples не содержат backend-specific coordinate branches.
