# Transactional Play/Stop Plan

## Status

Implemented on 2026-07-16 for architecture card #477.

## Problem

`GameModeModel` currently performs Play and Stop as an unchecked sequence of
scene copy, editor attachment, render attachment, mode changes and scene
destruction. The model publishes `_game_scene_name` before the transition has
committed, ignores explicit `False` results from attachment operations, and
closes the game scene on Stop before the editor and renderer have returned to
the editor scene.

A failure in the middle can therefore leave these independently managed facts
in disagreement:

- which scene the editor tools and editor viewport use;
- which scenes are attached to `RenderingManager`;
- which scene modes are `STOP`, `INACTIVE` or `PLAY`;
- whether the UI reports Editing or Playing;
- which object owns and eventually closes the copied game scene.

Malformed scene-file loading is related but out of scope. It is tracked by
card #476. This plan only covers the already-created editor/game scene pair and
the Play/Stop transition between them.

## Architectural constraints

`RenderingManager` deliberately supports multiple attached scenes. Neither
`RenderSceneSession` nor the editor layer may reduce that capability to one
globally active scene.

The one-scene invariant belongs only to the editor's primary scene role:

```text
RenderingManager attached scenes = {primary, preview, tools, other...}
                                  ^
                                  |
                     PrimaryRenderSceneBinding
```

`PrimaryRenderSceneBinding` owns and changes only the primary attachment that
it was constructed with. It never enumerates, reconciles or detaches unrelated
scenes. Other callers retain the ordinary `RenderSceneSession.attach()` and
`detach()` multi-scene API.

The binding is scoped to one Play session rather than being a global editor
service. Normal scene-file operations may replace the editor scene before Play
begins. On Start, the binding claims the current editor scene. On successful
Stop it returns to that scene and is discarded.

## Target model

### Primary render binding

The binding exposes:

- `scene_name`: the primary scene currently owned by the binding;
- `sync_current()`: persist live render configuration into that scene;
- `rebind(new_scene_name)`: atomically change only this binding's attachment.

`rebind` attaches the new scene before detaching the old scene. If either step
fails, it restores the old attachment and removes the new one. Explicit
`False` results are failures; exceptions are logged and propagated. A rollback
failure is logged separately and the game-mode coordinator must not destroy a
scene that may still be referenced.

Temporary coexistence of the old and new primary scenes is intentional and is
compatible with the manager's multi-scene contract. Attachments unrelated to
the binding are unchanged.

### Committed game session

`GameModeModel` stores one optional committed game-session record containing:

- editor scene name;
- copied game scene name and object;
- primary render binding;
- saved scene-tree expansion state.

`is_game_mode` derives only from the presence of this committed record. A
candidate remains local while Start is preparing and committing, so UI code
cannot observe a half-created Play state. During Stop the committed record
remains published until the editor scene, render binding and scene modes have
all been restored and the game scene has been closed.

### Transition order

Start prepare:

1. Reject reentrant transitions and missing editor state.
2. Prepare changed project code.
3. Capture editor UI/camera state.
4. Synchronize the current primary render configuration.
5. Copy the editor scene into a candidate game scene.

Start commit:

1. Rebind the primary render attachment from editor to game.
2. Switch the editor attachment from editor to game.
3. Set editor mode to `INACTIVE` and game mode to `PLAY`.
4. Store the committed game-session record.
5. Emit state and mode-entered signals.

Failure rolls completed steps back in reverse order, restores the original
editor mode, and closes the candidate only after no attachment can reference
it.

Stop commit:

1. Rebind the primary render attachment from game to editor.
2. Switch the editor attachment from game to editor.
3. Set both scenes to `STOP`.
4. Close the now-unreferenced game scene.
5. Clear the committed game-session record.
6. Emit state and mode-entered signals.

Failure before game-scene destruction restores the game editor/render
attachments and the original modes. The committed session remains Playing.

## Error contract

Attachment commands have a command-style contract: reaching the requested
postcondition is success; an explicit `False` or exception is failure. A
normal same-scene operation is filtered by the binding before invoking the
underlying service. Every transition failure and every rollback failure is
logged with its stage.

There is no connector-less Play fallback. Frontends create Game Mode only when
both editor and render services are available.

## Implementation slices

1. Add and unit-test `PrimaryRenderSceneBinding` independently of either UI
   toolkit, including unrelated attached scenes and injected attach/detach
   failures.
2. Replace `GameModeModel`'s loose render connector with a binding factory and
   a committed game-session record.
3. Change Start/Stop to commit-only publication with explicit rollback and
   transition logging.
4. Wire native and tcgui frontends through the same binding.
5. Add failure-injection tests for every Start and Stop attachment boundary,
   plus repeated successful cycles.

## Verification

- focused `PrimaryRenderSceneBinding`, connector and `GameModeModel` tests;
- complete `termin-app` Python tests through the central `./run-tests.sh`
  entry point when focused tests pass;
- `./build-sdk.sh --no-wheels` only if native bindings or bundled runtime
  inputs changed. This implementation is expected to be Python-only, so an
  existing SDK is sufficient unless tests reveal otherwise.

## Completion criteria

- failed Start leaves the original editor scene, primary render attachment,
  modes and published UI state unchanged;
- failed Stop leaves the committed game session playable and attached;
- successful Stop closes the copied game scene exactly once;
- unrelated scenes remain attached across Start, Stop and rollback;
- Playing/Stopped signals are emitted only after commit;
- both editor frontends use the same transactional core.

## Implementation outcome

- `PrimaryRenderSceneBinding` owns one scoped primary attachment and performs
  add-before-remove rebinding with compensating rollback. It never enumerates
  or changes unrelated `RenderingManager` scenes.
- `GameModeModel` now owns an optional committed game-session record. Candidate
  scene state remains local during Start, and the record remains published
  during Stop until restoration and game-scene destruction complete.
- Start and Stop restore editor attachment, primary render attachment and
  scene modes on injected failures. Explicit frontend `False` results become
  transition failures; native session adapters normalize successful no-op
  returns to command success.
- Native and tcgui frontends construct the same scoped binding through a
  factory, while other editor features retain direct multi-scene
  `RenderSceneSession.attach()` and `detach()` access.

## Verification record

- focused editor transition and session selection: 22 passed;
- `./build-sdk.sh --no-wheels`: passed;
- `./setup-sdk-python-env.sh`: refreshed the SDK-backed checkout overlay;
- `./run-tests.sh`: passed, including 74 C/C++ tests, all working Python
  suites and Python lint. Window/editor-process smoke remains outside the
  default working set.
