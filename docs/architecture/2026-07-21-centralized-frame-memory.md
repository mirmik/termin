# Centralized Frame Memory

## Status

Architectural sketch. This document records a possible direction and does not
yet establish a stable public API or authorize a repository-wide allocator
migration.

## Context

Hot engine paths currently choose their temporary-storage strategy locally.
Some systems construct ordinary containers for each operation, while others
retain scratch `std::vector` instances and reuse their capacity between
frames. Both approaches can be locally reasonable, but together they leave no
single place to answer basic operational questions:

- how many general-heap allocations occur during a frame;
- how much CPU scratch memory a frame needs at its peak;
- which subsystem caused a transient-memory spike;
- whether a pointer to one-frame data escaped into persistent state;
- whether the sum of independently retained container capacities is larger
  than the actual cross-system peak.

The offscreen render planner is a representative example. Its jobs, producer
table, traversal state and DFS stack are valid only during one planning call,
but their backing storage is retained in long-lived vectors so that the steady
state does not allocate. That is efficient in isolation, yet it repeats a
storage policy that other hot-path systems must independently rediscover.

The proposed direction is to make transient CPU memory an explicit engine
facility and to establish a common policy:

> CPU data that is guaranteed not to outlive the logical frame should come
> from frame memory. Data with a shorter lifetime should come from a scoped
> scratch region inside that frame. General-purpose heap allocation in a hot
> path is reserved for persistent state and diagnosed when used accidentally.

This is primarily an ownership, observability and consistency initiative. A
reduction in allocator overhead and fragmentation is expected, but is not the
only or necessarily the largest benefit.

## Goals

- Give one-frame CPU data an explicit and reviewable lifetime.
- Reuse one central backing-store high-water mark across subsystems instead of
  retaining unrelated scratch capacities in every owner.
- Make steady-state hot paths independent of the general heap.
- Collect frame-wide and per-subsystem transient-memory telemetry.
- Support both C and C++ engine modules without introducing upward module
  dependencies.
- Detect stale frame pointers and unexpected arena growth in development
  builds.
- Leave room for future parallel frame work without putting a lock around one
  global bump pointer.

## Non-goals

- Replacing persistent resource, scene, cache or registry storage.
- Managing GPU-visible allocations or resources whose destruction is delayed
  until a fence completes.
- Treating every allocation made while rendering as one-frame memory.
- Hiding unclear ownership behind a globally accessible fallback allocator.
- Replacing algorithmic improvements with a faster allocator. For example, a
  linear producer lookup in a graph planner remains a scaling problem even if
  its table is allocated from an arena.

## Lifetime classes

The policy needs more precision than a `temporary`/`persistent` split.

### Persistent

State that survives frame boundaries: scenes, components, render resources,
registries, caches, compiled pipeline descriptions and retained application
state. Its owner and destruction path remain explicit. Frame memory must not
be stored in these objects.

### Frame

CPU data valid until the end of one logical engine frame. Examples may include
frame-wide snapshots, collected work descriptions and transient lookup tables
consumed later in the same frame.

Reset is bulk and occurs only after all synchronous CPU consumers of the frame
have completed.

### Scoped scratch

Data valid only during one operation or phase. A scratch scope records an arena
marker and rewinds to that marker on scope exit. This permits memory reuse
within a frame and prevents repeated operations from accumulating duplicate
scratch until the frame ends.

The offscreen planner belongs to this class: `render_display()` may plan more
than once during one logical frame, and no planner job needs to remain valid
after its callback has completed.

### GPU in-flight

CPU or GPU data that must remain alive until submitted GPU work completes. Its
lifetime is measured in submissions, fences or frames in flight, not in CPU
frame boundaries. Staging buffers, deferred resource destruction and backend
command storage must use a separate fence-aware mechanism.

Resetting frame memory after CPU submission is not proof that these resources
are safe to release.

## Proposed ownership and module boundary

The low-level allocation primitive should live in `termin-base`. Render,
scene, GUI and engine modules already depend on the base module; placing the
primitive in `termin-engine` would either prevent lower layers from using it
or introduce invalid reverse dependencies.

The logical frame owner should live in `EngineCore`, because it owns the main
loop and composes scene update, render planning, rendering and after-render
work.

```text
termin-base
|-- tc_arena                  C-compatible block/marker primitive
|-- tc_arena_metrics          reserved, committed, peak, overflow
`-- C++ memory_resource       optional std::pmr adapter

EngineCore instance
`-- EngineFrameMemory
    `-- FrameScope (epoch N)
        |-- frame allocations
        |-- ScratchScope: scene.tick
        |-- ScratchScope: render.planner
        |-- ScratchScope: render.collection
        `-- future worker-owned arena lanes
```

The arena is owned per `EngineCore`, not by a process-global singleton. This
keeps tests, multiple runtimes, shutdown order and telemetry isolated. Access
is passed explicitly through a frame context; it is not discovered through a
global or thread-local fallback.

## Logical frame boundary

The CPU frame boundary is not the same as
`RenderContext2::begin_frame()`/`end_frame()`. A render context frame describes
a command-list submission and may occur more than once within one logical
engine frame.

For `EngineCore::run()`, the logical frame naturally surrounds one complete
loop iteration, including host event/UI work, scene tick, before-render,
rendering and after-render callbacks:

```text
begin logical frame / acquire epoch
|-- poll host events and compose UI
|-- scene tick
|-- before render
|-- render and present
|-- after render
`-- end logical frame / validate and reset
```

Standalone `tick_and_render()` and hosts that call `RenderingManager`
directly need an explicit contract as well. They must not silently operate
against stale memory left by `run()`. The final API may provide either a
top-level RAII frame scope or a host-facing `run_frame` operation, but every
entry path must establish exactly one unambiguous logical frame.

Nested engine frames should be rejected. Nested scratch scopes are expected.

## Illustrative API

The exact naming is open, but the intended ownership should be visible in the
types.

```cpp
class EngineFrameMemory {
public:
    FrameScope begin_frame();
    const FrameMemoryStats& last_frame_stats() const;
};

class FrameScope {
public:
    uint64_t epoch() const;
    std::pmr::memory_resource* resource();
    ScratchScope scratch(const char* tag);
};

class ScratchScope {
public:
    std::pmr::memory_resource* resource();
};
```

C modules need the same storage without depending on C++ containers:

```c
typedef struct tc_arena tc_arena;
typedef struct tc_arena_marker {
    size_t block_index;
    size_t offset;
    uint64_t epoch;
} tc_arena_marker;

void* tc_arena_alloc(tc_arena* arena, size_t size, size_t alignment);
tc_arena_marker tc_arena_mark(const tc_arena* arena);
void tc_arena_rewind(tc_arena* arena, tc_arena_marker marker);
```

The C++ `std::pmr::memory_resource` adapter should sit on the same primitive so
that `std::pmr::vector`, strings and maps participate in the same accounting.
The primitive itself should expose markers, tagging and diagnostics rather
than being only a thin alias for `std::pmr::monotonic_buffer_resource`.

## Allocation and destruction rules

Arena reset releases storage, not object-owned resources and not C++ object
lifetimes automatically.

- Trivially destructible arrays and records may be allocated directly.
- Local `std::pmr` containers must be destroyed before their scratch scope is
  rewound. Their destructors still matter when elements own resources.
- Placement-constructed non-trivial objects need an explicit destruction
  policy. A destructor registry may be added if real use cases justify it; it
  should not be the initial default.
- Resource-owning objects, reference-count holds and handles requiring a
  release operation should normally remain outside raw arena storage.
- No frame or scratch pointer may be stored in a persistent container, queued
  asynchronous task or callback that can run after its scope ends.

Development builds should attach an epoch to frame contexts and, where
practical, poison rewound memory. Views that cross a public boundary may carry
the source epoch so stale use can fail close to its origin.

## Backing-store and overflow policy

The arena should retain reusable blocks across frames; freeing all blocks on
every reset would merely reintroduce heap traffic under another name.

Expected behavior:

- bump allocation within committed blocks;
- bulk reset or marker rewind without per-allocation work;
- tracked acquisition of additional backing blocks on growth;
- explicit alignment and overflow checks;
- allocation failure logged at the subsystem tag and propagated to the caller;
- optional release/decay policy under memory pressure, not unconditional
  per-frame shrinking;
- a separate tracked path for unusually large allocations so one transient
  outlier does not permanently distort the ordinary block pool.

An upstream heap fallback must never be silent. It may be a legitimate growth
mechanism, but telemetry must distinguish a frame that reused existing blocks
from one that expanded the arena.

## Concurrency model

The current rendering path is sequential, but the allocator contract should
not require that forever or expose caller thread identity as a precondition.

A single mutex-protected arena shared by all future jobs would centralize
contention. The preferred extension is a central `EngineFrameMemory` owner
with explicitly assigned worker lanes or sub-arenas. Each worker allocates from
its own bump region; the frame owner collects their metrics and resets them
after all frame jobs join.

Frame memory must be passed to a worker together with its work context. There
should be no thread-local allocator lookup. An asynchronous job that may
survive the frame must copy or promote its inputs into an appropriate longer
lived owner.

## Telemetry and enforcement

The facility should report at least:

- bytes reserved and committed;
- current usage and frame high-water mark;
- allocation count;
- number and size of backing-block growth events;
- unusually large allocations;
- usage and peak grouped by subsystem tag;
- rewind/reset count and active epoch;
- failed allocations and configured limits.

Tags should be stable names such as `render.offscreen_planner`,
`render.item_collection` and `scene.scheduler`, not arbitrary dynamically
constructed strings.

Once representative systems have migrated, debug and profiling builds can add
a general-heap allocation observer around the hot frame scope. Initially it
should report remaining call sites. Turning it into an assertion is a later
policy decision and should allow documented integration boundaries where a
third-party API necessarily allocates.

## Offscreen planner as a first migration

`OffscreenRenderPlanner` is a suitable early adopter because its scratch data
has a narrow synchronous lifetime and consists mostly of trivially
destructible records:

- render jobs;
- producer entries;
- root, attachment and visitation flags;
- DFS stack;
- temporary pass-read pointers.

The target shape is a nearly stateless planner whose `execute()` receives a
frame context, opens `render.offscreen_planner` scratch, constructs PMR or
arena-backed arrays, invokes jobs synchronously, and rewinds before returning.
Its callback contract must state that the job pointer is borrowed only for the
duration of the callback.

This migration should not obscure independent algorithmic work. In particular,
the current linear `producer_for()` lookup prevents the graph build from being
strictly linear in vertices and edges. An arena-backed hash table or dense
handle index may address that separately.

## Suggested migration sequence

1. Implement and test the low-level arena, markers, alignment, overflow and
   metrics in `termin-base`.
2. Add the PMR adapter and tests covering container destruction before rewind.
3. Introduce per-instance `EngineFrameMemory` and define all top-level frame
   entry paths, including standalone ticking and direct rendering hosts.
4. Expose frame and scratch telemetry in the existing profiler/debug tooling.
5. Migrate the offscreen planner and compare output, allocation count and
   memory peaks against its existing tests.
6. Inventory other persistent scratch containers and per-operation heap
   allocations. Migrate them by demonstrated lifetime rather than by broad
   mechanical replacement.
7. Add diagnostics for general-heap allocation inside migrated hot paths.
8. Design worker lanes only when a real parallel consumer exists, preserving
   the explicit frame-context contract.

The migration should remain incremental. Persistent vectors are not wrong by
definition, and a vector that represents retained state or a deliberate cache
should not be moved merely because it is touched each frame.

## Open questions

- Should host event/UI composition be inside the canonical engine frame scope,
  or should hosts receive a separate frame-memory context?
- What is the public standalone-frame API for embedders that do not use
  `EngineCore::run()`?
- Which block sizes and large-allocation threshold fit editor and player
  workloads?
- Should arena memory decay after a number of low-usage frames, only under an
  explicit trim request, or both?
- How should frame-memory metrics be presented alongside CPU profiler sections?
- Which APIs need epoch-bearing views, and where is poisoning sufficient?
- Do any existing render callbacks retain CPU descriptions until a later GPU
  submission, requiring promotion rather than frame allocation?
