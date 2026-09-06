# Второй пакет исправлений графического стека — 2026-09-06

Продолжение [первого пакета](2026-09-06-graphics-repair-pass-1.md) и umbrella #2230.
Исправлены #2200 и #2201.

## Изменения

- **#2200:** общие buffer barriers для `upload_buffer` и command-list
  `copy_buffer`. Зависимости ограничены диапазоном байтов и учитывают usage:
  vertex/index/uniform/storage и transfer. До записи учитываются прежние GPU
  readers/writers, после записи обеспечивается видимость следующим consumers.
  `copy_buffer` отклоняет неверные handles/ranges, перекрывающееся self-copy и
  запись внутри render pass с сообщением в логе.
- **#2201:** переход в `TRANSFER_SRC_OPTIMAL` задаёт `TRANSFER_READ` access;
  shader-read dependency охватывает все поддерживаемые queue shader stages,
  включая vertex. `GENERAL` имеет memory read/write dependency. Copy/blit
  переводят в shader-read только sampled images; остальные сохраняют допустимое
  прежнее состояние или получают layout согласно usage после первой записи.
- Новый тест выявил дополнительный дефект: создание image view для transfer-only
  image запрещено Vulkan. Для таких owned/external textures view больше не
  создаётся; native image по-прежнему доступен операциям копирования.

В steady state не добавлены queue/device idle и CPU waits. Семантика Vulkan
dependencies сверена со [спецификацией Khronos](https://docs.vulkan.org/spec/latest/chapters/synchronization.html):
порядок command buffers сам по себе не устанавливает memory dependency.

## Проверки

- `BUILD_JOBS=8 task test:cpp`: **237 passed, 0 failed**, ещё 4 inventory entries
  пропущены вне выбранного обязательного профиля. Vulkan validation и sync
  validation включены; ошибки не подавлялись.
- `tgfx2_vulkan_buffer_sync_test`: шесть indexed pixel checks, три submissions
  без idle между ними, upload → draw → copy overwrite → draw. Проверены vertex,
  index, GPU-written uniform buffers и ненулевые source offsets. Тест использует
  собственный native coherent capture, чтобы отделить проверку buffer dependencies
  от ещё открытого host-readback контракта #2202.
- `tgfx2_vulkan_image_sync_test`: повторный upload → vertex texture fetch,
  render → copy non-sampled attachment → LOAD, device blit в transfer-only
  texture и девять pixel readbacks. Проверяются также restored layouts.
- Оба новых теста проходят в ASan/UBSan на llvmpipe, explicit Khronos layer,
  synchronization validation и leak detection включены.
  Итог полного прогона: **230 passed, 5 failed из 235**, без skips. Failures:
  два Widget leak tests (#2238), Release assert policy (#2240), FEM UAF (#2241)
  и unsupported MSAA=2 (#2208).
- `BUILD_JOBS=8 task build`: полный SDK пересобран и проверен.
- `task lint:cpp -- --python-bindings --jobs 4` для трёх изменённых production
  Vulkan translation units прошёл. Сохранено прежнее необязательное предупреждение
  о размере `get_or_create_render_pass`.

Логи: `/tmp/termin-graphics-pass2-cpp-final.log`,
`/tmp/termin-graphics-pass2-asan-final.log`, `/tmp/termin-graphics-pass2-sdk.log`,
`/tmp/termin-graphics-pass2-lint.log`. Параметры sanitizer-профиля совпадают с
[первым проходом](2026-09-06-graphics-repair-pass-1.md#проверки).
В команде первого отчёта исправлен `TERMIN_SHADER_ARTIFACT_ROOT`: требуется
`sdk/share/termin` (родитель каталога `shaders`). Первоначальный sanitizer-запуск
второго пакета имел три ошибки окружения из-за неверного корня;
финальный запуск использует исправленный путь.

## Оставшиеся работы

- **#2202:** host-readback barriers/completion/invalidation ещё не исправлены.
  Зелёные pixel checks на доступной памяти не доказывают non-coherent correctness.
- **#2246:** новая investigation — lifetime mapped uploads относительно
  in-flight GPU readers. GPU barriers не защищают CPU memcpy в используемый GPU
  allocation; frame ring и обычные UBO требуют отдельной проверки consumers.
- **#2230, ordering:** `execute_immediate` остаётся next-submit prelude,
  независимо от host-порядка записи draw. Комментарии и документация исправлены;
  общий ordered-stream/lifetime контракт ещё не изменён.
- **#2208:** llvmpipe воспроизводит unsupported MSAA=2 в
  `tcplot_retained_chart3d_test` (поддержаны 1 и 4 для RGBA8/D32F). Подробности
  добавлены в существующую capability-card.
- Полный sanitizer-профиль также продолжает выявлять ранее заведённые
  #2238/#2240/#2241; успешный обычный CTest их не закрывает.

Windows/D3D11, browser/WebGPU и Quest в этом пакете не проверялись.
