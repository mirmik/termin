# tgfx2 Backend Binding Layer Completion Goal Plan

Дата: 2026-06-21

Этот документ предназначен как рабочий план для запуска через долгую goal-сессию.
Он дополняет архитектурный документ
`docs/plans/2026-06-21-tgfx2-backend-binding-plan-layer.md` и фиксирует
порядок доведения слоя до основного контракта tgfx2.

## Goal Prompt

Цель: довести tgfx2 backend binding layer до состояния, где
`RenderContext2` и migrated shader paths передают backend-ам semantic resource
values плюс backend binding plan, а OpenGL, D3D11 и Vulkan исполняют placement в
своей native модели без подделки под центральную numeric descriptor модель.

Работать по фазам ниже. После каждой фазы:

- собрать затронутые targets;
- запустить focused tests;
- обновить этот план и, при необходимости, живую документацию;
- зафиксировать найденные технические хвосты в Kanboard #21 или отдельной
  задаче, если хвост выходит за scope текущей миграции.

Не считать цель завершённой, пока migrated path для OpenGL, D3D11 и Vulkan не
использует `BoundResourceSetDesc` / `BackendBindingPlanEntry` как основной
источник placement.

## Current State Snapshot

На 2026-06-21 уже сделано:

- `IRenderDevice::pipeline_resource_layout_token()` добавлен как neutral API.
- `ResourceSetDesc::resource_layout_token` добавлен рядом с transitional
  `descriptor_set_layout`.
- `tgfx2/backend_binding_plan.hpp` добавил:
  - `ShaderResourceKey`;
  - `BackendPlacement`;
  - `BackendBindingPlanEntry`;
  - `BackendBindingPlan`;
  - `BoundResourceValue`;
  - `BoundResourceBinding`;
  - `BoundResourceSetDesc`.
- `RenderContext2` строит `BackendBindingPlan` для active backend и symbolic
  bindings резолвит через plan entries.
- `IRenderDevice::create_bound_resource_set()` добавлен как backend boundary
  API с default adapter в legacy `ResourceSetDesc`.
- OpenGL backend напрямую потребляет `BoundResourceSetDesc`:
  - UBO / SSBO / texture / sampler placement берётся из
    `BackendBindingPlanEntry::placement.opengl`;
  - добавлен runtime test `tgfx2_opengl_bound_resource_set`.
- D3D11 backend напрямую потребляет `BoundResourceSetDesc`:
  - `b/t/s/u` placement берётся из
    `BackendBindingPlanEntry::placement.d3d11`;
  - `tgfx2_d3d11_smoke` normal-material pass переведён на
    `create_bound_resource_set()`;
  - Windows runtime validation ещё требуется.
- Vulkan backend напрямую потребляет `BoundResourceSetDesc`:
  - descriptor placement берётся из
    `BackendBindingPlanEntry::placement.vulkan`;
  - descriptor writes строятся из resolved resource values, а не из
    `ResourceBinding::set/binding`;
  - dynamic UBO offsets сохранены через `VkResourceSetResource`;
  - `tgfx2_vulkan_smoke` содержит bound-resource-set runtime case.
- `RenderContext2` migrated symbolic path audited as bound-first:
  - planned symbolic bindings are emitted as `BoundResourceSetDesc`;
  - planned symbolic bindings preserve shader scope in `BoundResourceGroup`
    entries at the backend boundary;
  - numeric `ResourceBinding` entries remain only as explicit legacy side
    channel;
  - comments were updated to stop describing Vulkan/OpenGL/D3D11 as flattened
    `ResourceSetDesc` consumers.
- Scope-aware boundary shape added:
  - `BoundResourceSetDesc::groups` carries frame/pass/material/draw/transient
    buckets;
  - each `BoundResourceGroup` carries a `dirty` flag;
  - `BoundResourceSetDesc::bindings` remains as flat compatibility input when
    no groups are present;
  - OpenGL, D3D11, Vulkan, and the legacy adapter consume grouped bindings via
    the same iteration contract;
  - OpenGL and D3D11 command lists skip clean groups and rebind only dirty
    scopes;
  - repeated symbolic binds with unchanged resolved value do not dirty the
    scope or recreate the current resource set;
  - Vulkan still consumes all groups to build a complete descriptor set;
  - OpenGL/Vulkan smoke coverage now uses grouped bound resource sets.
- Binding-plan validation hardened:
  - incompatible duplicate semantic names are rejected;
  - D3D11 missing placement, class mismatch, and stage/register conflicts are
    rejected;
  - D3D11 class-separated same numeric index (`b2` + `t2`) is allowed;
  - OpenGL UBO/SSBO/image binding point and texture/sampler unit conflicts are
    rejected;
  - Vulkan non-zero set and duplicate `(set,binding)` conflicts are rejected;
  - Vulkan `create_bound_resource_set()` rejects wrong backend placement and
    descriptor-kind/value-kind mismatches.
- Legacy numeric API documented as compatibility path:
  - `ResourceBinding` / `ResourceSetDesc` comments mark them as low-level
    numeric compatibility types;
  - `IRenderDevice::create_resource_set()` is documented as legacy numeric path;
  - `IRenderDevice::create_bound_resource_set()` is documented as the primary
    migrated backend boundary.
- Live architecture documentation added:
  - `termin-graphics/docs/architecture/backend-binding-plan.md`;
  - indexed from `termin-graphics/docs/architecture/index.md`.

Что всё ещё transitional:

- Scope groups now reach the backend boundary and OpenGL/D3D11 use dirty flags
  for native slot rebinding. Vulkan resource set creation still processes the
  whole grouped state because descriptor sets require complete descriptor
  contents.
- `ResourceBinding` остаётся value + placement struct и используется как
  compatibility adapter.
- `pipeline_resource_layout_token()` всё ещё opaque transitional token, а не
  полноценный `PipelineResourceLayout` handle.
- validation в `build_backend_binding_plan()` базовая, не закрывает все limits
  и capability checks.

## Latest Verification Snapshot

Локальная Linux-проверка на 2026-06-21:

- `./build-sdk.sh --no-wheels` passed.
- `./setup-test-venv.sh --force` was run after rebuilding SDK bindings.
- `./run-tests-python.sh termin-graphics/tests/python/` passed:
  `55 passed, 2 skipped`.
- `./run-tests.sh` passed:
  - C/C++: `22/22` tests passed;
  - Python: `560 passed, 6 skipped`.

Отложенный completion gate: Windows runtime validation for the D3D11 bound path.
Эта проверка intentionally оставлена на отдельный Windows pass. Linux verifies
D3D11 sidecar/shaderc metadata and compilation-adjacent behavior, but it does
not execute the D3D11 command-list smoke.

Windows gate preparation:

- Added `scripts/validate-tgfx2-d3d11-bound-path.ps1`.
- Added CI job `tgfx2-d3d11-bound-windows` on `windows-latest`.
- Kanboard #21 was updated with the prepared-but-not-yet-proven Windows gate
  status.
- Kanboard #92 tracks the deferred Windows validation pass:
  `[graphics/d3d11] Validate tgfx2 bound resource path on Windows`.
- The script configures a D3D11-focused test build, builds
  `tgfx2_d3d11_smoke`, and runs the matching CTest filter.
- The script mirrors the existing Visual Studio generator guard and uses
  MSBuild `/m:1` for target builds to avoid known solution-level races.
- Optional `-WindowTests` additionally builds/runs
  `backend_window_d3d11_present` when SDL/window testing is available.

The gate is deferred until this Windows job or an equivalent Windows host run
has produced a passing result. Do not treat the Linux pass as proof of D3D11
runtime execution.

## Non-Goals

Не делать в рамках этой goal-сессии:

- массовую перепись shader compiler / sidecar schema без отдельного плана;
- multi-set Vulkan layout migration, если single set ещё не переведён на
  `BoundResourceSetDesc`;
- удаление public legacy numeric API до того, как все backend-и имеют direct
  bound path;
- новые fallback-и по имени ресурса в backend command lists;
- silent remapping при неверном backend placement.

Если старый путь падает после миграции migrated shader path, это допустимо,
если падение диагностируемое и не ломает явно legacy API.

## Definition Of Done

Слой можно считать доведённым до архитектурно полезного состояния, когда:

1. OpenGL, D3D11 и Vulkan имеют concrete
   `create_bound_resource_set(BoundResourceSetDesc, legacy_numeric_bindings)`.
2. OpenGL command list берёт placement из `placement.opengl`.
3. D3D11 command list берёт placement из `placement.d3d11`.
4. Vulkan descriptor update берёт placement из `placement.vulkan`, а не из
   `ResourceBinding::set/binding`.
5. `RenderContext2` migrated symbolic path не создаёт backend placement сам.
6. Legacy numeric APIs отделены и названы как compatibility / low-level path.
7. Binding-plan validation ловит missing placement, wrong backend placement,
   duplicate/conflicting slots и очевидные backend limit violations.
8. Есть runtime coverage:
   - OpenGL bound resource set;
   - D3D11 bound resource set;
   - Vulkan bound resource set.
9. Документация называет live contract:
   semantic shader interface -> backend binding plan -> bound resource values
   -> backend-native execution.

## Phase 1: Validate Current D3D11 Step On Windows

Зачем: D3D11 direct bound path уже внесён, но Linux не может проверить runtime.
Перед дальнейшей миграцией нужно закрыть этот риск.

Tasks:

- Собрать SDK / tests на Windows.
- Запустить `tgfx2_d3d11_smoke`.
- Убедиться, что normal-material pass с `BoundResourceSetDesc` проходит.
- Если test падает:
  - проверить register placement `b0/b1`;
  - проверить `stage_mask`;
  - проверить, что `BoundResourceValue::offset == 0`;
  - проверить constant-buffer alignment / size.
- После фикса повторить smoke.

Commands:

```powershell
.\scripts\validate-tgfx2-d3d11-bound-path.ps1
ctest --test-dir build\Release-tests -C Release -R tgfx2_d3d11_smoke --output-on-failure
ctest --test-dir build\Release-tests -C Release -R backend_window_d3d11_present --output-on-failure
```

Acceptance:

- `tgfx2_d3d11_smoke` проходит на Windows.
- Если `backend_window_d3d11_present` не проходит по внешней причине, причина
  записана отдельно, но `tgfx2_d3d11_smoke` всё равно должен пройти.
- План обновлён с фактическим Windows result.

Stop Conditions:

- D3D11 smoke падает из-за shader compiler / SDK setup, а не из-за binding
  layer. Тогда завести отдельный task и продолжать только если runtime path
  можно проверить другим D3D11 smoke.

## Phase 2: Vulkan Direct Bound Resource Sets

Зачем: это главный недостающий backend. После этой фазы все backend-и будут
симметрично потреблять placement из binding plan.

### 2.1 Data Model

Tasks:

- Расширить `VkResourceSetResource`:
  - сохранить `BoundResourceSetDesc bound_desc`;
  - сохранить `std::vector<ResourceBinding> legacy_numeric_bindings`;
  - добавить `bool has_bound_desc`.
- Добавить override:

```cpp
ResourceSetHandle create_bound_resource_set(
    const BoundResourceSetDesc& desc,
    const std::vector<ResourceBinding>& legacy_numeric_bindings = {}) override;
```

- Не удалять `create_resource_set()`; legacy tests and low-level code должны
  продолжать работать.

Acceptance:

- Vulkan backend собирается.
- `create_bound_resource_set()` пока может вызывать common internal helper, но
  не должен терять `BoundResourceSetDesc`.

### 2.2 Descriptor Update From Plan Placement

Tasks:

- Вынести общую часть `create_resource_set()` в helper, который умеет строить
  descriptor writes из двух источников:
  - legacy `ResourceSetDesc`;
  - new `BoundResourceSetDesc`.
- Для bound path:
  - descriptor set layout token брать из `BoundResourceSetDesc`.
  - expected binding искать по `placement.vulkan.binding`.
  - descriptor type брать из `placement.vulkan.descriptor_kind`, сверяя с
    pipeline reflected layout.
  - set пока требовать `0`, как текущий guard для multi-set.
  - buffer/texture/sampler handles брать из `BoundResourceValue`.
- Dynamic UBO semantics сохранить:
  - если pipeline layout binding ожидает dynamic UBO, descriptor type должен
    остаться `VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC`;
  - dynamic offsets должны продолжить попадать в `VkResourceSetResource`.

Important:

- Не использовать `ResourceBinding::set/binding` внутри bound path.
- Если нужен temporary lookup key, строить его из
  `BackendBindingPlanEntry::placement.vulkan`.
- Missing bound value для descriptor binding должен иметь понятный log/error.

Acceptance:

- Existing Vulkan smoke continues passing.
- New bound Vulkan smoke passes.
- Negative validation catches wrong Vulkan placement kind.

### 2.3 Vulkan Runtime Test

Add or extend test:

- preferred: add focused case to `tgfx2_vulkan_smoke`;
- alternative: new `tgfx2_vulkan_bound_resource_set`.

Test shape:

- Create simple pipeline with one UBO.
- Create `BoundResourceSetDesc` with:
  - `placement.kind = VulkanDescriptor`;
  - `placement.vulkan.set = 0`;
  - `placement.vulkan.binding = reflected binding`;
  - `placement.vulkan.descriptor_kind = UniformBuffer`.
- Bind resource set and draw offscreen.
- Read center pixel with `read_pixel_rgba8()`.

Acceptance:

- Test fails if Vulkan ignores `BoundResourceSetDesc`.
- Test fails if descriptor update accidentally reads only legacy
  `ResourceBinding::binding`.

Commands:

```bash
cmake --build build/Release-tests --target tgfx2_vulkan_smoke --config Release
ctest --test-dir build/Release-tests -R '^tgfx2_vulkan_smoke$' --output-on-failure
```

Stop Conditions:

- Vulkan descriptor cache lifetime becomes ambiguous after adding bound sets.
  Stop, document the cache ownership issue, and split it before continuing.

## Phase 3: Make Bound Path The Primary RenderContext2 Contract

Зачем: после Phase 2 backend-и умеют принимать bound sets напрямую. Теперь
нужно убрать migrated path с legacy adapter как основной формы.

Tasks:

- Audit `RenderContext2`:
  - `use_shader_resource_layout()`;
  - `bind_uniform_data()`;
  - queued symbolic bindings;
  - `flush_resource_set()`;
  - `build_pending_bound_resource_set()`.
- Убедиться, что migrated symbolic path:
  - хранит `BackendBindingPlanEntry`;
  - хранит только `BoundResourceValue`;
  - вызывает `create_bound_resource_set()`;
  - не строит `ResourceBinding`, кроме explicit legacy numeric bindings.
- Переименовать helper-и, если они всё ещё звучат как flattening в main path.
  Например:
  - `legacy_resource_set_desc_from_bound()` оставить только в compatibility
    layer;
  - не использовать его в concrete migrated backend paths.
- Добавить comments там, где numeric API остаётся intentionally legacy.

Acceptance:

- Search results показывают, что `legacy_resource_set_desc_from_bound()` не
  используется в migrated RenderContext2 direct path, кроме default adapter for
  unported/custom backend.
- `RenderContext2` не инспектирует backend-specific placement fields напрямую.
- Existing symbolic bind tests pass.

Useful searches:

```bash
rg -n "legacy_resource_set_desc_from_bound|ResourceBinding|create_resource_set|create_bound_resource_set|d3d11|descriptor_set_layout" termin-graphics/src/tgfx2 termin-graphics/include/tgfx2
```

## Phase 4: Binding Plan Validation Hardening

Зачем: сейчас слой есть, но неправильный sidecar / reflection может доехать до
command list. Ошибки должны ловиться раньше.

Tasks:

- Expand `build_backend_binding_plan()` validation:
  - backend placement kind must match active backend;
  - missing placement is error;
  - duplicate semantic resource names with incompatible kind/scope are error;
  - duplicate backend slots are error where backend cannot alias them;
  - array count must be non-zero;
  - resource kind must match descriptor/register/binding class.
- D3D11:
  - validate `b/t/s/u`;
  - validate slot ranges:
    - constant buffers: `D3D11_COMMONSHADER_CONSTANT_BUFFER_API_SLOT_COUNT`;
    - SRV: `D3D11_COMMONSHADER_INPUT_RESOURCE_SLOT_COUNT`;
    - samplers: `D3D11_COMMONSHADER_SAMPLER_SLOT_COUNT`;
    - UAV policy must be explicit.
  - conflict key: `(stage mask intersection, register class, register index)`.
- OpenGL:
  - distinguish binding point and texture unit conflicts;
  - UBO and SSBO binding points have separate limits;
  - texture units and sampler units must be consistent;
  - image units require explicit unsupported or implemented policy.
- Vulkan:
  - set must be `0` until multi-set support lands;
  - descriptor type must match resource kind;
  - descriptor count/array count must match or be compatible;
  - duplicate `(set,binding)` is error unless it is the same logical resource
    merged across stages.

Tests:

- Add unit cases in `tgfx2_device_factory_test` or a new focused test file:
  - missing D3D11 placement;
  - wrong placement kind for active backend;
  - D3D11 `b2` + `t2` allowed;
  - D3D11 duplicate `b2` same stage rejected;
  - OpenGL UBO binding conflict rejected;
  - OpenGL texture unit conflict rejected;
  - Vulkan non-zero set rejected;
  - Vulkan wrong descriptor kind rejected.

Acceptance:

- Bad placement fails at plan build or resource set creation, not silently at
  draw time.
- Error messages name resource and backend placement.

Commands:

```bash
cmake --build build/Release-tests --target tgfx2_device_factory_test --config Release
ctest --test-dir build/Release-tests -R '^tgfx2_device_factory_test$' --output-on-failure
```

## Phase 5: Scope-Aware Resource Groups

Status: partially implemented. The backend boundary shape and `RenderContext2`
bucket preservation are now in place:

- `BoundResourceGroup` was added.
- `BoundResourceSetDesc::groups` is the preferred migrated representation.
- `BoundResourceGroup::dirty` identifies scopes changed since the previous
  emitted resource set for the current pass/pipeline.
- `BoundResourceSetDesc::bindings` remains as flat compatibility input when
  `groups` is empty.
- `RenderContext2` emits planned symbolic resources into groups by shader
  scope.
- OpenGL, D3D11, Vulkan, and the legacy adapter consume grouped bindings when
  present.
- OpenGL and D3D11 skip clean groups when applying native slot bindings.
- Vulkan still consumes all groups to build a complete descriptor set.
- OpenGL and Vulkan runtime smoke tests now submit grouped bound resource sets;
  D3D11 smoke uses grouped frame/draw bindings but still needs Windows runtime
  validation.

Still remaining: Windows runtime validation for D3D11 grouped dirty binding and
any broader pass/material ownership changes. Keep ownership changes in the
follow-up unless a separate goal explicitly pulls them into implementation.

Tracking: Kanboard #91 - `[render] Add scope-aware resource groups to tgfx2
binding boundary`.

Зачем: backend-и должны видеть frame/pass/material/draw groups so they can bind
native slots efficiently and without descriptor-set shaped assumptions. The
first boundary-level step is done; the next step is using the preserved groups
for dirty-scope rebinding and backend-specific update minimization.

Design Direction:

```cpp
enum class ResourceBindingScope {
    Frame,
    Pass,
    Material,
    Draw,
    Transient,
    Unscoped,
};

struct BoundResourceGroup {
    ShaderResourceScope scope;
    std::vector<BoundResourceBinding> bindings;
};

struct BoundResourceSetDesc {
    uintptr_t resource_layout_token;
    std::vector<BoundResourceGroup> groups;
    // transitional flat bindings may remain during migration
};
```

Tasks:

- [x] Decide whether to extend `BoundResourceSetDesc` in-place or add
  `BoundResourceBundle` / `BackendResourceBindings`.
- [x] Keep compatibility with current flat list during migration.
- [x] Make `RenderContext2` preserve scope buckets until backend boundary.
- [x] Backend execution consumes grouped bindings:
  - OpenGL: binds grouped entries by binding points / texture units.
  - D3D11: binds grouped entries by stage/register class.
  - Vulkan: still updates descriptor set for now, but grouping prepares multi-set
    descriptor layouts.
- [x] Use preserved groups for dirty-scope rebinding/update minimization.

Acceptance:

- [x] Dirty tracking can identify which scopes changed.
- [x] No backend needs to infer scope from resource name.
- [x] Flat list remains only as compatibility representation.

Stop Conditions:

- If scope grouping requires rewriting material/pass ownership code, stop and
  split a separate material binding migration task.

## Phase 6: Pipeline Resource Layout Handle

Зачем: `pipeline_resource_layout_token()` is neutral enough for transition, but
still too weak. The final layer needs an explicit resource layout object/handle.

Tasks:

- Introduce type:

```cpp
struct PipelineResourceLayoutHandle {
    uint32_t id;
};
```

or keep opaque `uintptr_t` internally but expose a named C++ type.

- Clarify ownership:
  - pipeline owns/caches backend binding plan/layout;
  - resource sets reference a layout token/handle;
  - invalid layout handle must be a hard error.
- Update API names and comments:
  - `pipeline_descriptor_set_layout()` stays deprecated compatibility only;
  - new code uses `pipeline_resource_layout_token()` or handle.
- Eventually move layout-specific validation into backend layout object, not
  every resource set creation.

Acceptance:

- Docs no longer describe OpenGL/D3D11 layout as fake descriptor-set layout.
- Vulkan may still map resource layout to descriptor set layout internally.
- D3D11/OpenGL layout identity remains pipeline-local/backend-native.

## Phase 7: Legacy Numeric API Deprecation

Зачем: old API may stay, but it must be clearly low-level and not the migrated
shader path.

Tasks:

- Document `ResourceBinding` as legacy/low-level value+placement struct.
- Rename internal helpers if useful:
  - `bind_legacy_resource_binding`;
  - `legacy_numeric_bindings`;
  - avoid ambiguous helper names in migrated code.
- Add comments in `IRenderDevice::create_resource_set()` and
  `create_bound_resource_set()`.
- Search for new production uses of `ResourceBinding` and classify:
  - acceptable legacy low-level path;
  - should migrate to `BoundResourceSetDesc`;
  - bug.

Acceptance:

- New migrated shader/material code has no reason to author numeric backend
  slots.
- Legacy API use sites are explicit and searchable.

## Phase 8: Documentation And Live Contract

Зачем: plans are not live source of truth. When implementation stabilizes, move
the result into architecture docs.

Tasks:

- Update or create live docs under `termin-graphics/docs/architecture/`:
  - shader resource contracts;
  - pipeline resource layout;
  - backend binding plan;
  - legacy numeric API status.
- Update `docs/plans/2026-06-21-tgfx2-backend-binding-plan-layer.md` with final
  status.
- Update `docs/plans/index.md` if new docs are added.
- Add a short migration note for future backend authors:
  - implement `create_bound_resource_set()`;
  - consume backend placement from `BackendBindingPlanEntry`;
  - keep default adapter only if backend is intentionally legacy.

Acceptance:

- A new engineer can understand the contract without reading this goal plan.
- Plan document clearly says what remains future work.

## Verification Matrix

Linux focused checks:

```bash
cmake -S . -B build/Release-tests
cmake --build build/Release-tests --target termin_graphics2 --config Release
cmake --build build/Release-tests --target tgfx2_device_factory_test --config Release
cmake --build build/Release-tests --target tgfx2_opengl_bound_resource_set --config Release
cmake --build build/Release-tests --target tgfx2_vulkan_smoke --config Release
ctest --test-dir build/Release-tests -R '^tgfx2_device_factory_test$' --output-on-failure
ctest --test-dir build/Release-tests -R '^tgfx2_opengl_bound_resource_set$' --output-on-failure
ctest --test-dir build/Release-tests -R '^tgfx2_vulkan_smoke$' --output-on-failure
ctest --test-dir build/Release-tests -R '^tgfx_tests$' --output-on-failure
git diff --check
```

Full project check when scope is large enough:

```bash
./run-tests.sh
```

Python shaderc checks when shader sidecar/reflection behavior changes:

```bash
./run-tests-python.sh termin-graphics/tests/python/test_termin_shaderc_cli.py
```

Windows D3D11 checks:

```powershell
.\scripts\validate-tgfx2-d3d11-bound-path.ps1
ctest --test-dir build\Release-tests -C Release -R tgfx2_d3d11_smoke --output-on-failure
ctest --test-dir build\Release-tests -C Release -R backend_window_d3d11_present --output-on-failure
```

SDK build after public API / binding changes:

```bash
./build-sdk.sh --no-wheels
./setup-test-venv.sh --force
```

## Risk Register

### Vulkan Descriptor Cache Lifetime

Risk: bound resource set creation may interact poorly with existing descriptor
set cache/hash logic.

Mitigation:

- keep legacy cache intact first;
- add separate hash for bound desc based on placement + values;
- do not share cached descriptor set if layout token differs.

### Dynamic Uniform Buffer Semantics

Risk: Vulkan dynamic offsets currently depend on `ResourceBinding` path.

Mitigation:

- explicitly preserve dynamic offset computation in bound path;
- add a Vulkan test for ring/dynamic UBO if current smoke has such coverage.

### Over-Broad API Churn

Risk: trying to replace `ResourceSetDesc` everywhere in one pass can break
unrelated low-level paths.

Mitigation:

- migrate backend concrete bound path first;
- only then classify and deprecate legacy API.

### Scope Grouping Blast Radius

Risk: scope groups touch material/pass ownership and may drag in renderer
architecture.

Mitigation:

- keep Phase 5 separate;
- stop and split if pass/material code needs broad rewrite.

### Hidden Shader Sidecar Assumptions

Risk: plan builder validation can expose invalid old sidecars.

Mitigation:

- prefer failing loudly during active development;
- document any intentional compatibility exception;
- do not add silent fallback placement.

## Suggested Goal Chunking

If this is run as a long goal, use these checkpoints:

1. Validate D3D11 on Windows or record blocker.
2. Implement Vulkan `create_bound_resource_set()` storage and internal helper.
3. Move Vulkan descriptor writes to `placement.vulkan`.
4. Add Vulkan bound runtime test.
5. Audit `RenderContext2` and remove migrated legacy adaptation.
6. Harden validation and add negative tests.
7. Implement boundary-level scope grouping.
8. Implement dirty-scope rebinding optimization for native-slot backends.
9. Update live docs and final status.

Recommended stopping point for one goal: finish checkpoints 1-8. Broader
pass/material ownership changes should still be split if they appear during
later renderer work.

## Completion Checklist

- [ ] D3D11 smoke validated on Windows. Deferred to Kanboard #92.
- [x] Vulkan stores `BoundResourceSetDesc`.
- [x] Vulkan descriptor writes use `placement.vulkan`.
- [x] Vulkan bound runtime test added.
- [x] OpenGL bound runtime test remains passing.
- [ ] D3D11 bound runtime test remains passing. Deferred to Kanboard #92.
- [x] `RenderContext2` migrated path is bound-first.
- [x] `RenderContext2` preserves planned binding scopes in `BoundResourceGroup`.
- [x] Dirty-scope rebinding uses preserved groups for update minimization.
- [x] Binding plan validation covers wrong/missing placement.
- [x] Legacy numeric API documented as compatibility path.
- [x] Architecture docs updated.
- [x] Kanboard #21 updated with final status.
