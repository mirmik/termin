using System;
using System.IO;

namespace Termin.Native
{
    /// <summary>
    /// Process-wide singleton that owns the one tcplot/tgfx2 GPU
    /// runtime (IRenderDevice + PipelineCache + RenderContext2 +
    /// FontAtlas). Every PlotView* in the application borrows it.
    ///
    /// Rationale: tcplot used to create its own OpenGLRenderDevice
    /// inside each PlotView, which caused GL resource collisions
    /// when a single window hosted two GLWpfControl instances
    /// (shared GL context between them). One device per process
    /// is the invariant that keeps those collisions from happening.
    ///
    /// Lifecycle: lazily created from the first WPF host that
    /// reaches native-init (where a live GL context is available
    /// courtesy of GLWpfControl.Start()). Kept alive for the
    /// process lifetime — no explicit tear-down since the GL
    /// context dies with the process anyway.
    /// </summary>
    public static class Tgfx2Host
    {
        private static GpuHost? _host;
        private static readonly object _lock = new();

        public static bool IsCreated => _host != null;

        public static GpuHost Instance =>
            _host ?? throw new InvalidOperationException(
                "Tgfx2Host.EnsureCreated() was not called — " +
                "no GL-hosting control has initialised yet.");

        public static void EnsureCreated(string ttfPath)
        {
            if (_host != null) return;
            lock (_lock)
            {
                if (_host != null) return;
                if (!File.Exists(ttfPath))
                {
                    throw new FileNotFoundException(
                        $"Tgfx2Host: font file not found: {ttfPath}");
                }
                _host = new GpuHost(ttfPath);
            }
        }
    }
}
