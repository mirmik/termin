# Termin Graphics for .NET

Termin Graphics provides the focused C# bindings and native runtime used by
Termin's retained 2D/3D charts on Windows.

The initial public product supports .NET 8 applications on Windows x64 and the
D3D11 backend. It is built from Termin's `plot-d3d11` profile and does not
include the editor, Python runtime, SDL, Vulkan, or legacy OpenGL.

The native binaries use the dynamic Microsoft C++ runtime. Install the latest
[Microsoft Visual C++ v14 Redistributable for x64](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist?view=msvc-170)
on the target machine. The `net8.0-windows7.0` asset name states the Windows API
contract; run it only on a Windows release supported by .NET 8.

Use the base runtime directly for non-WPF hosts:

```xml
<PackageReference Include="Termin.Graphics" Version="{{TERMIN_VERSION}}" />
```

WPF applications should reference the adapter package, which brings the exact
same version of the base runtime transitively:

```xml
<PackageReference Include="Termin.Graphics.Wpf" Version="{{TERMIN_VERSION}}" />
```

The package supplies the managed assemblies, the `win-x64` native dependency
closure, and the precompiled D3D11 shader resources. Applications do not need a
Termin SDK checkout at runtime.

The managed API currently keeps the established `Termin.Native` namespace and
assembly name. Package naming describes the public product and does not imply
an assembly or namespace rename.
