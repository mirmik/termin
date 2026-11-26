# Termin.Engine

Termin's full C# scene and rendering runtime for .NET 8 and later.
The NuGet package includes Linux x64 / Vulkan and Windows x64 / D3D11
native libraries, shaders and font. The Linux Vulkan loader and a Vulkan
driver, or the Windows D3D11 runtime and Microsoft Visual C++ 2015–2022
x64 Redistributable, are installed by the host system.

Reference `Termin.Engine` in your app and publish for `win-x64` or
`linux-x64`. Use the exact same package version at build and deployment.
The app's build copies the selected native runtime and the shader files.
Linux binaries require glibc 2.43, libstdc++ with GLIBCXX_3.4.32, and
`libshaderc.so.1`.

```xml
<PackageReference Include="Termin.Engine" Version="[0.5.5]" />
```

Initialize Termin at app scope and acquire a `Tgfx2Host` for the backend.
Build a `Scene` from entities, rendering components and a camera. Render to
an `OffscreenDisplay` and use `ReadBgra` to fill the bitmap buffer on the
render thread. The result is opaque sRGB BGRA8888 in top-to-bottom row order.

`Termin.Engine` and `Termin.Graphics` both supply a `Termin.Native` assembly.
Choose one profile per application, including transitive dependencies.

[Avalonia example](https://github.com/mirmik/termin/tree/master/termin-csharp/examples/AvaloniaPositioner)
