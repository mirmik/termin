# Android Emulator Vulkan Smoke

The Android Render Showcase has an `android-emulator-debug` profile for the
`x86_64` ABI. The supported software Vulkan configuration is the Android
Emulator's SwiftShader backend:

```bash
task build:android -- --abi x86_64 --ndk "$ANDROID_HOME/ndk/27.2.12479018"
./sdk/bin/termin_builder build android-emulator-debug \
    --project test-projects/android-render-showcase

"$ANDROID_HOME/emulator/emulator" \
    -avd Pixel_7_API_36 \
    -no-window -no-snapshot -no-boot-anim -no-audio \
    -gpu swiftshader_indirect
```

Install `test-projects/android-render-showcase/dist/android-emulator/apk/`
`AndroidRenderShowcase-debug.apk` and launch
`org.termin.testprojects.androidshowcase/org.termin.android.TerminActivity`.
A valid smoke reaches at least frame 120 and shows both the 3D scene and the
native HUD. `-gpu lavapipe` remains useful as an independent software-driver
fallback when diagnosing emulator-host problems.

## Shader artifact compatibility

Android packages use offline Vulkan SPIR-V artifacts. Slang emits `OpSource`
debug metadata with its `SourceLanguage` enumerant. Emulator 37.1.11's older
SwiftShader parser rejects the newer Slang enumerant before compiling an
otherwise valid module. `termin_shaderc` therefore removes `OpSource` from
Slang Vulkan output. The instruction is non-semantic: executable SPIR-V,
descriptor decorations, reflection sidecars, and normal Vulkan validation are
left intact. Malformed instruction streams still fail the build.

The shader compiler regression suite feeds an `OpSource Slang` module through
the real postprocess and verifies that the metadata is absent from the emitted
artifact while descriptor processing continues to work.
