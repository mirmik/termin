# Termin.Engine NuGet product

`Termin.Engine` provides the full `Termin.Native` C# scene/rendering profile
to .NET 8 and later. One package includes `win-x64` with D3D11 and
`linux-x64` with Vulkan. The published `Termin.Graphics` package remains
the `plot-d3d11` product. A consumer graph containing both products fails
at MSBuild package resolution with `TERMIN001`, including transitive
references.

## Build the two native inputs

On each platform use a separate, fresh `BUILD_DIR` and `SDK_PREFIX` for
the native-only SDK. Set `TERMIN_SLANGC` to the pinned toolchain's `slangc`
(or put it on the build host's PATH).

| Platform | Native build |
| --- | --- |
| Linux | `task build:cpp -- --no-sdl --no-opengl --vulkan --shader-artifacts=vulkan` |
| Windows | `task build:cpp -- --no-sdl --no-vulkan --no-opengl` |

With `SDK_PREFIX` still set to that installation, build and stage the bindings.

```sh
task build:csharp -- --profile=full --no-opengl
task stage:engine:nuget
```

The Linux staging host needs `readelf` and `patchelf`. Staging resolves
SDK-internal dependencies and records the external system dependencies.
ELF binaries use `$ORIGIN` in the package. The primary SDK files and
versioned names required by ELF consumers are included. Installed SDK
files are untouched by relocation.

Copy both stage archives to `build/engine-nuget/` on the packaging host.
They must correspond to the same source revision. Compose the package with
`task package:engine:nuget`. The composer validates staged hashes,
combines the built-in shader catalogs and selects the redistributable Droid
Sans from the pinned third-party source. It puts the compile-time
reference under `ref/net8.0` and each platform's implementation under
`runtimes/<rid>/lib/net8.0`. At runtime the .NET SDK selects the managed
assembly and native files for the target RID. The transitive MSBuild
target copies the shader files and font to `share/termin`.

## Gate and release

Run `task test:engine:nuget` on both platforms with the exact same
`.nupkg`. The gate creates an external Avalonia project, restores it via
`PackageReference` into an empty package cache, builds a framework-dependent
RID publish, checks each copied Termin file and runs the pixel smoke from
an unrelated directory. On Linux a headless builder can use
`xvfb-run -a task test:engine:nuget`. Use `--build-only` and
`--run-only` after `--` to split Windows SSH build and desktop execution.
An offline build can add `--dependency-source <feed>` for Avalonia and its
dependencies.

Copy the Windows `build/engine-nuget/gate-win-x64/report.json` to the
release host. The release command checks both pass reports against the
SHA-256 of the exact package. The default is a dry run against NuGet.org.
With a scoped key for the first package push available in the process
environment, upload and reconcile the downloaded package with the
verified artifact.

```sh
task publish:engine:nuget
task publish:engine:nuget -- --upload
```

The initial Linux build was verified on Ubuntu 26.04 with the Vulkan
llvmpipe driver. It requires glibc 2.43, libstdc++ with GLIBCXX_3.4.32,
the Vulkan loader and a driver, and `libshaderc.so.1`. Windows was verified
on a Windows x64 VM with D3D11 and the VC++ x64 runtime. Both the reference
Avalonia sample and the external AntennaBench GUI were tested on both
platforms.
