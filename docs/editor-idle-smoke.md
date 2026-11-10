# Editor idle and wake verification

## Verified Linux run (2026-11-10)

SDK native build `b2164e838d8e35597bf0`, private Xvfb, Vulkan lavapipe,
`tests/fixtures/windows-d3d11-scene`; 3-second warmup after the owner-thread
startup handshake, then 15-second measurements. Command:

```sh
task smoke:editor-idle -- --xvfb --software-vulkan --matrix --functional --warmup 3 --duration 15
```

| FPS limit | VSync | Idle CPU (% of one core) | With both diagnostic windows open |
| --- | --- | ---: | ---: |
| 60 | On | 0.000 | 0.000 |
| 60 | Off | 0.000 | 0.000 |
| Unlimited | On | 0.067 | 0.000 |
| Unlimited | Off | 0.067 | 0.000 |

All four cases passed file-watcher wake (about 302 ms, including debounce),
worker-log capture drain (about 10 ms at the probe's sampling resolution),
camera transition, PLAY/STOP and SIGINT shutdown with exit code zero.
MCP dispatch-to-owner was 405–504 ms **including CLI startup and transport**.
Zero CPU here means no additional process CPU ticks during the measurement,
not a claim of zero cost for processing events. Main-thread samples showed
blocking waits. The previous Unlimited reproduction consumed about one core.

The run's detailed report is `/tmp/termin-editor-idle-yrnlydpp/report.json`
(temporary evidence; the table and reproduction command above are durable).
`task build` succeeded with `TERMIN_PYTHON_RUNTIME_OFFLINE=1`; the expanded
`task test -- --window-tests` passed under Xvfb/lavapipe (292 C/C++ tests and
the working Python suites). Native tests cover hidden/restored and zero-size
windows; socket-backed tests cover SpaceMouse readiness and disconnect.
Physical GPU/window-manager minimize/restore, a real SpaceMouse, and Windows
verification remain outstanding.

## Reproduction procedure

Build the installed SDK with `task build` before running these checks. The harness
uses installed bindings, copies the small scene fixture into a unique temporary
directory, isolates editor settings/cache, and uses a private MCP session. It
does not attach to or terminate an existing editor. Logs and JSON measurements
remain in the printed artifact directory; the bearer-token session file is
removed after the owned editor process tree is stopped.

```sh
# One Unlimited/VSync-on case, private virtual display, software Vulkan.
task smoke:editor-idle -- --xvfb --software-vulkan

# All four 60/Unlimited × VSync-on/off cases.
task smoke:editor-idle -- --xvfb --software-vulkan --matrix

# Include producer wakes, camera, PLAY/STOP and open diagnostic windows.
task smoke:editor-idle -- --xvfb --software-vulkan --functional

# Repeat on the real desktop/GPU with the normal display environment.
task smoke:editor-idle -- --matrix
```

Each case waits for an owner-thread MCP response, warms up for 15 seconds, then
samples 15 seconds without MCP calls or user input. CPU is the difference in
Linux process user+system CPU time divided by wall time: 100% means one core,
not the whole machine. The default maximum is 5%; `--max-cpu` changes that
environment-specific threshold. Per-interval main-thread `wchan` samples help
diagnose whether the thread waits, but do not replace deterministic scheduler
tests or prove that every background thread is idle. Startup is reported
separately. The report includes the checkout revision and SDK native build ID;
these are separate identities, not a claim that the SDK matches the checkout.

After idle, an MCP script reports its owner-thread timestamp. The measured
dispatch-to-owner and round-trip durations include client startup and transport;
they are not isolated executor queue latency. SIGINT then tests shutdown from
idle, with a timeout. Forced cleanup after failure does not count as passing
shutdown.

`--functional` installs a temporary `.idleprobe` processor in the copied project
and changes a file from the harness process. The processor writes an owner-thread
receipt outside the project; the harness waits for that file without issuing MCP
requests. A separate delayed Python worker emits through the native logging
binding and records when capture has been drained, also before any subsequent
MCP request. Thus an unrelated MCP wake cannot mask missing file/log wakes. This
exercises the native logging path from a Python worker, not a dedicated C++ test
thread, and checks drain rather than the console's visual contents.

It also advances a camera transition, enters and leaves PLAY, and repeats idle
CPU sampling with local Frame Profiler and Framegraph Debugger windows open.
These assertions do not replace checking animation smoothness, simulation
correctness, or physical window minimize/restore behavior. Functional checks run
for each matrix case when both flags are supplied.

`--probe-script /absolute/path/probe.py` runs additional Python against the
isolated editor after the first idle measurement, then repeats warmup and idle.
Assertions in that script fail the case. The script has the ordinary editor MCP
namespace and can exercise camera transitions, PLAY/STOP, diagnostic windows,
or resource updates. Only use the temporary project passed as `project_path`.

The CPU harness alone does **not** close the full #3761 acceptance. Record these
additional checks using deterministic tests or a physical desktop smoke:

- A file changed externally reloads after debounce without mouse/keyboard input.
- Native worker-thread logs appear without unrelated input; a burst exceeding
  one drain batch is fully consumed.
- Camera transitions complete, held navigation remains smooth, and stopping
  movement returns to idle. Test SpaceMouse on a connected device.
- PLAY remains continuous; STOP returns to idle. After a long inactive interval,
  resuming does not cause fixed-update catch-up or a false profiler hitch.
- Secondary windows receive input/repaint. Minimize a dirty window, confirm no
  CPU spin, then restore it and verify the requested image is presented.
- Open profiler/debug windows receive new data but do not generate an endless
  stream of their own empty frames.

For Windows, build and run `task test` with the supported backend configuration
(WPF/D3D11 builds use `--no-sdl --no-vulkan --no-opengl`). Open a copy of the same
fixture using `sdk/bin/termin_editor.exe`; use an isolated settings location and
`TERMIN_EDITOR_MCP_SESSION_FILE` in a fresh temporary directory. Repeat the four
settings combinations, waiting 15 seconds after load and measuring 15–30 seconds
of idle. PowerShell's `(Get-Process -Id $EditorPid).CPU` provides cumulative CPU
seconds: compute `100 * delta_CPU / delta_wall_seconds`. Record PID, SDK build,
backend, window state, CPU, wake checks above, and orderly close. The Linux
`/proc` harness is not a Windows automation implementation; leave that platform
check explicitly outstanding until performed.
