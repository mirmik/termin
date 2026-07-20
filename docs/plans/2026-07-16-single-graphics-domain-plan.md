# Single Application Graphics Domain Plan

## Status

Implemented for architecture card #472 on 2026-07-16; ownership API tightened
by #703 on 2026-07-21.

## Decision

Termin supports one installed application graphics domain and one
`IRenderDevice` per process. That device may serve any number of scenes,
renderers, windows, presentation surfaces and swapchains.

The historical OpenGL pull-render requirement for two windows does not imply
two resource domains. A window is a presentation endpoint. OpenGL may switch
one compatible native context between windows, or use contexts in one share
group, while Vulkan and D3D11 use multiple surfaces/swapchains over one device.

Standalone devices remain valid for isolated tests and tools. Creating one
does not install it into process-wide C/Python interop. Simultaneous multi-GPU,
multi-backend rendering and cross-device resource transfer are unsupported.

## Original risk

`GraphicsHost` published an owned device from its constructor.
`Tgfx2Context.from_window` published the same pointer again, and direct
Android/OpenXR paths called an unrestricted global setter. A second owner could
therefore replace the active device, while destruction could clear a device it
did not own.

Tgfx2 handles are device-local `uint32_t` values. Different backends allocate
the same IDs from independent pools, so silently replacing the global device
can resolve an otherwise valid handle against an unrelated resource.

## Target ownership contract

The C interop boundary exposes an owner-checked registration:

- `tgfx2_interop_claim_device(device, owner)` installs the first device;
- a repeated claim by the same owner/device is idempotent;
- every conflicting device or owner is rejected and logged;
- `tgfx2_interop_release_device(device, owner)` succeeds only for the owner;
- `tgfx2_interop_get_device()` remains an observing accessor.

`tgfx::GraphicsHost` is the sole owning application-domain object. Named
factories distinguish application hosts, which own the interop claim, from
isolated test/tool hosts, which never publish globally. Borrowed-device and
borrowed-context host constructors do not exist.

## Migration

1. Add owner-checked claim/release to the C interop API and remove the
   unrestricted setter.
2. Make `GraphicsHost` owning-only and expose named application/isolated
   factories rather than public claim/release toggles.
3. Claim from application composition roots:
   `WindowedGraphicsSession`, standalone `RenderEngine`, `tcplot::GpuHost`, Android
   smoke and OpenXR smoke.
4. Make `Tgfx2Context.from_runtime` and `from_context` validate that their host
   device is already installed instead of mutating global state.
5. Remove primary/secondary window construction. Every `BackendWindow` is an
   equal per-window presentation target created by one session.
6. Add focused tests for conflicting claim, mismatched release and idempotent
   owner operations.

## Handle policy

Handles remain compact and device-local. They are valid only with the installed
application device that created them. A `domain + slot + generation` ABI is not
introduced because Termin has no supported cross-device resource workflow.

Generation checking for recycled slots inside one device is a separate future
hardening concern and does not justify simultaneous application domains.

## Verification

- focused tgfx2 interop ownership test;
- existing multi-window/shared-device tests;
- `./build-sdk.sh --no-wheels`;
- `./run-tests.sh`;
- packaged editor/runtime import smoke.

## Completion criteria

- no constructor or observer wrapper silently changes the active device;
- a second primary application host fails without replacing the first device;
- non-owner teardown cannot clear the installed device;
- headless ownership and host-device borrowing are explicit;
- multi-window remains one device with multiple presentation endpoints;
- all repository tests pass.

## Implementation result

- The unrestricted global setter was replaced with owner-checked claim and
  release operations. Conflicts are rejected and logged without changing the
  active device.
- `GraphicsHost` is owning-only. Application and isolated factories encode
  interop policy; Python renderer contexts borrow the typed host with binding
  keep-alive instead of passing raw device/context pointers.
- `BackendWindow` exposes no device/context API. `BackendWindowSystem` owns
  only platform state, while `WindowedGraphicsSession` provides the standard
  composition and teardown order for any number of equal windows.
- `RenderEngine` receives the exact host explicitly and no longer constructs a
  second cache/context around the globally installed device.
- Android, OpenXR, `tcplot::GpuHost` and standalone `RenderEngine` paths now
  have explicit ownership and exact-owner teardown.
- Device locality is documented at the handle definition, and native tests
  cover idempotent claim, conflicting owners/devices and mismatched release.

## Verification result

- `./build-sdk.sh --no-wheels` — passed;
- `./setup-sdk-python-env.sh` — passed;
- `./run-tests.sh` — passed, including all 74 native tests and Python suites;
- `git diff --check` — passed.

A live editor-window smoke under Xvfb reached the editor main loop and shut down
after the requested frame count, confirming application-device initialization.
The process returned failure because the local OpenGL shader cache lacked its
generated Slang sources; that pre-existing shader-runtime issue is independent
of graphics-domain ownership and is tracked as board card #495. Interactive
multi-window behavior remains a platform smoke check.
