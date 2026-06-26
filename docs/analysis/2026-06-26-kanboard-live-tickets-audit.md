# Аудит живых Kanboard-тикетов Termin на 2026-06-26

## Область

Проверена активная доска `termin` (`project_id=1`) через `scripts/kanboard-api`:

- всего активных тикетов: 65;
- колонки: `Backlog` - 57, `In Progress` - 3, `On Test` - 5;
- swimlanes: `Common` - 60, `Android/OpenXR` - 3, `Chronosquad` - 2.

Цель аудита: отделить реальные открытые баги от уже сделанных работ, устаревших записей, future work и зонтичных карточек. Доска при этом не изменялась.

## Легенда

- **Баг** - воспроизводимый или правдоподобный дефект, регрессия, crash, leak, silent failure.
- **Сделано** - код/тесты в репозитории или комментарии карточки подтверждают, что acceptance фактически закрыт.
- **Частично** - часть карточки выполнена, но оставшийся scope ещё полезен.
- **Зонт** - карточка агрегирует несколько направлений и должна жить как roadmap/эпик, а не как конкретная задача.
- **План** - архитектурная миграция или policy work без явного текущего бага.
- **Ручная проверка** - нужно устройство, Windows, интерактивный UI или проект вне этого checkout.
- **Сомнительно** - карточка выглядит неактуальной, внешней к engine или требует повторного baseline.

## Короткий вывод

Доска сейчас смешивает backlog, журнал уже выполненных миграций и несколько настоящих production blockers. Главный шум создают карточки, где в комментариях уже написано "сделано, проверки прошли", но Kanboard всё ещё держит их активными.

Кандидаты на закрытие или перевод в `Done` после минимальной контрольной проверки:

- #28, #29, #41, #53, #80, #120, #122 - acceptance выглядит закрытым.
- #113 - закрывать после PowerShell sanity на Windows, Linux-путь уже исправлен.
- #114 - основной `entity_lib` scope закрыт; отдельно оставить/создать маленькую cleanup-задачу на мёртвый `termin-app/core_c/src/tc_scene_registry.c`.
- #115 - центральный `DEFAULT_DOMAIN_COMPONENT_SPECS` уже разобран; оставшаяся standard/optional policy покрывается #116.

Крупные зонты, которые лучше оставить, но переписать с текущим состоянием:

- #7 Android/OpenXR regression pass.
- #12 editor/MCP ergonomics.
- #27 desktop standalone/runtime package umbrella.
- #36 следующий вынос из `termin-app`.
- #40 asset runtime extraction.
- #89 D3D11/backend parity.
- #95 `IRenderDevice` capability split.
- #116 standard vs experimental SDK packages.

Настоящие открытые дефекты/риски, которые выглядят важнее всего:

- #34 и #119 - shutdown/teardown crash у packaged/player runtime.
- #77 - fatal Python finalization на ошибке создания окна.
- #16 и #125 - resource/module reload lifecycle оставляет stale registrations/dependencies.
- #3 - OpenGL parity после shader migration, если свежий editor smoke всё ещё ловит black output/pipeline absence.
- #100/#81 - nanobind leak diagnostics; лучше консолидировать, потому что это один класс проблем с разными входами.
- #47 - возможная математическая ошибка в `solve_Adxx_Cdx_Kx_b`.
- #48 - незафиксированная политика `-ffast-math` против NaN/Inf semantics.

## Локальные проверки

Проверял не только комментарии доски, но и текущий checkout. Важные подтверждения:

- `entity_lib` в исходниках почти исчез: `rg entity_lib` вне build/sdk находит только исторический план. При этом `termin-app/core_c/src/tc_scene_registry.c` остался как неиспользуемая legacy-реализация, а `tc_scene_registry.h` уже static-inline делегирует в `tc_scene_pool`.
- `run_project_build_pipeline()` останавливает сборку до target packaging при diagnostics level `error`; `profile_build` возвращает non-zero. Это закрывает #53.
- `desktop_runtime_packager` хранит parsed `Requirement`, проверяет specifiers и обрабатывает extras; тесты покрывают version mismatch и extra deps. Это закрывает #122.
- `run-tests-python.sh` и `.ps1` больше не поддерживают `--no-venv` и не подмешивают SDK `site-packages` в `PYTHONPATH`. Это закрывает суть #113.
- `termin-default-assets` больше не хранит монолитный `DEFAULT_DOMAIN_COMPONENT_SPECS`: он собирает lightweight provider modules вроде `termin_kinematic_component_specs`, `termin_navmesh_component_specs`, `termin_render_component_specs`. Это закрывает основной #115.
- D3D11 реально присутствует в `termin-graphics`/`termin-display`, включая `D3D11Swapchain`, `BackendWindow` path, `supports_compute=false`, `read_pixel_depth_float()` и smoke tests. При этом C# `BackendType.cs` всё ещё показывает `D3D12`, что подтверждает хвост #87.

## Разбор по кластерам

### Build/runtime package

Desktop standalone bundle уже далеко не "не начат": pipeline, diagnostics, BuildContext, profile dispatch, runtime package validation, desktop host, Python runtime packaging и MCP diagnostics были реализованы в серии работ вокруг #27. Поэтому дочерние #28/#29/#30/#31/#41/#53 в текущем виде в основном исторические. Оставшиеся реальные направления:

- #32 и #39 - полный asset graph и explicit include policy для dynamic resources;
- #33 - relocatable smoke, заблокирован clean shutdown;
- #34/#119 - player shutdown crash;
- #109 - size work после minimal Python: mesh binary/compact payload и size regression;
- #111 - host-specific shader target schema/defaults.

### D3D11/render

D3D11 MVP частично стал реальным backend, а не placeholder. #18 и #89 теперь надо обновить: они не должны перечислять уже закрытые runtime-placement/window/smoke этапы как blockers. Открытые хвосты: editor/player project scene smoke, material/skinned/foliage coverage, dynamic offsets/push constants/storage/UAV policy, backend capability split, C# enum regeneration, и оставшаяся clip-space/readback regression discipline.

#93 выглядит реализованным локально, но должен дождаться Windows/CI smoke. #94/#95 - нормальные future architecture tasks. #17 остаётся спорным: в комментариях есть и "acceptance complete", и последующий возврат в backlog из-за отсутствия заявленной PipelineCache/layout статистики. Пока это не закрывать без повторной проверки stats surface.

### Modules/reload/Python

#105 реализован для Python `.pymodule` auto-reload, но оставляет C++ `.module` descriptor/source/build-trigger reload, serialization/race policy и UI diagnostics. #106 почти закрыт: e2e Python, C++ leaf и C++ cascade smokes добавлены в `run-tests.sh`; остаток - Windows equivalent. #125 - реальный свежий дефект: helper-only loose `.py` changes не каскадируют в dependent components.

#96 выглядит закрытым по SDK/runtime venv части; оставшийся импорт `Scripts.ChessUIComponent` через удалённый legacy path относится скорее к `termin-chess` или отдельной migration card, а не к project venv.

### Assets/package boundaries

#40 и #36 - зонты по дальнейшему выносу из `termin-app`. Они полезны, но требуют обновления scope, потому что большая часть re-export cleanup уже прошла.

#80 готов к закрытию: `VoxelGridHandle` уже canonical alias/native payload path, ResourceManager fallback убран по комментариям и тестам. #38 можно оставить как более широкий native/assets split, но нужно убрать из него уже выполненную часть #80.

#114 готов к закрытию как `entity_lib` umbrella. Найденный остаток `tc_scene_registry.c` лучше оформить маленькой отдельной cleanup-задачей, если не удалить сразу.

#115 готов к закрытию по central catalog; #116 должен остаться для standard/experimental SDK/profile policy.

### Android/OpenXR и Chronosquad

#7 - нормальный umbrella, #5 и #8 - его конкретные gates. Без Quest build/device runtime их нельзя закрывать.

#6 уже несколько раз smoke-checked и должен быть либо переведён в `On Test`/закрыт как разовая проверка, либо переформулирован как регулярный smoke. #11 выглядит сомнительно как engine bug: комментарий говорит, что просадка возникает, когда на GPU развёрнут qwen. Нужен baseline без qwen; если он чистый, закрыть как external/resource contention.

## Таблица по всем активным тикетам

| ID | Класс | Вывод | Рекомендация |
|---:|---|---|---|
| #1 | Баг | Foliage shadow/pattern artifact без свежих комментариев. | Оставить, нужен repro/screenshot и отделение shader/data issue. |
| #3 | Баг / частично | OpenGL shader parity частично чинили: GLSL bindings, `.artifact`, `.termin` ignore, shaderc fingerprint. Неясно, свежий editor smoke чистый или нет. | Оставить, обновить фактическим smoke-result; если black output ушёл - закрыть или сузить. |
| #5 | Ручная проверка | Quest APK build gate. | Оставить как concrete check под #7. |
| #6 | Ручная проверка / сомнительно | Chronosquad smoke уже проходил после shader fixes; оставался content log noise. | Перевести в On Test или закрыть как разовый smoke; для регулярности создать отдельный smoke-policy task. |
| #7 | Зонт | Android/OpenXR regression pass объединяет #5 и #8. | Оставить как umbrella до build + device runtime. |
| #8 | Ручная проверка | Device runtime smoke отдельно от APK build. | Оставить. |
| #11 | Сомнительно | Perf drop объяснён qwen на GPU. | Повторить baseline без qwen; если подтверждается - закрыть как external. |
| #12 | Зонт / частично | MCP/editor ergonomics улучшались; остаются transform symmetry, undo-aware editing, framegraph related work. | Оставить umbrella, перечислить актуальные children. |
| #13 | Частично | MCP path уже умеет stable pass_index; UI/dialog всё ещё name-based. | Оставить In Progress или split UI cleanup. |
| #16 | Баг | File watcher/resource unregister lifecycle всё ещё дырявый; loose Python removal подтверждает риск stale registrations. | Оставить, приоритет средний/высокий. |
| #17 | Частично / спорно | Было заявлено done, потом возвращено в backlog из-за отсутствия stats. | Оставить, сначала подтвердить/добавить PipelineCache hit/miss/create/layout diagnostics. |
| #18 | Частично | D3D11 MVP сильно продвинулся: device, shaders, swapchain, window smoke. Остались real editor/player smoke и capability gaps. | Обновить описание, убрать закрытые blockers. |
| #20 | План | Legacy GLSL compatibility bindings после Slang/reflection. | Оставить как cleanup после стабилизации shader policy. |
| #25 | План / баг-риск | Editor/game input source separation - реальный design risk для custom controllers. | Оставить, оформить API contract. |
| #26 | Сделано / частично | Runtime shader artifacts уже пишутся через project_build/exporter; остатки покрываются #32/#39. | Закрыть или слить в #32/#39 после контрольного build smoke. |
| #27 | Зонт | Desktop standalone bundle umbrella; большая часть pipeline уже сделана. | Оставить umbrella, переписать current state и children. |
| #28 | Сделано | Bundle layout/app.json/package manifest реализованы и тестировались. | Закрыть. |
| #29 | Сделано | Desktop profile backend перешёл на runtime package path в рамках pipeline work. | Закрыть. |
| #30 | Сделано / частично | Python runtime/package/scripts реализованы; size/deps остались в #109/#116/#122. | Закрыть текущую карточку или сузить до оставшихся конкретных gaps. |
| #31 | Сделано / частично | Desktop host с Python support и player MCP есть; shutdown вынесен в #34/#119. | Закрыть как implemented, blockers вести отдельно. |
| #32 | Частично | Asset graph расширен: shaders/materials/standalone meshes. Dynamic resources и long tail assets остаются. | Оставить, связать с #39. |
| #33 | Баг-блокер / QA | Relocatable smoke стартует, но direct host clean shutdown блокируется #34. | Оставить, blocked by #34. |
| #34 | Баг | Direct `termin_player` shutdown crash under signal. | Оставить высоким приоритетом. |
| #35 | План | Navmesh package/import boundary debt. | Оставить, актуально как architecture cleanup. |
| #36 | Зонт | Следующий вынос из `termin-app`; много batch cleanup уже сделано. | Оставить, но обновить scope/current leftovers. |
| #38 | Частично | Voxel handle/resource часть сделана через #80; более широкий native/assets split может оставаться. | Обновить, убрать закрытую часть #80. |
| #39 | План / баг-риск | Dynamic `from_name` resources ещё не имеют explicit include policy; broad material include только частичный dev fix. | Оставить. |
| #40 | Зонт / частично | Asset runtime extraction очень продвинулся; остаются `termin.assets.resources`/ResourceManager ownership и runtime cleanup. | Оставить umbrella, переписать. |
| #41 | Сделано | Profile target dispatch для desktop/android/quest реализован и задокументирован. | Закрыть. |
| #43 | План | Needs-work тесты после инвентаризации. | Оставить как QA debt, но лучше разбить по пакетам при взятии. |
| #47 | Баг-риск | Возможная математическая ошибка в qopt effective system. | Оставить, нужен domain review/test. |
| #48 | Баг-риск / policy | `-ffast-math` конфликтует с intentional infinity semantics. | Оставить, нужна явная numeric policy. |
| #49 | План | Animation/skeleton asset/component boundary. | Оставить. |
| #51 | План | Package/distribution/import naming policy. | Оставить, полезный recurring CI-risk. |
| #53 | Сделано | Fatal validation gate реализован в pipeline/profile CLI, тесты есть. | Закрыть. |
| #54 | Частично | Headless runtime slice реализован: loop, collision extension, request_quit. Остался audit components requiring GPU. | Оставить или split remaining guardrail task. |
| #76 | План | Политика loose Python scripts в editor. | Оставить, связать с #16/#125. |
| #77 | Баг | Fatal Python finalization после failed window init. | Оставить, относится к player init/shutdown robustness. |
| #80 | Сделано | `VoxelGridHandle` развязан от app ResourceManager и стал canonical/native path. | Закрыть. |
| #81 | Баг / дубликат-класс | Nanobind leaks на lightweight imports. | Консолидировать с #100/#119 или оставить как import-only reproduction. |
| #84 | План | Pose3/GeneralPose3 ABI migration. | Оставить. |
| #85 | План / баг-риск | Magic names in shader compilation/resource policy; warning `u_params` без scope подтверждает актуальность. | Оставить. |
| #86 | Зонт / план | Унификация `nos::trent` и `tc_value` - большая architecture migration. | Оставить umbrella, не смешивать с quick fixes. |
| #87 | Баг-риск | Platform bindings still have app-private deps; C# generated enum still says `D3D12` while C++ has `D3D11`. | Оставить, добавить конкретный C# enum subtask если нужно. |
| #89 | Зонт / частично | D3D11 parity umbrella; много clip-space/D3D11 work сделано, но backend parity не закрыта. | Оставить, обновить current remaining list. |
| #93 | Сделано / On Test | D3D11 compute/readback mismatch fixed locally; ждёт Windows/CI smoke. | Держать On Test до Windows result, затем закрыть. |
| #94 | План | FrontFace default migration to CCW authoring. | Оставить future graphics migration. |
| #95 | Зонт / план | Capability-specific `IRenderDevice` split. | Оставить architecture umbrella. |
| #96 | Сделано / ручная проверка | SDK Python executable/project venv path fixed; remaining failure is project legacy import. | Перевести On Test/закрыть после Windows check; project import вынести отдельно. |
| #99 | План | Scene render extensions owner still app/native-owned. | Оставить. |
| #100 | Баг | Windows `run-tests.ps1` passes but prints nanobind leaks. | Оставить; связать с #81/#119 teardown/leak class. |
| #105 | Частично | Python `.pymodule` auto-reload implemented; C++ module/watch/race/UI scope remains. | Оставить, обновить title/scope. |
| #106 | Сделано / ручная проверка | E2E hot reload smokes added to `run-tests.sh`; remaining Windows equivalent. | Перевести On Test или закрыть после Windows coverage decision. |
| #108 | Баг / tooling | Windows editable install fails on locked native modules with poor diagnostics. | Оставить. |
| #109 | Частично | Minimal Python packaging and FEM split done; mesh compact format/size regression remain. | Оставить, сузить на remaining size drivers. |
| #110 | On Test / ручная проверка | Code-side SDL/PySDL2 alignment present; needs interactive click/drag/keyboard. | Держать On Test до ручной Linux UI проверки. |
| #111 | Частично | Explicit `d3d11` now rejected when `fxc` missing; host-specific profile schema/default shader target policy remains. | Оставить. |
| #113 | Сделано / On Test | Linux fail-fast `.venv` policy implemented; PowerShell runtime not checked. | Закрыть после Windows/pwsh sanity or mark Linux-only verified. |
| #114 | Сделано | `entity_lib` target/artifact removed; only unrelated/dead `tc_scene_registry.c` cleanup remains. | Закрыть; завести/сделать отдельный cleanup для dead file. |
| #115 | Сделано | Central builtin component catalog removed into lightweight domain provider packages. | Закрыть; broader standard/optional policy вести в #116. |
| #116 | Зонт / план | Standard vs experimental SDK packages remains open. | Оставить. |
| #119 | Баг | `termin run dev` player shutdown still exits 139/leaks after build-time leaks fixed. | Оставить высоким приоритетом; связан с #34/#77/#100. |
| #120 | Сделано | `termin-components-kinematic` added to standard player runtime seed; tests updated. | Закрыть. |
| #122 | Сделано / On Test | Requirement specifiers/extras enforcement implemented with regression tests. | Закрыть после полного build/test run, либо перевести Done. |
| #125 | Баг | Loose Python helper changes не каскадируют к dependent components. | Оставить; свежий реальный reload defect. |

## Рекомендованный порядок уборки доски

1. Закрыть очевидно выполненные карточки: #28, #29, #41, #53, #80, #120, #122.
2. Для #113, #93, #110, #106 сделать недостающие Windows/manual checks и закрыть или оставить строго как On Test.
3. Переписать зонты #27, #36, #40, #89, чтобы они отражали не историю, а текущие оставшиеся blockers.
4. Объединить leak/shutdown-related карточки в понятную структуру:
   - shutdown crash: #34/#119/#77;
   - nanobind leak diagnostics: #81/#100;
   - C++ player migration plan как implementation direction, не как отдельный дубликат.
5. После закрытия #114 завести маленький cleanup для `termin-app/core_c/src/tc_scene_registry.c` или удалить его сразу с проверкой сборки.
