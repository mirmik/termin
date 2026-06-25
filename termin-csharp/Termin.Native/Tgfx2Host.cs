using System;
using System.IO;

namespace Termin.Native
{
    /// <summary>
    /// Process-wide singleton that owns the one tcplot/tgfx2 GPU
    /// runtime while at least one GL-hosting control is alive.
    /// </summary>
    public static class Tgfx2Host
    {
        private static GpuHost? _host;
        private static int _leaseCount;
        private static readonly object _lock = new();

        public static bool IsCreated => _host != null;

        public static GpuHost Instance =>
            _host ?? throw new InvalidOperationException(
                "Tgfx2Host.Acquire() was not called - " +
                "no GL-hosting control has initialised yet.");

        public static GpuHost Acquire(string ttfPath)
        {
            lock (_lock)
            {
                if (_host == null)
                {
                    ShaderRuntime.ConfigureFromAssemblyDirectory();

                    if (!File.Exists(ttfPath))
                    {
                        throw new FileNotFoundException(
                            $"Tgfx2Host: font file not found: {ttfPath}");
                    }
                    _host = new GpuHost(ttfPath, BackendType.OpenGL);
                }

                _leaseCount++;
                return _host;
            }
        }

        public static void Release()
        {
            lock (_lock)
            {
                if (_leaseCount <= 0)
                {
                    return;
                }

                _leaseCount--;
                if (_leaseCount == 0)
                {
                    _host?.Dispose();
                    _host = null;
                }
            }
        }
    }
}
