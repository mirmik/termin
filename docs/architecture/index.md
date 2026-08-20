# Architecture Notes

Этот раздел хранит cross-module архитектурные заметки и правила, которые не принадлежат одному конкретному модулю.

Для module-local архитектуры используйте `<module>/docs/`. Для исторических планов и чеклистов используйте [plans](../plans/index.md).

## Current Notes

- [WorldController and EngineCore RuntimeSession](2026-08-20-game-application.md) - проектный world-level controller, минимальная per-run session, transient scene context и синхронная смена primary scene в safe point движка.
- [District monorepo](2026-08-14-district-monorepo.md) - принятая схема единого репозитория с корневыми `core`, `graphics`, `physics`, `engine`, `editor` и `platform`, общим build orchestration и независимыми SDK-профилями.
- [Shared 2D composition](2026-08-11-shared-2d-composition.md) - отдельные Widget и GraphicItem semantic trees поверх общего affine/clip/bounds evaluation и канонического `DrawList2D`, с невладеющими handle-based projections между ними.
- [Articulation3D as a chain of moving frames](2026-08-04-articulation3d-moving-frame-chain.md) - `Articulation3D` как unit-only дерево подвижных выходных фреймов без runtime-разделения на joint/link, включая инерцию, контакты и границу scene authoring.
- [Canonical naming](2026-03-15-canonical-naming.md) - канонические Python namespace'ы и правила импортов.
- [Architecture TODO](2026-03-16-architecture-todo.md) - открытые архитектурные вопросы.
- [Scene rendering lifecycle](2026-05-07-scene-rendering-lifecycle.md) - заметки по lifecycle scene rendering.
- [Clip space policy](2026-06-26-clip-space-policy.md) - целевая политика `TerminClip -> NativeClip` и план миграции 3D render paths.
- [UI storage and plot annotations](2026-07-07-ui-storage-and-plot-annotations.md) - целевая модель владения UI-виджетами и границы plot annotations.
- [Retained visual scene 2D](2026-07-27-retained-visual-scene-2d.md) - отдельный handle-based модуль `termin-visual-scene` поверх `termin-graphics` для GUI tool scenes и plot annotation projection; не дублирует renderer и не относится к world-space 2D games.
- [Multilanguage component/pass/widget/graphic-item lifetime model](2026-07-09-multilanguage-component-lifetime-model.md) - единая C-side модель владения, vtable, языкового body и deleter для `tc_component`, `tc_pass`, `tc_widget` и `tc_graphic_item`.
- [Native prefab runtime](2026-07-15-native-prefab-runtime.md) - Python-free prefab runtime, stable source identity, native instance reconciliation and editor/tooling boundaries.
- [Player host and embeddable runtime boundary](2026-07-15-player-and-runtime-boundary.md) - `termin-player` as an editor-adjacent CLI/Play Mode host versus `termin-runtime` as an editor-free embeddable native library.
- [Build profiles and product composition](2026-07-16-build-profiles-and-product-composition.md) - project-owned product recipes, typed target variants, explicit scene/module roots and the boundary between portable intent, local toolchains, resolved requests and artifact manifests.
- [Display render surface contract](2026-07-19-display-render-surface-contract.md) - целевая граница между `tc_display`, backend-neutral offscreen texture output, display-owned input routing и native window presentation.
- [Framework-neutral window management](2026-07-23-framework-neutral-window-management.md) - целевая граница `termin-window::WindowManager`, application-owned window content, optional UI adapters и независимой headless document composition.
- [No owner-thread restrictions](2026-07-24-no-owner-thread-restrictions.md) - обязательный запрет creator/owner/UI/render-thread affinity в engine API и правила замены таких ограничений внутренней синхронизацией и транзакционными границами.
- [Language-neutral deferred dispatcher](2026-07-24-language-neutral-deferred-dispatcher.md) - optional caller-driven `termin-dispatch` с каноническим C ABI, C++/Python projections и без автоматической интеграции в Termin applications.
- [Centralized frame memory](2026-07-21-centralized-frame-memory.md) - архитектурный набросок общей CPU frame arena, scoped scratch-регионов, telemetry и политики миграции hot-path allocations.
- [Graphics host and window session](2026-07-21-graphics-host-and-window-session.md) - каноническое владение application graphics domain через `GraphicsHost` и композиционный lifetime `WindowedGraphicsSession`.
- [Extensible material surface contracts](2026-07-28-extensible-material-surface-contracts.md) - versioned shader-side surface producer/consumer contracts, standard PBR v1 и граница plugin-owned G-buffer/deferred pipelines.
- [Backend-neutral MRT contract](2026-07-28-backend-neutral-mrt-contract.md) - pass-local ordered color attachments из независимых framegraph textures, pipeline identity, validation и cross-backend semantics.
- [Backend-neutral layered shadow pool](2026-08-04-layered-shadow-pool.md) - целевая общая модель array textures и subresource views в tgfx2, renderer-owned `ShadowPool`, layer allocations и отображение shadow sampling на WebGPU, Vulkan, D3D11 и OpenGL.
- [Graded world transform](2026-07-29-graded-world-transform.md) - accepted graded `Rigid -> Similarity -> AxisScaled -> Affine` world cache, exact hierarchical composition and separate logical quaternion orientation.

## Historical Notes

- [Core SDK and domain repository boundary](2026-08-13-core-domain-repositories.md) - отменённый эксперимент с независимыми domain-репозиториями; сохранён как анализ пакетных границ.
- [Native GUI application host](2026-07-23-native-gui-application-host.md) - историческая промежуточная ownership-модель, удалённая после перехода на framework-neutral window adapter.
- [Native GUI windowed and headless host](2026-07-23-native-gui-windowed-headless-host.md) - промежуточное выделение presentation/input/offscreen mechanics через общий host; механика сохраняется, ownership-модель заменена.
