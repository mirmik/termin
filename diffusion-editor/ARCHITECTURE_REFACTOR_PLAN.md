# Diffusion Editor Architecture Refactor Plan

## Goal

Bring the diffusion editor to a healthier long-term architecture where UI,
document state, canvas interaction, generation workflows, engines, and
serialization have explicit boundaries.

The goal is not cosmetic file reshuffling. Module moves should happen only
after responsibilities are separated enough that the new layout reflects real
architecture.

## Target Shape

- `EditorWindow` is a composition root and UI shell:
  - creates panels, engines, controllers, and services;
  - wires callbacks;
  - shows dialogs/message boxes;
  - updates status text;
  - delegates application workflows to controllers/services.
- Document mutations go through commands and `DocumentService`, so undo/redo and
  dirty-state behavior remain consistent.
- Canvas owns viewport, input dispatch, rendering, and interactive tool state,
  but not generation business logic.
- Generation workflows use typed request/result/event objects.
- Engines are backend adapters with narrow request APIs, not workflow
  coordinators.
- Dialogs and panels do not reach into private `EditorWindow` state.
- Pixel-level image operations live in pure helpers covered by focused tests.
- Legacy migrations are isolated and testable.

## Current Main Problems

1. `editor_window.py` is still too large and owns several workflows.

   Diffusion workflow has been extracted, but LaMa, InstructPix2Pix,
   segmentation, and Grounding still leave pending state and submit/poll logic in
   the window.

2. `editor_canvas.py` mixes too many responsibilities.

   It currently combines input handling, tool behavior, viewport coordinate
   mapping, repaint/invalidation, and GPU compositor coordination.

3. `grounding_dialog.py` has the weakest boundary.

   It mixes UI construction, model cache, model loading, inference, threading,
   status updates, and direct writes into editor private state.

4. Some UI paths still mutate document state directly.

   Layer rename currently assigns `layer.name` directly from `LayerPanel`,
   bypassing commands/history.

5. Engine APIs are inconsistent.

   `DiffusionEngine.submit(...)` has a long argument list. Other engines have
   their own ad hoc request/poll shapes.

6. Tool runtime state, serialization, and legacy migration are coupled.

   `tool.py` is still acceptable, but it will become a pressure point when
   ControlNet, multi-reference inputs, and richer generation settings arrive.

7. The package is flat.

   This is tolerable while boundaries are being extracted, but it already makes
   subsystem ownership harder to see.

## Phase 1: Close Document Model Violations

Add commands for remaining direct document mutations.

Tasks:

- Add `SetLayerNameCommand`.
- Move layer rename in `LayerPanel` to `DocumentService`/command execution.
- Audit direct UI/canvas writes to `Layer` fields.
- Convert state changes that should participate in undo/redo into commands.
- Add undo/redo tests for layer rename and any newly commandified actions.

Success criteria:

- User-visible document mutations do not bypass the command/history path.
- Rename can be undone/redone.
- Direct mutation remains only for transient UI/runtime state.

## Phase 2: Complete Generation Workflow Boundaries

Bring LaMa and InstructPix2Pix to the same workflow shape as Diffusion.

Tasks:

- Add `InstructGenerationController`.
- Add typed Instruct request/result/event objects.
- Move Instruct load/apply/poll/pending-layer state out of `EditorWindow`.
- Add `LamaGenerationController`.
- Add typed LaMa request/result/event objects.
- Move LaMa submit/poll/pending-layer state out of `EditorWindow`.
- Keep `EditorWindow` responsible only for panel sync, status display, and
  command execution.

Success criteria:

- `EditorWindow` no longer owns `_pending_lama_layer` or
  `_pending_instruct_layer`.
- Instruct/LaMa workflows can be unit-tested with fake engines.
- Result application still goes through document commands.

## Phase 3: Unify Engine APIs

Make engines backend adapters with typed requests.

Tasks:

- Add `DiffusionEngine.submit_request(DiffusionRequest)`.
- Replace the long `DiffusionEngine.submit(...)` call path after
  `submit_request` is stable.
- Add request/result dataclasses for Instruct, LaMa, and segmentation.
- Standardize poll output into typed events instead of ad hoc tuples.
- Keep logging inside engines for failures and important lifecycle events.

Success criteria:

- Controllers call engines with a single request object.
- Engine poll result shapes are explicit and testable.
- Argument-order bugs become unlikely.

## Phase 4: Redesign Grounding

Split Grounding into UI, engine, controller, and DTOs.

Target modules:

- `grounding_types.py`: request params, box/mask result DTOs, events.
- `grounding_engine.py`: model cache, loading, DINO/SAM inference.
- `grounding_controller.py`: async lifecycle, pending result, event mapping.
- `grounding_dialog.py`: UI only.

Tasks:

- Remove direct writes to `editor._pending_grounding_result`.
- Move model loading/cache out of the dialog.
- Route results through controller events.
- Apply accepted selection/masks through document commands.
- Add tests for controller lifecycle and result mapping.

Success criteria:

- Dialog does not know editor internals.
- Grounding can be tested without constructing UI.
- Errors are logged and surfaced through typed events/status handling.

## Phase 5: Decompose Canvas Responsibilities

Turn `EditorCanvas` into a smaller canvas shell plus tool/controller helpers.

Possible boundaries:

- viewport and coordinate mapping;
- input dispatch;
- brush/paint operations;
- mask/selection operations;
- patch rectangle interaction;
- move tool behavior;
- GPU invalidation bridge.

Tasks:

- Identify cohesive method clusters in `editor_canvas.py`.
- Extract pure coordinate/viewport helpers first.
- Extract tool state machines second.
- Keep rendering and invalidation behavior stable during each step.
- Add focused tests around each extracted behavior.

Success criteria:

- Canvas remains responsible for canvas interaction, not editor workflows.
- Tool behavior is easier to test without full UI setup.
- GPU compositor invalidation paths remain explicit.

## Phase 6: Split Tool Runtime Model From Serialization

Prepare tool data for ControlNet and multi-reference inputs.

Tasks:

- Keep runtime tool classes/dataclasses focused on current editable state.
- Move tool serialization/deserialization to `tool_serialization.py`.
- Move legacy migration helpers out of normal runtime paths where possible.
- Add explicit migration tests for old tool formats.
- Avoid indefinite fallback compatibility during active development when a
  clean migration is better.

Success criteria:

- Adding a new tool/reference setting does not require scattering migration code.
- Runtime tool code is not dominated by serialization concerns.
- Legacy support is documented and tested.

## Phase 7: Reorganize Packages After Boundaries Exist

Only move modules after earlier phases make ownership clear.

Possible final layout:

```text
diffusion_editor/
  app/
    editor_window.py
    main.py
    settings.py
  document/
    layer.py
    layer_stack.py
    commands.py
    document_service.py
    history.py
    serialization.py
  canvas/
    editor_canvas.py
    canvas_tools.py
    brush.py
    gpu_compositor.py
  generation/
    types.py
    patch_resolver.py
    reference_resolver.py
    diffusion_request_builder.py
    diffusion_controller.py
    instruct_controller.py
    lama_controller.py
  engines/
    diffusion_engine.py
    instruct_engine.py
    lama_engine.py
    segmentation_engine.py
    grounding_engine.py
  ui/
    panels/
    dialogs/
```

Tasks:

- Move files in small batches.
- Update imports mechanically.
- Run full tests after each batch.
- Avoid combining package moves with behavior changes.

Success criteria:

- Package layout communicates subsystem ownership.
- Imports become more directional.
- No behavior changes are hidden inside file moves.

## Testing Strategy

- Pure helpers: fast unit tests.
- Commands/document: undo/redo and serialization roundtrip tests.
- Controllers: fake engines/builders and event lifecycle tests.
- Engines: smoke/unit tests around request dispatch and error logging where
  feasible.
- Canvas: focused interaction tests for extracted behaviors.
- UI dialogs: test pure candidate/formatting/selection helpers, not pixel UI.
- Full `./run-tests.sh` after behavior-affecting changes.

## Priority Order

1. Add `SetLayerNameCommand` and move rename to command/history.
2. Extract Instruct/LaMa generation controllers.
3. Split Grounding into engine/controller/dialog/types.
4. Add `submit_request(DiffusionRequest)` and unify engine APIs.
5. Decompose `EditorCanvas`.
6. Split tool runtime model from serialization/migration.
7. Reorganize packages once boundaries are real.

## Current Progress

- Phase 1 started.
- Added `SetLayerNameCommand`.
- Moved layer rename from direct `LayerPanel` mutation to the
  `EditorWindow`/`DocumentService` command path.
- Added `LayerStack.set_layer_name()` as the document-model mutation point used
  by the command and by non-editor fallback panel usage.
- Added undo/redo coverage for layer rename.
- Audited remaining direct writes matching document fields:
  - document mutations are now concentrated in `LayerStack`, commands,
    serialization/migration, and canvas snapshot callbacks;
  - visible direct writes in panels/windows are widget visibility, not layer
    visibility.
- Phase 2 implemented.
- Added `InstructGenerationController`.
- Added `LamaGenerationController`.
- Moved LaMa submit/poll/pending-layer state out of `EditorWindow`.
- Moved InstructPix2Pix load/apply/poll/pending-layer state out of
  `EditorWindow`.
- Added controller tests with fake engines for LaMa and Instruct lifecycle.
- Phase 3 implemented for current generation engines.
- Added typed `InstructRequest` and `LamaRequest` DTOs next to
  `DiffusionRequest`.
- Added `submit_request(...)` adapters to Diffusion, InstructPix2Pix, and LaMa
  engines.
- Updated Diffusion, InstructPix2Pix, and LaMa controllers to submit typed
  request objects instead of long argument lists.
- Added typed `SegmentationRequest` and `SegmentationResult` DTOs.
- Added `EnginePollEvent` and typed inference result DTOs for Diffusion,
  InstructPix2Pix, LaMa, and segmentation.
- Updated generation controllers to consume `poll_event()` instead of raw
  engine tuples.
- Added `SegmentationGenerationController` and moved segmentation pending-layer
  state out of `EditorWindow`.
- Kept legacy low-level `poll()` methods in engines for compatibility while
  controllers use the typed event API.
- Remaining Phase 3 cleanup: decide when to delete legacy `submit(...)`/`poll()`
  tuple APIs after all callers are migrated.
- Phase 4 implemented for the current Grounding workflow.
- Added `grounding_types.py` for model options, request params, detections,
  results, and engine events.
- Added `GroundingEngine`; DINO/SAM model caches, loading, inference, and the
  worker thread moved out of `grounding_dialog.py`.
- Added `GroundingController`; pending-layer state and request submission moved
  out of `EditorWindow`.
- `GroundingDialog` now only builds UI and emits typed `GroundingParams`.
- Grounding result application now goes through `map_grounding_result(...)` and
  document commands.
- Preserved DINO box fallback when SAM 2.1 segmentation fails, while surfacing
  the SAM error through status events and logs.
- Added controller and result-mapper tests for Grounding.
- Phase 5 started.
- Added `canvas_geometry.py` and moved canvas/layer rectangle clipping,
  coordinate conversion, visible layer rect calculation, and rect union helpers
  behind pure functions.
- Added focused geometry tests for clipped canvas/layer rectangles and offset
  layers.
- Added `canvas_rect_drag.py` for Selection/Patch rectangle drag state.
- `EditorCanvas` now delegates rectangle drag begin/move/finish/preview logic
  to `CanvasRectDrag` while preserving the existing Selection/Patch final rect
  semantics.
- Added focused rect drag tests.
- Added `soft_mask_stroke.py` for pure soft-brush dab/line operations on float
  masks.
- `EditorCanvas` now reuses the same tested soft-stroke implementation for
  layer masks, mask erase previews, and selection painting instead of carrying
  duplicated pixel math.
- Added focused soft mask stroke tests.
- Added `canvas_composite.py` with `CanvasCompositeBridge`.
- Moved CPU/GPU composite ownership, stale GPU readback, dirty layer refresh,
  move-transform refresh, and mask-erase preview composition out of
  `EditorCanvas`.
- `EditorCanvas` keeps compatibility properties for the remaining private
  callers/tests, but delegates composite updates and GPU compositor lifecycle to
  `CanvasCompositeBridge`.
- `CanvasStrokeTool` implementations now ask the canvas to refresh transformed
  layers instead of duplicating compositor invalidation logic.
- Added focused composite bridge tests for CPU refresh, move transforms, and
  GPU invalidation.
- Added `canvas_paint_stroke.py` with `PaintStrokeBuffer` and tested paint
  blending for live brush strokes.
- Removed paint stroke runtime fields from `EditorCanvas`; the canvas now asks
  the stroke buffer to apply dirty regions and only coordinates compositor
  refresh.
- Added `canvas_edit_session.py` with `CanvasEditSession` for transient mouse
  edit state, dirty accumulation, last pointer position, and edit callback
  metadata.
- Removed the scattered `_painting`/`_last_paint_pos`/edit metadata fields from
  `EditorCanvas` mouse handlers.
- Added `canvas_smudge.py` with `SmudgeStrokeBuffer` and brush-rect clipping
  helpers for smudge carry-buffer state, dab application, and line
  interpolation.
- Removed smudge carry-buffer ownership and smudge pixel math from
  `EditorCanvas`; the canvas now delegates smudge operations and refreshes the
  returned dirty region.
- Remaining Phase 5 work: extract higher-level paint/mask/selection state
  machines for mask/selection paths, then remove the compatibility surface
  after private callers are migrated.

## Architectural Smell Checklist

Use this checklist during future work:

- Does a UI widget directly mutate document state?
- Does a dialog access private fields of `EditorWindow`?
- Does a workflow keep pending async state in `EditorWindow`?
- Does a function accept a long list of loosely related parameters where a typed
  request object would be clearer?
- Does a module mix UI, model loading, inference, and document application?
- Does serialization fallback logic leak into normal runtime behavior?
- Does a pixel operation live inside UI code?
- Does a new feature require editing `EditorWindow` in multiple unrelated
  places?

If the answer is yes, prefer extracting a boundary before adding more behavior
on top.
