# Третий пакет исправлений графического стека — 2026-09-06

Продолжение [второго пакета](2026-09-06-graphics-repair-pass-2.md) и umbrella #2230.
Исправлена #2202: Vulkan host visibility и публикация readback-результатов.

## Изменения

Общий readback-путь вынесен в `vulkan_readback.cpp`; повторявшиеся allocation,
record/submit/wait и CPU-copy блоки удалены из `vulkan_transfer.cpp`.

- Staging buffers после GPU copy получают TRANSFER_WRITE → HOST_READ barrier.
  Прямое чтение host-visible buffers тоже ждёт GPU completion и имеет dependency
  от возможных GPU accesses; device-local readback проверяет CopySrc и диапазон.
- CPU-copy выполняется только после успешного completion, map и invalidate.
  Invalidation выполняется **при действующем mapping**, до memcpy; unmap
  сбалансирован и при ошибке. VMA округляет диапазон по nonCoherentAtomSize и
  пропускает ненужный cache maintenance для coherent memory. Это соответствует
  [документации VMA](https://gpuopen-librariesandsdks.github.io/VulkanMemoryAllocator/html/memory_mapping.html).
- End/submit/wait errors на синхронном пути не публикуют данные. Если submit
  прошёл, а wait завершился ошибкой, staging/command buffer передаются отложенной
  очистке, поскольку completion ещё не доказан.
- Async results появляются только после проверенного frame fence или успешного
  `wait_idle()`. Последний завершает только уже submitted requests; текущая
  несданная prelude не считается исполненной. Teardown не читает результаты.
- Frame submit и fence wait/reset проверяются с логом/исключением. Неудачный
  submit не помечает fence in-flight и не переносит readback в completed slot.
  Immediate command allocation/begin/end также проверяются.
- Pixel format/usage/sample/bounds проверяются до native copy. RGBA8 pixel API
  принимает RGBA8_UNorm/RGBA8_sRGB, depth API — D32F. Full color readback сохраняет
  существующие преобразования форматов в float; арифметика размеров проверяется.
  Ошибки completion/map/invalidate оставляют пользовательский output неизменным.

Синхронное чтение требует ранее submitted producer. Оно не выполняет несданные
draw/prelude команды; общий ordering-контракт остаётся в #2230. Прямые CPU writes
в mapped allocations относительно in-flight GPU readers остаются в #2246.

## Проверки

- `BUILD_JOBS=8 task test:cpp`: **239 passed, 0 failed**; 4 inventory entries
  пропущены вне выбранного обязательного профиля. Vulkan/sync validation включены.
- `tgfx2_vulkan_readback_memory_test`: instrumented non-coherent allocator держит
  старые host bytes до invalidate; проверяет offset/range и порядок map/invalidate/
  copy/unmap. Failed completion, failed map, null mapping и failed invalidate
  сохраняют output и не оставляют несбалансированный mapping. Это модель памяти,
  а не заявление о доступности физического non-coherent heap на тестовой машине.
- `tgfx2_vulkan_readback_test`: device-local и host-visible buffer после GPU copy,
  нечётные byte offsets, сохранение output при неверном диапазоне, color/depth
  pixel/full sync readback, async до/после submit и wait_idle, одноразовый poll,
  attachment writes и completion через повторное использование frame slot.
- Оба новых теста прошли в ASan/UBSan на llvmpipe с Khronos/sync validation и
  LeakSanitizer; подавления ошибок не добавлялись.
  Полный прогон: **232 passed, 5 failed из 237**, без skips. Остались два Widget
  leak tests (#2238), Release assert policy (#2240), FEM UAF (#2241) и
  unsupported MSAA=2 (#2208), как во втором пакете.
- `BUILD_JOBS=8 task build`: полный SDK собран и проверен, включая native Python
  import graph. Изменений Python API нет.
- `task lint:cpp -- --python-bindings --jobs 4` для трёх изменённых production
  translation units прошёл. Сохранено прежнее необязательное предупреждение о
  размере `get_or_create_render_pass`.

Логи: `/tmp/termin-graphics-pass3-cpp-final.log`,
`/tmp/termin-graphics-pass3-asan.log`, `/tmp/termin-graphics-pass3-sdk.log`,
`/tmp/termin-graphics-pass3-lint.log`. Sanitizer-профиль использует
`VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.json`,
`VK_LOADER_LAYERS_DISABLE=~implicit~`,
`TERMIN_SHADER_ARTIFACT_ROOT=$PWD/sdk/share/termin`, `--no-opengl --no-sdl` и
параметры сборки из [первого прохода](2026-09-06-graphics-repair-pass-1.md#проверки).

## Оставшиеся работы

В #2213 отражён частичный прогресс, но карточка остаётся открытой: нужен общий
terminal device error state, оставшиеся upload/transient allocation checks и
native fault injection полного failure/cleanup контракта. Исключение после ошибки
submit само по себе не является recovery устройства.

Ранее заведённые #2238/#2240/#2241 и MSAA capability defect #2208 не входят в этот
пакет. Windows/D3D11, browser/WebGPU и Quest здесь не проверялись.
