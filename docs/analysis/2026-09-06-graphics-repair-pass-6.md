# Шестой пакет исправлений графического стека — 2026-09-06

Продолжение [пятого пакета](2026-09-06-graphics-repair-pass-5.md), umbrella #2230.
Исправлены #2209 (UBO offset/cache) и #2210 (pipeline color mask).

## UBO base offset и dynamic offset

Для пользовательского UBO `BoundResourceValue.offset` теперь записывается в
`VkDescriptorBufferInfo.offset` и входит в descriptor cache identity. Bind-time
dynamic offset прибавляется к этой базе; повторный cache hit сохраняет тот же
диапазон. Например, base=N и dynamic=N читают диапазон 2N. Это соответствует
[контракту Vulkan descriptor buffer info](https://docs.vulkan.org/refpages/latest/refpages/source/VkDescriptorBufferInfo.html).

Внутренний ring UBO сохраняет прежнюю схему: descriptor base=0, slice offset
передаётся динамически; такие resource sets не используют descriptor cache.
Не понадобились дополнительные cached wrappers или изменение ownership.

Также исправлен связанный случай `range=0`: берётся остаток буфера **после base
offset**, ограниченный реальным `maxUniformBufferRange`. Лимит запоминается при
инициализации устройства, вместо прежней константы 65536. Нулевой implicit range
нормализуется до конкретного значения до cache lookup; эквивалентные explicit и
implicit ranges используют одну cache entry.

До descriptor allocation проверяются Uniform usage, handle, выравнивание base
offset, границы buffer и range limit. Неверный запрос логируется и возвращает
пустой handle. Explicit oversized range больше не обрезается молча. Проверка
произвольных caller-provided bind-time dynamic offsets остаётся частью общего
descriptor validation направления #2230; этот пакет проверяет корректное
сложение базы и допустимого dynamic offset.

## Color mask

Каждый `VkPipelineColorBlendAttachmentState` получает R/G/B/A bits из
`PipelineDesc.color_mask`, включая MRT. Ранее Vulkan всегда включал все каналы.
OpenGL уже использует `glColorMask`, D3D11 — `RenderTargetWriteMask`; смысл
полей не меняется. Код этих backends не изменялся; их native parity здесь
отдельно не прогонялась.

## Проверки

Новый `tgfx2_vulkan_pipeline_contracts_test` рисует fullscreen triangle в два
color attachments, затем читает каждый канал обоих targets:

- три выровненных диапазона одного UBO с разными RGBA значениями;
- base=0, base=N, повторный base=0 через cache hit, base=N + dynamic=N;
- implicit `range=0` в последнем диапазоне и его эквивалентность explicit range;
- отказ out-of-bounds/misaligned descriptors до native calls;
- RGBA, R-only, RGB без alpha, alpha-only, пустая mask и GB-only;
- сохранение исходного clear value всех отключённых каналов обоих MRT outputs.

`BUILD_JOBS=8 task test:cpp`: **242 passed, 0 failed**, 4 inventory entries вне
профиля. Vulkan core/sync validation включены; новые pixel checks прошли.
В обычном прогоне также проходят существующие ring/dynamic binding regressions.
Полный `task build` собрал SDK и проверил bundled Python/native import graph.
Focused clang-tidy для двух изменённых Vulkan translation units прошёл;
осталось прежнее необязательное предупреждение о размере `get_or_create_render_pass`.
Новый regression прошёл также под ASan/UBSan на llvmpipe. Полный sanitizer
прогон: **236 passed, 4 failed из 240**, без skips и Vulkan validation errors.
Остались прежние #2238 (два Widget leaks), #2240 (Release assert policy) и
#2241 (FEM UAF); это offscreen профиль, оконные #2253/#2255 здесь не проверялись.

Логи: `/tmp/termin-graphics-pass6-cpp-final.log`,
`/tmp/termin-graphics-pass6-asan-final.log`, `/tmp/termin-graphics-pass6-sdk-final.log`,
`/tmp/termin-graphics-pass6-lint-final.log`.
Sanitizer profile: llvmpipe, `VK_LOADER_LAYERS_DISABLE=~implicit~`,
`TERMIN_SHADER_ARTIFACT_ROOT=$PWD/sdk/share/termin`, `--no-opengl --no-sdl`,
ASan/UBSan/LeakSanitizer без suppressions.

Window/platform gates из пятого пакета этим offscreen прогоном не подменяются.
#2207 остаётся On Test, прочие lifetime/retirement работы — отдельными карточками.
