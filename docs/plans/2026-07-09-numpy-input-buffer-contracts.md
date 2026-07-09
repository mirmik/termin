# NumPy-only input buffer contracts migration

Дата: 2026-07-09

Статус: инструкция для goal-run. Scope намеренно ограничен входными public binding contracts.

Связанные карточки:

- `#221 [bindings] Accept buffer-compatible bulk data instead of NumPy-only arrays`
- `#214 [python/api] Replace NumPy bulk buffer contracts with native buffer types`

Исходный аудит: [NumPy Usage Inventory](../analysis/2026-07-07-numpy-usage-inventory.md).

## Goal prompt

Use this as the goal objective:

```text
Implement the first pass of #221: public nanobind input paths that only need typed contiguous CPU memory should accept generic buffer-compatible data instead of NumPy-only arrays. Keep NumPy callers working, do not change NumPy-returning APIs, add representative non-NumPy buffer tests, and document the remaining scope.
```

## Intent

This pass should remove NumPy as a required input ABI for selected public C++/nanobind bulk-data entry points. It should not remove NumPy from Python compute/authoring modules and should not solve native buffer return objects.

The desired public contract for migrated inputs:

- accepts NumPy arrays through the generic buffer path;
- accepts at least one non-NumPy buffer-compatible object where practical, for example `array.array`, `memoryview`, `bytes`, or `bytearray`;
- requires explicit dtype, shape, and C-contiguity;
- rejects incompatible inputs with clear Python exceptions and C/C++ logs where the local code logs validation failures;
- avoids silent dtype conversion, hidden reshaping, or implicit copies unless the specific API already has an explicit copy boundary.

## Non-goals

- Do not replace `nb::ndarray<nb::numpy, ...>` return values in this pass.
- Do not remove NumPy from mesh/image/parser/solver Python code that genuinely computes with NumPy.
- Do not introduce a complete Python wrapper for `tc_tensor` unless a narrow helper is needed and can be finished with tests.
- Do not change runtime package dependency policy for NumPy in this pass.
- Do not accept arbitrary Python sequences as bulk buffers unless the target API already had such a contract.

## Starting points

Audit current native binding inputs with:

```bash
rg -n "nb::ndarray<|nb::numpy|nb::cast<nb::ndarray" \
  -g '*.cpp' -g '*.hpp' \
  --glob '!build/**' --glob '!sdk/**'
```

Likely first targets:

- `termin-graphics/python/bindings/immediate_bindings.cpp`: immediate mesh/line draw inputs still use `nb::numpy`.
- `termin-render-passes/python/render_passes_bindings.cpp`: matrix input helpers still use `nb::numpy`; matrix returns are out of scope.
- `termin-render/python/render_framework_bindings.cpp`: model/view/projection matrix input casts still use `nb::numpy`.
- `termin-materials/python/bindings/material_bindings.cpp`: color/vector array casts still use `nb::numpy`.
- Existing generic-buffer paths in `termin-mesh`, `termin-graphics/tgfx2`, `termin-voxels`, `termin-navmesh`, and `tcplot` should be used as reference and cleaned up only if needed for consistency.

Prefer representative coverage over touching every possible file. If a file mostly exposes return buffers or true compute arrays, leave it documented for `#214`.

## Implementation Plan

1. Reconfirm active scope from the task board and inventory.
   - Read `scripts/taskboard show 221`.
   - Read `docs/analysis/2026-07-07-numpy-usage-inventory.md`.
   - If the board has changed materially, update this plan or the card before implementation.

2. Classify native `nb::ndarray` use.
   - Mark each occurrence as `input`, `output`, `input/output`, or `internal cast`.
   - Mark each input as `bulk buffer`, `small geometry value`, or `true NumPy/compute`.
   - Only migrate `bulk buffer` and simple matrix/vector input contracts where the function immediately reads or copies data.

3. Add or reuse a small shared validation helper if local duplication starts growing.
   - It can stay in the module being migrated for the first slice if there is no stable cross-module include location.
   - If shared across modules, prefer a low-level binding helper near `termin-base`/`tcbase` rather than a render- or mesh-owned helper.
   - The helper should make dtype, ndim/shape, and C-contiguity checks explicit.

4. Migrate selected inputs from NumPy-only to generic CPU buffer contracts.
   - Replace `nb::ndarray<nb::numpy, T, ...>` input parameters with `nb::ndarray<T, nb::c_contig, nb::device::cpu, ...>` or an equivalent validated buffer view.
   - For `bytes`/`bytearray` payload APIs, keep or add explicit byte-buffer overloads when that is clearer than pretending bytes are typed arrays.
   - Keep existing NumPy callers working without extra copies.
   - Do not change returned array/object types in the same edit unless required to compile.

5. Add representative tests.
   - At minimum, one migrated mesh/graphics/texture/render input path must be tested with a non-NumPy object.
   - Also test the same path with a NumPy array to prove compatibility.
   - Add a negative test for wrong dtype or wrong shape when the local test harness makes that practical.
   - Prefer `array.array`/`memoryview` for typed numeric buffers and `bytes`/`bytearray` for `uint8` payloads.

6. Update documentation.
   - Add a short binding/API note describing accepted input buffer contracts.
   - Update `docs/analysis/2026-07-07-numpy-usage-inventory.md` or add a new dated note with migrated inputs and remaining intentional NumPy dependencies.
   - Record return-value NumPy arrays as remaining `#214` scope, not as unfinished `#221` work.

7. Verify.
   - Run focused Python tests for touched packages.
   - Run `./run-tests.sh` before declaring the card ready unless a known unrelated failure is documented with exact output.
   - If native bindings were rebuilt manually, prefer the normal SDK/test environment flow from `AGENTS.md`.

## Done Criteria

The goal is complete when all of the following are true:

- At least one representative public bulk input path no longer requires `nb::numpy` and accepts a non-NumPy buffer-compatible object.
- Existing NumPy callers for the migrated path still pass tests.
- Incompatible dtype, shape, or contiguity fails explicitly; there is no silent fallback conversion.
- Tests cover one successful non-NumPy buffer input and one successful NumPy input for the migrated path.
- Any remaining `nb::numpy` input contracts are listed as either intentionally out of scope, true NumPy/compute dependencies, or follow-up candidates.
- NumPy-returning APIs are unchanged or explicitly documented as deferred to `#214`.
- Relevant docs or inventory notes are updated.
- Focused tests and, if feasible, `./run-tests.sh` have been run and their result is recorded in the final goal report.

## Suggested final report format

When the goal finishes, report:

- migrated files and APIs;
- tests added or updated;
- verification commands and results;
- remaining `#221` follow-up candidates;
- `#214` items intentionally deferred, especially return buffers/native buffer objects.
