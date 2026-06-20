# D3D11 Runtime Placement Goal Plan

Дата: 2026-06-20

Связанная задача:

- Kanboard #18 - `[render] Довести Direct3D11 backend MVP`

Связанные документы:

- `docs/plans/2026-06-15-d3d11-backend-readiness-plan.md`
- `termin-graphics/docs/architecture/shader-resource-contracts.md`

## Goal

Закрыть главный разрыв D3D11 MVP: `termin_shaderc` уже пишет D3D11 placement
в sidecar, но runtime shader layout и D3D11 backend пока его не потребляют.

После этого goal-pass D3D11 resource binding должен работать по явному
`register_class/register_index + stage_mask`, а не по неявному
`kind + binding` и не через привязку всех ресурсов сразу во все VS/PS/GS
стадии.

Этот goal не включает DXGI swapchain/window present. Окно имеет смысл делать
после того, как resource placement model перестанет быть переходной
эвристикой.

## Current State

- `termin_shaderc --target d3d11` генерирует `.cso` и `.layout.json` v2.
- D3D11 sidecar entries содержат:

```json
{
  "d3d11": {
    "register_class": "b",
    "register_index": 2
  }
}
```

- `tc_shader_resource_binding` сейчас хранит только `set`, `binding`,
  `kind`, `scope`, `stage_mask`, `size`, fields.
- `tc_shader_bridge` читает общие поля sidecar, но не сохраняет D3D11
  placement в runtime metadata.
- `RenderContext2` bind-by-name резолвит ресурс в `ResourceBinding` через
  `set/binding`.
- `D3D11CommandList::bind_resource_set` использует
  `binding + array_element` и привязывает uniform buffers, SRV и samplers во
  все VS/PS/GS стадии.

## Non-Goals

- Не добавлять D3D-specific branches в pass, renderer или shader authoring
  code выше runtime/backend слоя.
- Не добавлять production shader `register(...)` placement.
- Не делать DXGI/SDL window present в этом проходе.
- Не портировать material/skinned/foliage smoke до стабилизации placement
  model.
- Не пытаться поддержать storage buffers/UAVs silently. Либо explicit support,
  либо clear diagnostic.

## Desired Contract

```text
Shader source owns semantic resource declarations.
Pass and termin_graphics code own semantic resource production and binding.
termin_shaderc owns backend placement.
Runtime resolves names through the active shader layout.
Backends consume resolved placement.
```

D3D11-specific детали должны жить только в:

- shaderc placement output;
- runtime layout metadata;
- backend command/resource binding implementation.

## Phase 0: Baseline And Guardrails

1. Сверить рабочее дерево:

```powershell
git status --short
```

2. Прочитать актуальные файлы перед изменениями:

- `termin-graphics/include/tgfx/resources/tc_shader.h`
- `termin-graphics/src/tgfx2/tc_shader_bridge.cpp`
- `termin-graphics/include/tgfx2/descriptors.hpp`
- `termin-graphics/include/tgfx2/i_command_list.hpp`
- `termin-graphics/src/tgfx2/render_context.cpp`
- `termin-graphics/src/tgfx2/d3d11/d3d11_command_list.cpp`
- `termin-graphics/src/tgfx2/d3d11/d3d11_render_device.cpp`

3. Уточнить существующие tests:

- `termin-graphics/tests/tests_shader_resource_layout.cpp`
- `termin-graphics/tests/test_tgfx2_device_factory.cpp`
- `termin-graphics/tests/test_tgfx2_d3d11_smoke.cpp`
- `termin-graphics/tests/python/test_termin_shaderc_cli.py`

Acceptance:

- Понятен текущий data path:
  `termin_shaderc sidecar -> tc_shader_bridge -> tc_shader_resource_binding ->
  RenderContext2 -> ResourceSetDesc -> D3D11CommandList`.
- Нет изменений в pass/renderers до введения runtime placement model.

## Phase 1: Add Runtime D3D11 Placement Metadata

1. Расширить runtime representation. Предпочтительный вариант:

```c
typedef enum tc_shader_d3d11_register_class {
    TC_SHADER_D3D11_REGISTER_NONE = 0,
    TC_SHADER_D3D11_REGISTER_B = 1,
    TC_SHADER_D3D11_REGISTER_T = 2,
    TC_SHADER_D3D11_REGISTER_S = 3,
    TC_SHADER_D3D11_REGISTER_U = 4,
} tc_shader_d3d11_register_class;

typedef struct tc_shader_d3d11_placement {
    uint32_t register_class;
    uint32_t register_index;
} tc_shader_d3d11_placement;
```

2. Добавить placement в `tc_shader_resource_binding`:

```c
uint8_t has_d3d11_placement;
tc_shader_d3d11_placement d3d11;
```

3. Обновить копирование, сортировку, merge и validation в
   `tc_shader_registry.c`.

4. Сохранить backward compatibility для Vulkan/OpenGL sidecars:
   `has_d3d11_placement == 0` допустим для non-D3D targets.

Acceptance:

- Existing shader resource layout tests проходят без D3D11 metadata.
- `tc_shader_set_resource_layout()` не теряет D3D11 placement при копировании.
- Conflicting generic `set/binding` behavior для Vulkan/OpenGL не меняется.

## Phase 2: Parse And Validate D3D11 Sidecar Blocks

1. В `tc_shader_bridge.cpp` добавить parser для `d3d11` object:

- `register_class`: string `b`, `t`, `s`, `u`;
- `register_index`: uint.

2. Для `target == "d3d11"` требовать валидный `d3d11` block у каждого
   resource entry.

3. Для non-D3D sidecars игнорировать отсутствие `d3d11`.

4. Добавить validation конфликтов на runtime load:

```text
same stage overlap + same register_class + same register_index
```

Конфликт допустим только если это один и тот же semantic resource при merge
vertex/fragment layouts.

5. Диагностики должны логировать:

- shader uuid/name;
- resource name;
- bad register class/index;
- conflicting resources.

Acceptance:

- D3D11 sidecar v2 без `d3d11` block не загружается молча.
- Bad `register_class`/missing `register_index` возвращает failure и пишет
  actionable log.
- Same numeric index в разных classes, например `b2` и `t2`, не конфликтует.
- Same class/index в disjoint stages не конфликтует.

## Phase 3: Carry Placement Through RenderContext2

1. Расширить `tgfx::ResourceBinding` или добавить backend placement companion.

Минимальный вариант для этого pass:

```cpp
struct D3D11ResourcePlacement {
    uint8_t has_placement = 0;
    uint8_t register_class = 0;
    uint32_t register_index = 0;
    uint32_t stage_mask = 0;
};
```

2. При bind-by-name в `RenderContext2` копировать из
   `tc_shader_resource_binding`:

- `stage_mask`;
- D3D11 placement, если есть.

3. Для `bind_uniform_data()` сделать то же самое.

4. Если backend D3D11, а active shader layout не содержит D3D11 placement,
   поведение должно быть явным:

- либо fail/log error при resource set creation/bind;
- либо временно разрешить compatibility mode только для non-artifact legacy
  shaders, но не для D3D11 `.cso.layout.json`.

Предпочтение: не добавлять новый silent fallback.

Acceptance:

- ResourceBinding produced by symbolic binding carries stage mask and D3D11
  placement.
- Existing Vulkan/OpenGL tests не требуют знания D3D11 fields.
- Missing symbolic binding остается warning/error как сейчас, не silently
  creates numeric slot.

## Phase 4: Update D3D11 Resource Binding

1. В `D3D11CommandList::bind_resource_set` перестать вычислять D3D slot через
   `binding + array_element`, если D3D11 placement есть.

2. Для D3D11 использовать:

```cpp
slot = d3d11.register_index + binding.array_element;
```

3. Register class должен выбирать API:

- `b`: `*SetConstantBuffers`
- `t`: `*SetShaderResources`
- `s`: `*SetSamplers`
- `u`: explicit unsupported diagnostic for now, unless UAV support is added
  in the same pass

4. Stage mask должен выбирать stages:

- vertex -> `VSSet...`
- fragment -> `PSSet...`
- geometry -> `GSSet...`

5. Не привязывать ресурс в стадию, где shader layout его не объявил.

6. Добавить helper functions вместо большого switch duplication:

- `bind_constant_buffer_to_stages(...)`
- `bind_srv_to_stages(...)`
- `bind_sampler_to_stages(...)`

7. Обработать stale state:

- минимально: при `bind_pipeline` или перед draw очищать slots, которые были
  привязаны D3D11 backend-ом ранее, но отсутствуют в текущем resource set;
- pragmatically acceptable first step: track last bound class/stage/slot and
  clear changed/missing slots when a new resource set is bound.

Acceptance:

- A VS-only resource is not bound to PS/GS.
- A PS-only texture is not bound to VS/GS.
- `b0` and `t0` can both be bound in the same draw.
- Storage buffer/UAV binding logs a clear unsupported message instead of
  pretending success.

## Phase 5: Tests

### C/C++ Runtime Layout Tests

Extend `termin-graphics/tests/tests_shader_resource_layout.cpp` or add a
focused tgfx2 test:

1. `tc_shader_set_resource_layout` preserves D3D11 placement.
2. `tc_shader_find_resource_binding` returns placement fields.
3. Layout validation detects same stage/class/index conflict.
4. Layout validation allows same index across different classes.

### Sidecar Parser Tests

Add tests around `tc_shader_bridge` load path. If helper functions are private,
prefer exercising public artifact load path with temporary sidecar files.

Cases:

1. Valid D3D11 layout with `b2`, `t4`, `s4`.
2. Missing `d3d11` for target d3d11 fails.
3. Invalid `register_class: "x"` fails.
4. Vertex-only and fragment-only resources preserve distinct stage masks.

### D3D11 Binding Smoke

Extend `test_tgfx2_d3d11_smoke.cpp` only after metadata path is wired:

1. Create/load a shader layout that declares:
   - VS constant buffer at `b0`;
   - PS texture at `t0`;
   - PS sampler at `s0`.
2. Use `RenderContext2` bind-by-name path.
3. Draw and read back expected pixel.

This test should fail if resource binding ignores stage mask or register class.

Acceptance:

- Tests prove D3D11 placement survives from sidecar to draw binding.
- No test relies on pass code manually choosing D3D11 slots.

## Phase 6: Build And Verification Commands

Windows focused checks:

```powershell
cmake --build build\Release-tests --target tgfx2_device_factory_test --config Release
& build\Release-tests\bin\Release\tgfx2_device_factory_test.exe
```

If the current build dir is not configured with D3D11, configure a focused
test build or update the existing one with `TGFX2_ENABLE_D3D11=ON`.

Then:

```powershell
cmake --build build\Release-tests --target tgfx2_d3d11_smoke --config Release
ctest --test-dir build\Release-tests -C Release -R tgfx2_d3d11_smoke --output-on-failure
```

Python shaderc checks:

```powershell
.\run-tests-python.ps1 termin-graphics/tests/python/test_termin_shaderc_cli.py
.\run-tests-python.ps1 termin-graphics/tests/python/test_termin_shaderc_d3d11_builtin_matrix.py
```

Broader regression candidates if runtime layout structs change:

```powershell
.\run-tests-cpp.ps1
.\run-tests-python.ps1 termin-app/tests/test_runtime_package_exporter.py
.\run-tests-python.ps1 termin-app/tests/test_project_builder.py
```

Acceptance:

- Focused C++ tests pass.
- Python shaderc D3D11 tests pass or skip cleanly when real `slangc`/`fxc`
  are unavailable.
- No new LNK warnings/errors from export changes.

## Phase 7: Documentation And Kanboard

1. Update `docs/plans/2026-06-15-d3d11-backend-readiness-plan.md` current
   state after implementation.
2. If runtime metadata changes are durable API, update the live shader
   resource contract doc, not only this plan.
3. Add a Kanboard #18 comment with:

- implemented files;
- tests run;
- remaining blockers.

4. Do not close #18 unless:

- D3D11 placement is consumed end-to-end;
- `tgfx2_d3d11_smoke` runs in a D3D11-enabled Windows build;
- remaining work is split into narrower follow-up cards.

## Stop Conditions

Stop and report before continuing if:

- making `tc_shader_resource_binding` ABI larger breaks installed Python/C++
  bindings in a way that requires a coordinated SDK rebuild policy;
- D3D11 placement conflicts with current generated sidecars from builtin
  shaders;
- D3D11 smoke cannot be built because the local CMake configuration lacks
  Windows SDK or D3D compiler tools;
- fixing resource binding requires changing pass/render code above
  `RenderContext2`.

## Expected End State

At the end of this goal-pass:

- D3D11 sidecar metadata is represented in runtime shader layout.
- RenderContext2 bind-by-name carries D3D11 placement to backend resource
  sets.
- D3D11 backend binds resources to correct register class, index and stage.
- The remaining D3D11 work is clearly reduced to:
  - DXGI/SDL present path;
  - unsupported resource kinds/UAV policy;
  - broader material/skinned/foliage/editor smoke coverage.
