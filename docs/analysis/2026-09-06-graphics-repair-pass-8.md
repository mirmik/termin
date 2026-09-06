# Восьмой пакет исправлений графического стека — 2026-09-06

Продолжение [седьмого пакета](2026-09-06-graphics-repair-pass-7.md), umbrella #2230.
Закрыты OpenGL packed uploads #2215, MSAA resolve #2216 и borrowed ownership
#2217. Дополнительно реализована #2262 (shared GLAD), оставлена On Test для
Windows DLL/SDK smoke.

## Packed texture uploads

Full upload делегирует общему region path. До native вызова проверяются handle,
mip (также до bit shift), single-sample 2D target, ненулевая область, границы
через subtraction checks, переполнение byte count и точный размер span.
Неверный ввод логируется и не меняет texture или GL state.

Scoped unpack state временно отключает caller PBO, задаёт alignment=1, нулевые
row length/image height/skips и отключает desktop byte swap/LSB-first.
После upload восстанавливаются pixel-store fields, PBO и прежняя texture
binding; active texture unit не меняется. Существующая top-left семантика
сохраняется через переворот строк и перевод координаты region Y.

## MSAA resolve

На время всей серии per-attachment resolve в end_render_pass scissor отключён.
После resolve восстанавливается прежний enable; box не меняется. Поэтому tiny
или offscreen scissor последнего draw больше не оставляет старые pixels в
resolve targets. Существующий независимый выбор read/draw attachment для MRT
сохранён.

## Ownership

Явный destroy и destructor используют общие ownership-aware release helpers:
external buffer/texture wrapper не удаляет native объект. Transient vertex и
dynamic UBO rings принадлежат buffer pool; отдельные поля GL names являются
ссылками, повторное удаление через них убрано. Explicit destroy owning ring
сбрасывает связанные handles/offset/initialized fields, позволяя создать ring
заново.

## Проверки

Перед sanitizer-проверкой выявлена и исправлена #2262: static GLAD попадал
одновременно в libtermin_graphics и libtermin_graphics2. ASan останавливал
process до main на ODR violation глобальных function pointers. Native GLAD
теперь имеет одного shared владельца `libtermin_glad`, export/import defines
и обычную SDK install entry; Emscripten сохраняет static target.
`tgfx::glad` CMake interface сохранён. Symbol inspection подтвердил:
`glad_glWaitSync` определяется только в новом loader, а не в двух graphics DSOs.
Windows DLL runtime smoke остаётся отдельной проверкой #2262.

Три новых оконных native теста выполняют Modern и Constrained33 policy на
desktop OpenGL context:

- `tgfx2_opengl_upload`: odd-width R8/RG8/RGB8/R16F, полная и региональная
  загрузка, точные native bytes, poisoned unpack fields/PBO, сохранение
  texture binding; short payload, invalid/extreme mip и rect, MSAA rejection
  с проверкой неизменившихся pixels.
- `tgfx2_opengl_resolve`: два MRT с разными цветами, disabled/tiny/offscreen
  scissor, все pixels asymmetric 7×5 targets, сохранение viewport/scissor и
  indexed color masks.
- `tgfx2_opengl_ownership`: native glIsBuffer/glIsTexture до/после wrapper
  destroy и device shutdown, borrowed objects сохраняются, owned удаляются;
  transient/UBO ring destroy/recreate lifecycle.

Оконный `task test:cpp -- --window-tests`: **260 passed, 1 failed из 261**.
Все новые regression Passed; единственный failure — прежняя #2253,
`termin_window_opengl33_tier` на NVIDIA. Vulkan validation errors отсутствуют,
две inventory entries вне профиля. Полный `task build` и focused
`task lint:cpp` прошли.

Для запуска профиля без Vulkan дополнена capability metadata двух новых Vulkan
тестов из pass7: отсутствие backend больше не воспринимается как незарегистрированный
test source. Все три новых GL теста зарегистрированы как window/OpenGL gates.

Первый ASan/UBSan OpenGL window profile с исправленным loader выполнил новые
pixel/state/ownership assertions, но LeakSanitizer завершил соответствующие
processes с ошибкой: allocations в NVIDIA GL/DBus и SDL title path.
Это не обозначается как sanitizer Passed. Investigation #2263 отделяет
внешние driver allocations от SDK teardown; SDL title leak уже отслеживается
в #2255. Ещё два contract fixtures выбирают OpenGL без context при выключенном
Vulkan — отдельная #2264. NVIDIA sanitizer итог: **198 passed, 17 failed,
7 runtime skips из 222**, ещё 12 inventory entries вне профиля.

С явно выбранным Mesa все три новые regression проходят ASan/UBSan/LSan
полностью. Также проходят существующие GL clear/bindings/navmesh tests и
opengl33_tier; это дополнительное evidence для #2253. Один
`termin_window_manager_live` даже в этом запуске сообщает NVIDIA adapter и
exit leaks; разница context loader выбора входит в #2263. Поэтому весь suite
нельзя считать однородным Mesa gate. Полный итог: **209 passed, 6 failed,
7 runtime skips из 222**, ещё 12 inventory entries вне профиля.
Failures: window_manager_live (#2263), два context fixtures (#2264),
frame_timeline leak (#2238), display_input_router leak (#2240), FEM UAF (#2241).
ODR violations и новые ошибки памяти в целевых GL regressions отсутствуют.
Renderer pixel smoke из #2238 входит в пропуски данного профиля без Vulkan.

GLVND выбирал NVIDIA RTX5090/595.84 даже с `LIBGL_ALWAYS_SOFTWARE=1`, что
подтверждено GL adapter logs и glxinfo. Для Mesa llvmpipe требуется также
`__GLX_VENDOR_LIBRARY_NAME=mesa`. Профиль использует X11,
`--no-vulkan --window-tests`, ASan/UBSan/LeakSanitizer без suppressions и
явный UI font. Он не подменяет Vulkan sanitizer gate предыдущего пакета.
Windows, WebGL2 и Quest runtime этим прогоном не проверены.

Логи: `/tmp/termin-graphics-pass8-window-final.log`,
`/tmp/termin-graphics-pass8-asan-final.log`, `/tmp/termin-graphics-pass8-sdk-final.log`,
`/tmp/termin-graphics-pass8-asan-mesa.log`, `/tmp/termin-graphics-pass8-lint.log`.
