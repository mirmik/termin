# termin-csharp

`termin-csharp` contains C# bindings/runtime packaging for Termin native
libraries.

Related documents:

- [Examples README](../examples/README.md)
- [Build system](../../docs/build-system.md)
- [2D plot customization](tcplot-customization.md)
- [3D plot customization](tcplot-3d-customization.md)

## Main Areas

- Native bridge project in `Termin.Native/`.
- Test project in `Termin.Test/`.
- CMake build integration in `CMakeLists.txt`.
- Examples in `examples/`.

## Public API

C# project: `Termin.Native`.

The SDK build path is handled by `build-sdk-csharp.sh` / `build-sdk-csharp.ps1`. For WPF plot consumers such as Alliance, use the plot-only D3D11 profile:

```powershell
.\build-sdk-csharp.ps1 --plot-d3d11 --no-sdl --no-vulkan --no-opengl
```

That profile generates only the tcplot C# bridge plus `Termin.Wpf`, copies the minimal native runtime (`termin.dll`, `tcplot.dll`, `termin_base.dll`, `termin_mesh.dll`, `termin_graphics*.dll`), and packages only D3D11 shader artifacts required by plots. The default `full` profile keeps the broader scene/render/component bindings for development.
Generated bindings carry an explicit profile marker. Direct `dotnet build`
uses that marker when no profile is specified and rejects an explicitly
requested profile that does not match the generated SWIG files. Switch
profiles through `build-sdk-csharp.*` (or reconfigure and build the native
CMake target) before invoking managed-only builds.
`Termin.Wpf` is Windows-only and multitargets `netcoreapp3.1` plus `net8.0-windows` through the WindowsDesktop SDK. The Windows SDK drop writes framework-specific managed assemblies under `sdk/csharp/lib/<tfm>/`; flat `sdk/csharp/lib/*.dll` copies are kept for legacy consumers and use the `netcoreapp3.1` WPF assembly. The Linux `build-sdk-csharp.sh` stage builds and packages `Termin.Native` plus Linux native `.so` runtime artifacts, but intentionally does not build `Termin.Wpf`.

WPF scene hosts use the full D3D11-only SDK:

```powershell
.\build-sdk.ps1 --no-sdl --no-vulkan --no-opengl
```

Create a `D3D11OffscreenDisplay` after acquiring `Tgfx2Host`, bind its
non-owning generation handle to `Tgfx2D3D11ImageHost`, render the display
through `RenderingManager`, then call `PresentDisplay()`. The image host
validates the display graphics-domain key before presentation and routes
DPI-scaled pointer, wheel, key, and text input through typed display calls.
Shutdown order is image host, owning display, then `Tgfx2Host`; C# finalizers
do not own native display or surface lifetime. `examples/SceneApp` is the
canonical executable reference and supports `--smoke`.

Plot customization docs are source-of-truth here and are copied into consumer
SDK drops by `VdegNexus/TerminSdk/update-sdk.ps1`.
