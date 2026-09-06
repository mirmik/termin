# Девятый пакет исправлений графического стека — 2026-09-06

Продолжение [восьмого пакета](2026-09-06-graphics-repair-pass-8.md), umbrella #2230.
Закрыты #2219 (depth readback state), #2220 (buffer transfer state) и
#2264 (backend-independent contract fixtures).

## Depth readback

Синхронные full/single depth reads раньше привязывали временный FBO только к
READ target, но `gl_web_compat::set_draw_buffer(GL_NONE)` менял draw buffers
чужого DRAW FBO. Общий `DepthReadFramebuffer` guard теперь привязывает временный
FBO к обоим targets для его настройки, а затем восстанавливает независимые
READ/DRAW bindings и удаляет временный FBO. Это работает и при исключении во
время CPU row flip. Состояние caller MRT не меняется.

Async readback уже сохранял оба framebuffer bindings; его реализация не
менялась, но он включён в regression для проверки общего контракта.

## Buffer transfers

Создание storage и upload используют `GL_COPY_WRITE_BUFFER`, readback —
`GL_COPY_READ_BUFFER`; scoped binding восстанавливает прежние copy targets.
Тип использования буфера больше не выбирает binding point для transfer:
операция над Index buffer не меняет EBO текущего VAO, Vertex/Uniform операции
также сохраняют соответствующие caller bindings. Путь работает в GL3.3 без DSA.

Создание проверяет native size limit. Upload/readback проверяют handle,
offset/size относительно buffer descriptor и native range без переполнений;
empty span — no-op. Ошибки параметров и map/unmap логируются.

## Contract fixtures

`render_execution` и `shadow_resource_contract` явно внедряют isolated
recording device. Существующий recorder вынесен в shared test-only header
`tests/support/render_execution_recording_device.hpp`; production код не
менялся. Эти suites проверяют orchestration/resources, а native pixel correctness
проверяется отдельными backend tests.

Прежние assertions сохранены. Добавлены проверки единственного физического
raster scope для fusion, resolve 4×→1× и отсутствия GPU allocation/scopes в
пустой shadow scene. Теперь выключение Vulkan не приводит к случайному
созданию OpenGL device без context; оба target исполняют intended assertions
в обоих профилях.

## Проверки

- `tgfx2_opengl_depth_state`: full/single/async depth values, разные READ/DRAW
  FBO, переставленные два MRT draw buffers; последующий реальный draw без
  восстановления draw FBO и проверка всех pixels обоих attachments.
- `tgfx2_opengl_buffer_state`: VAO/EBO, Array/Uniform/Copy bindings,
  создание/запись/чтение Index/Vertex/Uniform buffers, partial offsets и
  сохранение untouched bytes, invalid/empty ranges; indexed triangle без
  повторного VAO/EBO binding с pixel assertion.
- Оба GL теста выполняют Modern и Constrained33 feature policies.
- Два contract fixtures проходят с Vulkan и в no-Vulkan sanitizer profile.

`task test:cpp -- --window-tests`: **262 passed, 1 failed из 263**.
Оставшийся failure — прежний #2253, `termin_window_opengl33_tier` на NVIDIA.
Vulkan validation errors отсутствуют; две inventory entries вне профиля.
Focused `task lint:cpp` прошёл.

Оба новых GL regression и оба исправленных contract fixtures прошли
ASan/UBSan/LeakSanitizer без suppressions. Полный `task build` прошёл вместе
с SDK Python/native import checks. Полный sanitizer итог:
**213 passed, 4 failed, 7 runtime skips из 224**, ещё 12 inventory entries
вне профиля. Остались window_manager_live (#2263), frame_timeline leak (#2238),
display_input_router leak (#2240) и FEM UAF (#2241). Два context fixture failures
из pass8 устранены. Renderer pixel smoke из #2238 пропущен в профиле без Vulkan.
ODR violations и новые ошибки памяти в целевых GL tests отсутствуют.

Sanitizer профиль: `--no-vulkan --window-tests`,
`__GLX_VENDOR_LIBRARY_NAME=mesa LIBGL_ALWAYS_SOFTWARE=1 SDL_VIDEODRIVER=x11`,
явный UI font и shader artifact root `sdk/share/termin`. Новые GL tests работают
на Mesa llvmpipe. Известный `window_manager_live` всё ещё выбирает NVIDIA и
ловит exit leaks (#2263), поэтому весь профиль не называется однородным Mesa
gate. Windows/WebGL2/Quest не запускались.

Логи: `/tmp/termin-graphics-pass9-window.log`,
`/tmp/termin-graphics-pass9-asan.log`, `/tmp/termin-graphics-pass9-sdk.log`,
`/tmp/termin-graphics-pass9-lint.log`.
