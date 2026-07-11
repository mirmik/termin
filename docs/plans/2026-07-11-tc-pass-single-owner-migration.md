# tc_pass Single-Owner Migration Plan

## Status

Implemented on 2026-07-11 for the C, C++, Python and C# surfaces. The old
`tc_pass_ref_vtable` and `retain`/`release`/`drop` API have been removed.
`tc_component` remains deliberately deferred.

The implementation was made as one continuous migration with verification
checkpoints, rather than by keeping two lifetime models alive between slices.

## Purpose and scope

Migrate `tc_pass` from the `retain`/`release`/`drop` reference-vtable protocol
to the single-owner contract established by `tc_widget`. A pass is meaningful
only while owned by one pipeline. External code receives borrowed pointers or
generation-validated references; it does not acquire shared ownership.

`tc_component` is deliberately out of scope. It remains the final migration
after the pass contract has been implemented and exercised by C++, Python,
C#, serialization, pipeline replacement and module hot reload.

Related board work: architecture card #223 and Python pass leak slice #321.

## Reference contract from tc_widget

The parts to reproduce are:

- initialization does not establish ownership;
- owned adoption receives a non-null deleter atomically;
- borrowed attachment, if retained at all, is a separate explicitly named API;
- already-owned objects are rejected with an error log;
- lifecycle/resource teardown is distinct from memory destruction;
- the container removes every internal reference and invalidates external
  handles before invoking the deleter;
- failed creation/adoption/deserialization rolls ownership back exactly once;
- the owner container invokes the deleter exactly once on remove, replacement
  or container destruction.

Unlike UI test fixtures, production passes should not normally support
borrowed attachment. A pipeline can outlive a stack/static pass and render work
may retain pass-derived state between compilation and execution. The default
pipeline API should therefore accept only owned passes. Add a borrowed API only
if a concrete supported use case is found and its lifetime can be enforced.

## Pre-migration tc_pass lifetime surfaces

- `tc_pass_ref_vtable` supplies `retain`, `release` and `drop`.
- `tc_pass_vtable::destroy` performs pass lifecycle/resource teardown and must
  not be conflated with memory destruction.
- `CxxFramePass` embeds `tc_pass`, owns an atomic refcount and deletes itself
  when the count reaches zero.
- Python-native passes use a separately allocated C shell whose body is a
  Python object. Python-created C++ passes embed the C++ object in a nanobind
  wrapper and currently install Python retain/release callbacks.
- C# installs GCHandle retain/release callbacks through generated SWIG glue.
- `tc_pipeline` retains on insertion and releases on removal/destruction.
- `TcPassRef`, Python binding wrappers, graph compilation, unknown-pass
  replacement and module hot reload expose raw or externally retained pass
  references.

## Implemented API and state machine

Core C shape:

```c
typedef void (*tc_pass_deleter)(tc_pass* pass);

bool tc_pipeline_adopt_pass(
    tc_pipeline_handle pipeline,
    tc_pass* pass,
    tc_pass_deleter deleter
);
```

Insertion and replacement have equivalent explicit-adoption variants. The
authoritative deleter belongs to the pipeline slot and moves together with the
pass. `tc_pass::deleter` is the creator-supplied default used at the transfer
boundary; adoption copies it into the slot. Pipeline identity remains
authoritative and double adoption is rejected.

States:

1. `unowned`: the creating language owns the object; `owner_pipeline` is
   invalid. The pass may carry the deleter which must be transferred on
   adoption or used by `tc_pass_delete_unowned` on rollback.
2. `owned`: one pipeline owns the pass and one non-null deleter is associated
   with it. The creator has transferred its ownership.
3. `destroying`: the slot is no longer externally resolvable; lifecycle
   teardown runs once, registry links and bindings are cleared, then the
   deleter runs once.
4. `destroyed`: no raw pointer may be observed through pipeline APIs.

There is no transition from `owned` directly to another pipeline. Reordering
inside one pipeline uses `tc_pipeline_move_pass_before`, which moves the slot
and deleter without running lifecycle teardown. Ordinary `remove_pass` always
destroys; it never returns a live ownership token.

Pipeline lookup returns borrowed pass references. They are for immediate use
and must not survive removal, replacement, pipeline destruction or module
unload. The hot-reload path no longer retains a raw pass outside its pipeline;
no production cross-mutation use case remained that required a new pass handle.

## Implementation phases

### 1. Ownership tests and pipeline storage

- Add focused tests for unowned creation, adoption, double-adoption rejection,
  pipeline destruction, explicit removal, insertion/reordering and rollback.
- Store one deleter alongside every owned pipeline pass.
- Introduce owned adoption APIs and migrate internal pipeline creation paths.
- Keep compatibility wrappers only while call sites are being migrated in the
  same change series; do not preserve refcount semantics as a permanent
  fallback.

### 2. C++ passes

- Remove `CxxFramePass::_ref_count`, `retain()` and `release()`.
- C++ factory-created passes transfer `delete CxxFramePass` as their deleter.
- Preserve `CxxFramePass::destroy()` as lifecycle/resource teardown invoked
  before the deleter.
- Make factory/adoption failures delete the still-unowned pass exactly once.
- Update `TcPass`/`TcPassRef`: owning wrappers must hold an explicit unowned
  ownership token; pipeline-facing references are borrowed/validated.

### 3. Python passes and #321

- An unattached Python-created C++ pass remains owned solely by its nanobind
  wrapper; it must not retain itself.
- Adoption transfers one managed lifetime hold to the pipeline deleter record.
- Python-native pass deletion releases the Python body and frees its C shell in
  a defined order without reading the shell after the final decref.
- Cover local-reference deletion while adopted, explicit removal, pipeline
  destruction, copy and deserialization.
- Require subprocess shutdown tests with nanobind leak diagnostics enabled.

### 4. Serialization, replacement and unknown passes

- Every deserialized/copied pass receives an independent ownership record.
- Pipeline replacement destroys the previous pass only after it has been
  removed from lookup/compiled state.
- Unknown-pass placeholder restoration transfers ownership explicitly and
  never retains both placeholder and replacement through a hidden reference.
- Graph compiler failure paths destroy all unadopted results.

### 5. Hot reload and external references

- Audit every pass pointer that can survive a pipeline mutation or module
  unload.
- Replace externally retained pass references with pipeline slot + generation
  handles where their lifetime crosses an operation boundary.
- Before unloading module code, invalidate pass handles, run lifecycle teardown
  and invoke module-specific deleters while code is still loaded.
- Reject unload if a live pass cannot be destroyed safely; log the type and
  owning pipeline.

### 6. C# and ABI cleanup

- Replace GCHandle retain/release setup with one C# pass deleter installed at
  adoption.
- Regenerate SWIG output instead of maintaining generated glue manually.
- Verify removal and pipeline shutdown on Windows.
- Delete `tc_pass_ref_vtable`, `tc_pass_retain`, `tc_pass_release`,
  `tc_pass_drop` and all compatibility comments after all consumers migrate.
- Update public docs and bump any affected plugin/binding ABI versions.

## Verification gates

- Focused C/C++ pipeline ownership and unknown-pass tests.
- Python render and components-render suites with no nanobind leak warnings.
- Copy/deserialization tests proving independent owner records.
- Module hot-reload tests covering externally observed pass invalidation.
- `./build-sdk.sh --no-wheels` followed by `./run-tests.sh`.
- Windows C# build and shutdown/removal smoke before declaring the migration
  complete.

## Verification record

- `./build-sdk.sh --no-wheels`: passed, including generated C# bindings and
  their Linux build.
- focused C++ ownership, unknown-pass and native hot-reload tests: passed;
- Python render and components-render tests: passed, including shutdown and
  exact-refcount regression coverage;
- complete `termin-render` Python suite: 37 passed;
- central C/C++ run: 62 of 63 passed. The remaining native UI showcase
  mismatch predates this migration and is caused by its missing text
  measurement service;
- complete `termin-app` Python process still exposes a separate repeat-
  bootstrap crash in runtime type/facet registry teardown. The native stack is
  `tc_resource_map_get -> tc_type_registry_unregister -> destroy_facet_record`
  while registering `FrameDebugCapturePass`; both viewport tests pass alone.
- Windows execution remains a platform verification gate; the SWIG C# surface
  and generated project compile successfully on Linux.

## Deferred tc_component migration

After the pass migration is stable, apply the same state machine to
`tc_component`. That phase must additionally account for entity requirements,
`factory_retained`, pool migration, scene capability lists and component
handles. No compatibility layer added for `tc_pass` should make the later
component migration depend on reference counting.
