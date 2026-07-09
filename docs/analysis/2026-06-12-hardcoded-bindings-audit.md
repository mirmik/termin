# Аудит: захардкоженные binding-слоты и обходные хаки bind-by-name

**Дата:** 2026-06-12  
**Статус:** superseded, обновлено после удаления старых fallback-слоёв.

Первичный аудит фиксировал старую dual-path схему: bind-by-name для новых
шейдеров и индексные fallback-и для GLSL/material paths. Этот compatibility
layer удалён из runtime:

- отдельный header с legacy binding policy больше не существует;
- material pipeline больше не принимает структуру fallback bindings;
- frame/material/pass/draw resources биндятся через `tc_shader_resource_binding`
  и `RenderContext2` symbolic API;
- отсутствующий reflected resource теперь логируется как ошибка, а не
  подменяется историческим числовым слотом;
- parser больше не генерирует старые GLSL-блоки совместимости и не зеркалит их в
  C-side resource metadata; `.shader` материалы должны идти через Slang и
  generated layout sidecar.

Оставшиеся риски находятся не в runtime fallback-е, а в самих authored shader
interfaces: любой built-in/pass shader, который объявляет явные backend
bindings, должен быть либо портирован на Slang/resource sidecar, либо иметь
явно синхронизированную parser/asset metadata схему.
