# Termin OpenXR Android Smoke App

This Gradle project builds the experimental Quest/OpenXR smoke APK separately
from `termin-android`.

Build from the repository root:

```bash
./build-sdk-android.sh --abi arm64-v8a --platform android-26
./build-quest-openxr-apk.sh --gradle /path/to/gradle-8.x/bin/gradle
```

Install and launch on a connected headset:

```bash
./build-quest-openxr-apk.sh --gradle /path/to/gradle-8.x/bin/gradle --launch
```

The smoke app does not use the Termin render engine yet. It starts an OpenXR
session with OpenGL ES, creates a stereo color swapchain, clears each eye to a
cycling color, and submits the projection layer through `xrEndFrame`.
