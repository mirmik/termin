# Termin Graphics NuGet product contract

Status: accepted for the initial candidate implementation on 2026-09-04.

## Decision

Termin Graphics is published to .NET consumers as two coupled packages:

- `Termin.Graphics` owns `Termin.Native.dll`, the Windows x64 native DLL
  closure, precompiled D3D11 shader resources, and the transitive MSBuild target
  that copies those resources to consumer output;
- `Termin.Graphics.Wpf` owns `Termin.Wpf.dll` and has an exact-version
  dependency on `Termin.Graphics`.

Both packages use the repository-wide public version from
`build-system/version.toml`. The initial support matrix is deliberately narrow:

- Windows x64;
- .NET 8 with the `net8.0-windows7.0` NuGet asset group;
- D3D11 only;
- the existing `plot-d3d11` C# binding profile.

The public product does not promise Linux, macOS, another RID, SDL, Vulkan,
OpenGL, the broad `full` C# binding profile, or the legacy `netcoreapp3.1` WPF
target. Those can be added only as explicit, separately tested product
variants.

The existing `Termin.Native` managed assembly and namespace are retained. A
package projection does not require a source/API rename.

## Build boundary

NuGet packaging consumes only the installed `sdk-graphics/csharp` projection
created by the canonical root build. It must not pack generated files directly
from `termin-csharp/Termin.Native/runtimes`, `Generated`, or `share`.

The product lock in `build-system/graphics-nuget-lock.json` declares package
IDs, TFM/RID, input paths, minimum native closure, forbidden broad-profile
libraries, required shader artifacts, and release licenses. The product builder
rejects inputs that violate that contract and emits an exact manifest containing
the SHA-256 of every archive and archive member.

## Delivery stages

1. `task package:graphics:nuget` builds the canonical Windows graphics SDK with
   SDL, Vulkan, and OpenGL disabled, then creates an atomic local candidate.
2. A clean PackageReference consumer gate must restore only from that candidate
   and verify managed references, native loading, shader copying, and the WPF
   D3D11 smoke.
3. A guarded publisher may upload only a manifest-complete candidate after an
   explicit version confirmation and must reconcile the remote NuGet package
   content after publication.

Only stage 1 is part of the initial candidate implementation. Consumer runtime
verification and NuGet.org mutation remain separate release gates.
