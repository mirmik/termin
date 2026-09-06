# Седьмой пакет исправлений графического стека — 2026-09-06

Продолжение [шестого пакета](2026-09-06-graphics-repair-pass-6.md), umbrella #2230.
Rect clear #2211 закрыта; разделение texture views #2214 реализовано и
переведено в On Test: остаётся браузерная проверка WebGPU.

## Прямоугольная очистка

Публичный контракт `IRenderDevice::clear_texture`: ColorAttachment texture,
mip 0, все поддерживаемые array layers; half-open прямоугольник в top-left
координатах обрезается по размеру texture. Пустые и reversed rect — no-op;
соседние пиксели, остальные mip levels и caller graphics state сохраняются.
OpenGL и WebGPU по-прежнему отвергают создание array textures.

Vulkan выполняет очистку через LOAD/STORE render pass и
[`vkCmdClearAttachments`](https://docs.vulkan.org/refpages/latest/refpages/source/vkCmdClearAttachments.html).
Framebuffer использует отдельный attachment view. Прямоугольник больше не
игнорируется, MSAA очищается через color attachment writes. Layout dependencies
охватывают предыдущие и последующие обращения, включая неизменившийся layout.
Операция сохраняет существующий prelude ordering: записывается до следующего
submitted command list. Общая ревизия порядка команд остаётся в #2230.

OpenGL использует scissor с backend coordinate conversion и `glClearBufferfv`.
Сохраняются framebuffer binding, scissor box/enable и indexed color mask;
viewport и clear color не меняются. D3D11/WebGPU уже очищали clipped rect,
теперь их empty/reversed ветки согласованы с общим no-op контрактом.

## Sampling и attachment views

Vulkan и WebGPU создают независимые views: sampling видит полный mip chain,
attachment — mip 0. В `descriptors.hpp` зафиксирован существующий контракт:
ordinary render pass использует single-layer texture, multiview — первые
`view_count` layers. Attachment views выбирают color либо depth/stencil aspects;
sampled depth/stencil view предоставляет depth. Создание, external/surface
wrapping и уничтожение учитывают оба native view.

Новая D24/S8 regression выявила VUID-03320: прежний helper возвращал только
DEPTH также для layout transitions. Теперь full-image aspect mask отделена
от single data aspect: transitions охватывают DEPTH|STENCIL, sampling и native
transfer regions сохраняют отдельный DEPTH aspect. Формат CPU payload и перенос
самого stencil при upload/copy не исправлены этим пакетом: отдельная #2260.

## Проверки

- `tgfx2_vulkan_clear_rect_test`: каждый пиксель asymmetric 9×5 texture,
  partial/full/clipped/empty/reversed/extreme-int rect, mipmapped target и
  4× MSAA с resolve.
- `tgfx2_opengl_clear_texture`: каждый пиксель 7×5, десять rect cases,
  scissor on/off, сохранение draw/read FBO, viewport, scissor, clear value,
  двух indexed color masks; Modern/Constrained33 policy на desktop GL context;
  отдельная 4× MSAA clear/resolve regression.
- `tgfx2_vulkan_texture_views_test`: render-pass clear и clear_texture mip 0,
  сохранение заранее загруженного верхнего mip, explicit texelFetch и
  textureQueryLevels; D24/S8 attachment затем depth sampling.
- Browser texture-ops smoke теперь очищает, рендерит и семплирует texture с
  четырьмя mip levels, сохраняя прежние pixel expectations.

Первый native прогон поймал D24/S8 validation errors; они исправлены до
финального оконного прогона. `task test:cpp -- --window-tests`:
**257 passed, 1 failed из 258**, без Vulkan validation errors.
Все три новые regression прошли. Оставшийся failure —
`termin_window_opengl33_tier`, прежняя #2253. Две inventory entries вне профиля.

Полный `task build` прошёл вместе с SDK Python/native import checks.
Focused `task lint:cpp` для изменённых OpenGL/Vulkan translation units прошёл;
осталось прежнее необязательное предупреждение о размере
`get_or_create_render_pass`.

Полный ASan/UBSan offscreen прогон на llvmpipe: **238 passed, 4 failed из 242**,
без skips и Vulkan validation errors. Обе новые Vulkan regression прошли.
Оставшиеся failures — прежние #2238 (два Widget leaks), #2240 (Release assert
policy), #2241 (FEM UAF). Профиль: `--no-opengl --no-sdl`,
`VK_LOADER_LAYERS_DISABLE=~implicit~`, shader root `sdk/share/termin`,
ASan/UBSan/LeakSanitizer без suppressions. Оконные #2253/#2255 этим sanitizer
профилем не проверялись.

`task build:web` не смог начать сборку: Emscripten не установлен. WebGPU
изменения не объявляются проверенными сборкой или браузером. Gate для #2214:
в подготовленном Web окружении выполнить `task build:web -- --setup` и
`task test:web:browser`, проверить texture-ops pixels и отсутствие validation
errors. Windows D3D11 и Android/Quest этим desktop прогоном не проверены.

Логи: `/tmp/termin-graphics-pass7-window.log`,
`/tmp/termin-graphics-pass7-asan.log`, `/tmp/termin-graphics-pass7-sdk.log`,
`/tmp/termin-graphics-pass7-lint-final.log`, `/tmp/termin-graphics-pass7-web.log`.
