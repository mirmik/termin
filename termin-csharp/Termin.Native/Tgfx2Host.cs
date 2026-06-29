using System;
using System.IO;

namespace Termin.Native
{
    /// <summary>
    /// Process-wide singleton that owns the one tcplot/tgfx2 GPU runtime while
    /// at least one WPF plot host is alive.
    /// </summary>
    public static class Tgfx2Host
    {
        private static GpuHost? _host;
        private static BackendType? _backend;
        private static int _leaseCount;
        private static readonly object _lock = new();

        public static bool IsCreated => _host != null;

        public static GpuHost Instance =>
            _host ?? throw new InvalidOperationException(
                "Tgfx2Host.Acquire() was not called - " +
                "no WPF plot host has initialised yet.");

        public static GpuHost Acquire(string ttfPath, BackendType backend = BackendType.D3D11)
        {
            lock (_lock)
            {
                if (_host != null)
                {
                    if (_backend != backend)
                    {
                        throw new InvalidOperationException(
                            $"Tgfx2Host already owns a {_backend} runtime; " +
                            $"cannot acquire a {backend} runtime in the same process.");
                    }

                    _leaseCount++;
                    Trace($"acquire existing backend={backend} leases={_leaseCount}");
                    return _host;
                }

                NativeRuntimeSearchPath.Configure();
                ShaderRuntime.ConfigureFromAssemblyDirectory();

                if (!File.Exists(ttfPath))
                {
                    throw new FileNotFoundException(
                        $"Tgfx2Host: font file not found: {ttfPath}");
                }

                Trace($"creating host backend={backend} font={ttfPath}");
                _host = new GpuHost(ttfPath, backend);
                _backend = backend;
                _leaseCount++;
                Trace($"acquire new backend={backend} leases={_leaseCount}");
                return _host;
            }
        }

        public static void Release()
        {
            lock (_lock)
            {
                if (_leaseCount <= 0)
                {
                    Trace("release ignored leases=0");
                    return;
                }

                _leaseCount--;
                Trace($"release leases={_leaseCount}");
                if (_leaseCount == 0)
                {
                    Trace("disposing host");
                    _host?.Dispose();
                    _host = null;
                    _backend = null;
                }
            }
        }

        private static bool TraceEnabled =>
            !string.IsNullOrEmpty(Environment.GetEnvironmentVariable("TERMIN_WPF_PLOT_TRACE"));

        private static void Trace(string message)
        {
            if (!TraceEnabled)
            {
                return;
            }

            Console.Error.WriteLine($"[Termin.Native.Tgfx2Host] {message}");
        }
    }
}