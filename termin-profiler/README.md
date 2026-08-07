# Termin Profiler

`termin_profiler` is the standalone native GUI for Termin's authenticated
remote frame profiler. It does not start the editor and does not require a
project to be open.

For Android and Quest, the normal workflow is entirely inside the GUI:

1. Connect the headset with USB debugging enabled.
2. Press **Refresh Devices** and select the ready device.
3. Enter the application id and activity class. The Quest OpenXR defaults are
   `org.termin.openxr` and `android.app.NativeActivity`.
4. Press **Connect Quest**.

The profiler generates a per-launch token, allocates its own local ADB port,
force-stops and explicitly starts the selected application with diagnostics,
then connects automatically. **Disconnect Quest** removes only the ADB route
owned by this profiler instance. The token is never displayed, persisted, or
written to logs.

The **Manual (advanced)** row remains available for SSH forwards, automation,
and an already-running loopback target. The transport itself intentionally
connects only to `127.0.0.1`.

After connecting, use the toolbar to start or pause capture and to enable
detailed section profiling.

For deterministic window smoke tests the executable accepts `--render-count N` (or
the `TERMIN_PROFILER_RENDER_COUNT` environment variable) and
closes after rendering `N` frames.
