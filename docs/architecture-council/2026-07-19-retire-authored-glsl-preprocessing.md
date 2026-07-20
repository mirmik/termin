# Retire Authored GLSL Preprocessing

Дата: 2026-07-19

Статус: Accepted

## Контекст

Termin использует Slang как единственный product-level язык authored shaders:
все штатные `.shader` явно объявляют `@language slang`, builtin shader catalog
состоит из Slang sources, а project build по умолчанию формирует Slang shader
artifacts.

При этом в runtime сохранился старый GLSL authoring path:

- `termin-materials` владеет process-global `GlslPreprocessor` и include bank;
- `termin-graphics` предоставляет process-global preprocess callback;
- player регистрирует callback после asset scan, а bootstrap снимает его при
  shutdown;
- `GlslAsset` неявно публикует загруженный source в global include bank;
- отсутствующий callback и ошибка callback одинаково приводят к компиляции
  исходного source без preprocessing;
- часть C/Python API и runtime manifest parser по умолчанию трактуют неуказанный
  shader language как GLSL.

В repository-owned authored `.shader` и `.glsl` нет GLSL `#include`. Оставшиеся
`.vert.glsl` и `.frag.glsl` являются готовыми platform/backend stages, а не
входом старого include pipeline.

## Решение

Authored GLSL и его preprocessing pipeline удаляются. Новый ownership или
replacement для `GlslPreprocessor` не вводится.

Product-level shader contract:

- authored `.shader` использует Slang;
- отсутствие явного либо canonical language не должно молча означать GLSL;
- build и runtime package не предлагают GLSL как product-level default;
- generated GLSL, полученный из Slang для OpenGL, остаётся backend artifact и
  не становится authored GLSL resource;
- low-level graphics tests и tooling могут явно подавать raw GLSL backend-у,
  но этот путь не поддерживает Termin include semantics и не использует
  process-global state.

Из production/runtime удаляются:

- `GlslPreprocessor`, global include bank и Python bindings к ним;
- TGFX shader preprocess callback и backend helper;
- `GlslAsset`, `.glsl` asset plugin и registry wiring;
- player/bootstrap configure/register/unregister lifecycle;
- GLSL defaults в authored shader API, build profiles и runtime manifests.

Удаление должно быть fail-closed: старый authored GLSL input или manifest без
обязательного language диагностируется как unsupported/invalid, а не
перенаправляется в Slang и не компилируется через скрытый compatibility path.

## Обоснование

Сохранение preprocessor только ради совместимости создаёт вторую shader-source
архитектуру рядом со Slang, возвращает import-order dependence и поддерживает
process-global lifecycle без живого product consumer. Удаление уменьшает
runtime surface и делает границу source/artifact явной: Slang принадлежит
authoring/build domain, сгенерированный GLSL — backend artifact domain.

## Рассмотренные альтернативы

### Owner-checked global callback

Отвергнуто. Token и отдельный error result исправили бы teardown и fail-open,
но сохранили бы process-global include state и несуществующий authored GLSL
product contract.

### Preprocessor, принадлежащий GraphicsHost

Отвергнуто. Runtime isolation стала бы лучше, но graphics layer всё равно
владел бы Termin-specific source semantics, не нужными Slang pipeline.

### Поддерживать оба authored языка

Отвергнуто. В репозитории нет живого authored GLSL corpus, который оправдывал
бы отдельные import, hot-reload, packaging и diagnostics contracts.

## Последствия и риски

- внешние проекты со старыми GLSL `.shader` должны быть мигрированы на Slang;
- manifests без явного language перестанут загружаться;
- raw GLSL smoke/tests должны явно обозначать low-level backend scope;
- удаление default GLSL выявит call sites, которые случайно полагались на
  legacy overloads.

Такой call site был найден и исправлен в #640: variants `LineRenderer` теперь
сохраняют language, entry points и artifact policy исходного shader вместе с
явным lifetime contract.

## Реализованный contract enforcement

В #674 удалены C overloads `tc_shader_from_sources`,
`tc_shader_register_static` и `tc_shader_register_static_uuid`, которые
неявно выбирали GLSL. Их descriptor/ex replacements требуют language явно.
Новый `TcShaderCreateInfo` начинается с `TC_SHADER_LANGUAGE_UNSPECIFIED`, а
registry отклоняет source registration до выбора поддерживаемого языка.

Python factories требуют явный language и диагностируют его отсутствие.
`termin_shaderc compile` требует `--language`. Runtime package loader требует
непустой поддерживаемый `language`, а project build models и builtin catalog
больше не подставляют GLSL при отсутствии поля.

В #675 удалены `GlslPreprocessor`, TGFX process-global callback и backend
preprocess hook. OpenGL и Vulkan передают явно полученный raw GLSL прямо в
свои compiler paths; OpenGL-specific sampling overlay остаётся локальной
backend-трансформацией. Удалены `.glsl` asset type, registry/preloader wiring и
player/bootstrap lifecycle.

## Последующая работа

- #647 и children #648–#652 — продолжить canonical `TcShaderProgram` migration
  с единственным authored Slang contract.

## Ссылки

- Kanboard: #635, #640, #647, #648–#652, #674, #675;
- `termin-components/termin-components-render/src/line_renderer.cpp`.
