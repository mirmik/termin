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

The `windows7.0` TFM suffix is an API-version marker, not a promise to run on
Windows 7. Consumers need a Windows release supported by .NET 8 and the latest
x64 Microsoft Visual C++ v14 Redistributable because the native libraries use
the dynamic MSVC runtime.

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

The plot runtime closure is derived from the native binaries rather than only
the direct C# binding targets. It therefore includes the inspect, materials,
render-core, and graphics-binding-policy libraries pulled in transitively by
the retained chart stack. These are part of the focused product; engine,
scene, display, render-pipeline, and component libraries remain forbidden.

## Delivery stages

1. `task package:graphics:nuget` builds the canonical Windows graphics SDK with
   SDL, Vulkan, and OpenGL disabled, then creates an atomic local candidate.
2. `task test:graphics:nuget` rebuilds that candidate, copies it into an
   external temporary feed, and verifies managed references, native loading,
   shader copying, and a real WPF D3D11 retained-chart frame without access to
   the checkout or staged SDK at runtime. The gate preserves its report, logs,
   and exact candidate manifest under `build/graphics-nuget-consumer-gate`.
3. `task publish:graphics:nuget` validates the candidate and its passed consumer
   evidence, checks both remote versions, and prints the exact dry-run plan.
   `--upload --confirm-version VERSION` enables the irreversible base-then-WPF
   upload. Publication is bound to the exact package hashes in the passed gate;
   it never rebuilds or substitutes a different candidate.

NuGet.org mutation remains a separate release gate after stages 1 and 2 pass.
The publisher preflights both remote versions before the first mutation. It
downloads every existing or newly visible package and compares every original
archive member with the gated manifest; only NuGet's `.signature.p7s`
repository-signature member may be added. This makes a rerun safe after a
partial base-package publication without relying on `skip duplicate`.

## Publication operations

Run the dry plan on the same machine and workspace that retain the passed
candidate and `build/graphics-nuget-consumer-gate` evidence:

```powershell
task publish:graphics:nuget
```

For upload, create a short-lived NuGet.org API key scoped to push new versions
of only `Termin.Graphics` and `Termin.Graphics.Wpf`. The release owner supplies
it through the process environment; it is never accepted as a command-line
argument or written to evidence:

```powershell
$env:NUGET_API_KEY = '<scoped secret>'
task publish:graphics:nuget -- --upload --confirm-version 0.5.2
Remove-Item Env:NUGET_API_KEY
```

Keep the key in the release owner's secret store. Do not commit it, paste it
into task arguments, or expose it to pull-request workflows. A CI migration
should prefer NuGet.org Trusted Publishing; if a static key is temporarily
needed, place it in a protected release environment available only to trusted
tag/ref workflows.

Uploads are non-transactional. If the base package succeeds and the WPF upload
does not, retain the candidate and evidence unchanged and rerun the same
command. The publisher proves the existing base content and continues with WPF.
Any remote member mismatch stops publication for manual reconciliation.

After both pushes are visible, restore both packages from NuGet.org in a clean
external consumer and repeat the WPF/D3D11 smoke before closing the release.
