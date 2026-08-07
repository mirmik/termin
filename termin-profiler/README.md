# Termin Profiler

`termin_profiler` is the standalone native GUI for Termin's authenticated
remote frame profiler. It does not start the editor and does not require a
project to be open.

The transport intentionally connects only to `127.0.0.1`. Route a remote
Android or Linux target to a local port first. For a Quest NativeActivity:

```bash
scripts/android-profiler-forward --serial QUEST_SERIAL \
  --package org.example.openxr --activity android.app.NativeActivity

sdk/bin/termin_profiler
```

Enter the printed port and per-launch token, press **Connect**, then use the
toolbar to start or pause capture and to enable detailed section profiling.
The token is neither persisted nor written to logs.

For deterministic window smoke tests the executable accepts `--render-count N` (or
the `TERMIN_PROFILER_RENDER_COUNT` environment variable) and
closes after rendering `N` frames.
