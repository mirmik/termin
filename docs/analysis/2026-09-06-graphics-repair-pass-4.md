# Четвёртый пакет исправлений графического стека — 2026-09-06

Продолжение [третьего пакета](2026-09-06-graphics-repair-pass-3.md) и umbrella #2230.
Исправлены #2204 (Vulkan/SPIR-V baseline) и #2208 (Vulkan capabilities).
Первая часть уже зафиксирована пользователем в `de9213183`.

## Vulkan API и shaders

- Effective API ограничен запрошенной версией, loader, physical device и
  поддерживаемым engine baseline 1.3. Vulkan 1.0 loader без
  `vkEnumerateInstanceVersion` обрабатывается как 1.0.
- Runtime GLSL compiler выбирает core target: Vulkan 1.0 → SPIR-V 1.0,
  1.1 → 1.3, 1.2 → 1.5, 1.3 → 1.6. Target включён в ключ shader cache;
  cache format version обновлена.
- Готовые модули и данные из compiler/cache проверяются перед reflection и
  `vkCreateShaderModule`. Версия выше core baseline отклоняется с логом,
  содержащим shader context. Не предполагается неявное расширение baseline
  опциональными SPIR-V extensions.
- `api_version()` возвращает effective device API; VMA на desktop получает
  ту же версию. Существующий Android VMA dispatch workaround оставлен.

## Capabilities и descriptors

- Compute и storage textures больше не объявляются поддержанными. Dispatch
  логирует ошибку и выбрасывает исключение до `vkCmdDispatch`; storage texture
  allocation и graphics pipeline со storage-image descriptor отклоняются.
  Создание отдельного compute shader module остаётся допустимым для проверки
  artifacts; публичного compute pipeline API пока нет.
- Geometry, anisotropy и depth-bias clamp включаются только при поддержке
  physical device. Capabilities отражают enabled features. Sampler anisotropy
  проверяется на конечность, диапазон и включённую feature. Неподдерживаемые
  geometry/non-solid/depth-bias-clamp pipeline requests отклоняются до native calls.
  Geometry вместе с multiview пока явно отклоняется: дополнительная
  `multiviewGeometryShader` feature не включена.
- Pipeline reflection включает geometry stage, в том числе его отдельные UBO.
- `VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE` теперь заполняется, как и separate sampler.
  Нулевые texture/sampler handles используют существующие белую texture и
  default sampler; ненулевые неверные handles и texture без Sampled usage
  отклоняются с логом. Проверены явный и default sampling pixel paths.
- Texture limits берутся из sampled-image/sampler descriptor limits,
  отдельно для descriptor set и fragment stage, вместо числа descriptor sets.
- `VulkanRenderDevice::supports_texture(TextureDesc)` проверяет точный
  format/usage/sample contract через `vkGetPhysicalDeviceImageFormatProperties`,
  а также extent/layers/mips. `create_texture` использует этот запрос до allocation.
  Native tcplot test выбирает действительно поддержанный color+depth sample count:
  наличие 4 samples не подразумевает поддержку 2.

Общий query API для других backends и выбор допустимых значений в production
consumers выделены в #2250. Сейчас неподдержанный explicit request в Vulkan
даёт явную ошибку; переносимой автоматической настройки MSAA ещё нет.

## Проверки

- `BUILD_JOBS=8 task test:cpp`: **241 passed, 0 failed**, 4 inventory entries
  вне выбранного профиля. Vulkan core/sync validation включены.
- `tgfx2_vulkan_shader_target_test`: desktop → API1.0 → API1.1 → desktop,
  реальные draw/readback pixels, cache separation и precompiled version rejection.
- `tgfx2_vulkan_capabilities_test`: реальные geometry UBO и separate image/sampler
  draw/readback, явные/default bindings, anisotropy и depth-bias feature use,
  limits, отказ compute dispatch и storage textures/pipelines.
- `tcplot_retained_chart3d_test`: запрос/создание/отказ для RGBA8 и D32F при
  sample counts 1…128, затем render/resolve с поддерживаемым MSAA.
- Новые shader-target/capabilities tests и tcplot прошли также под ASan/UBSan
  на llvmpipe с Khronos/sync validation и LeakSanitizer, без подавлений.
  Полный прогон: **235 passed, 4 failed из 239**, без skips. Остались прежние
  два Widget leak tests (#2238), display input router leak из Release assert
  policy (#2240) и FEM UAF в `clear_runtime_links` (#2241).
  Ошибка неподдерживаемого MSAA=2 из предыдущих прогонов устранена;
  Vulkan validation errors в этом прогоне отсутствуют.
- Focused `task lint:cpp -- --python-bindings --jobs 4` прошёл для четырёх
  изменённых Vulkan translation units; осталось прежнее необязательное
  предупреждение о размере `get_or_create_render_pass`.
- `BUILD_JOBS=8 task build`: полный SDK собран, native Python import graph
  и bundled runtime проверены. Python API не менялся.

Логи: `/tmp/termin-graphics-pass4-cpp-final.log`,
`/tmp/termin-graphics-pass4-asan.log`, `/tmp/termin-graphics-pass4-sdk-final.log`,
`/tmp/termin-graphics-pass4-lint-final.log`.
Sanitizer environment и параметры соответствуют третьему пакету.

## Платформенные границы

Android/Quest здесь не запускались. В #1317 остаётся named smoke: собрать
Android SDK и Quest showcase APK; на Quest 2 с Vulkan validation проверить
runtime compilation и packaged shaders, оба глаза, движение/grab и повторные
перезапуски. Проверить отсутствие `pCode-08737`, descriptor и sync errors.
Desktop API1.0 test проверяет compatibility baseline, но не подменяет устройство.
Windows/D3D11 и browser/WebGPU в этом пакете не проверялись.
