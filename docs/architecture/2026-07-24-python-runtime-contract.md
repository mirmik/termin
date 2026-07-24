# Python Runtime and Threading Contract

## Status

Accepted. This is the canonical Python runtime contract for Termin.

## Runtime identity

Termin SDK, editor, launcher and development player use one bundled Python
runtime:

- CPython 3.14.6 free-threaded;
- ABI version `3.14`;
- SOABI `cpython-314t-*` on Linux and the corresponding `cp314t` ABI on
  Windows;
- `Py_GIL_DISABLED == 1`;
- `sys._is_gil_enabled() == False` before product imports.

The exact artifact and hash live in
`build-system/python-toolchain-lock.json`. CMake does not expose an ordinary
CPython profile. Every native extension shares `libnanobind-ft` and the SDK
import-graph gate rejects the first import that enables the GIL or uses another
ABI.

System Python may launch `termin_build`, but it is only a bootstrap tool. The
orchestrator materializes the pinned build interpreter before CMake, package
installation or tests. Product entry points never fall back to system
`site-packages`.

## Engine threading boundary

Free-threaded describes the Python interpreter, not the Termin engine API.
Unless a subsystem documents a stronger contract, access to engine, scene,
render and widget state is sequential. The host chooses the sequence and the
phase in which mutations are applied.

Termin does not enforce that model with:

- owner/creator thread identities;
- wrong-thread exceptions;
- hidden UI dispatch;
- `thread_local` state.

An application that performs work concurrently may publish a completion
through `termin-dispatch`. Its loop explicitly calls `drain` at a suitable
point and therefore owns ordering, budget and shutdown policy. The dispatcher
does not create threads or become part of `EngineCore`.

## Extending concurrency

A subsystem may later permit concurrent calls only by documenting and testing
its own data ownership, lifetime, publication, reentrancy and shutdown
contract. Synchronization belongs to that subsystem. The presence of 3.14t is
not by itself a reason to add speculative locks to process-global registries.

Parallel stress tests, TSAN and performance measurements are follow-up tools
for such explicitly concurrent paths, not prerequisites for using the
free-threaded interpreter with today's sequential engine contract.

## Verification

The supported gate consists of:

1. `./build-sdk.sh --no-wheels`;
2. `./run-tests.sh`;
3. installed launcher/editor/player/headless and module-reload smokes;
4. the free-threaded import-graph gate;
5. Windows build/test smoke before a runtime release is declared complete.

The language-neutral dispatcher contract is specified separately in
[Language-Neutral Deferred Dispatcher](2026-07-24-language-neutral-deferred-dispatcher.md).
