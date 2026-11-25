using System;
using System.Numerics;
using System.Runtime.InteropServices;
using Termin.Native;

namespace AvaloniaPositioner;

internal sealed class PositionerScene : IDisposable
{
    private Scene? _scene;
    private EngineCore? _engine;
    private RenderingManager? _renderer;
    private RenderEngine? _renderEngine;
    private RenderPipeline? _pipeline;
    private TcDisplayHandle _display = TcDisplayHandle.Invalid;
    private TcViewportHandle _viewport = TcViewportHandle.Invalid;
    private TcRenderTargetHandle _target = TcRenderTargetHandle.Invalid;
    private tc_display_handle? _displayRef;
    private Entity _turntable;
    private Entity _carriage;
    private Entity _camera;
    private bool _runtimeInitialized;
    private bool _hostAcquired;
    private bool _disposed;
    private float[] _linear = Array.Empty<float>();
    private int _width;
    private int _height;

    public PositionerScene(int width, int height)
    {
        try
        {
            string font = Environment.GetEnvironmentVariable("TERMIN_POSITIONER_FONT")
                ?? throw new InvalidOperationException("Set TERMIN_POSITIONER_FONT to the installed SDK font.");
            var backend = OperatingSystem.IsWindows() ? BackendType.D3D11 : BackendType.Vulkan;
            TerminCore.InitFull();
            _runtimeInitialized = true;
            var host = Tgfx2Host.Acquire(font, backend);
            _hostAcquired = true;
            _engine = new EngineCore();
            _renderer = _engine.rendering_manager();
            _renderEngine = new RenderEngine();
            _renderEngine.set_gpu_host(host);
            _renderer.set_render_engine(_renderEngine);

            _scene = new Scene("Azimuth and lift");
            BuildPositioner(_scene.Entities);
            _camera = _scene.Entities.CreateEntity("Camera");
            var cameraComponent = _camera.AddComponentByName("CameraComponent");
            if (!cameraComponent.IsValid)
                throw new InvalidOperationException("Termin could not create the camera component.");

            _pipeline = new RenderPipeline("Positioner");
            using var colorBuffer = new ResourceSpec
            {
                resource = "empty",
                resource_type = "fbo",
                scale = 1.0f,
                samples = 1,
            };
            colorBuffer.set_format("render_target");
            _pipeline.add_spec(colorBuffer);
            using var colorPass = new PositionerColorPass();
            colorPass.AttachTo(_pipeline);
            _pipeline.set_color_export("color", ColorContent.DisplayLinear);

            _display = CreateOffscreenDisplay(width, height);
            _viewport = TerminCore.ViewportNew("Positioner", _scene.Handle);
            _target = TerminCore.RenderTargetNew("Positioner");
            if (!_display.IsValid || !_viewport.IsValid || !_target.IsValid)
                throw new InvalidOperationException("Termin could not create the offscreen viewport.");
            TerminCore.ViewportSetRect(_viewport, 0, 0, 1, 1);
            TerminCore.RenderTargetSetScene(_target, _scene.Handle);
            using var pipelineHandle = _pipeline.handle();
            TerminCore.RenderTargetSetPipeline(_target, pipelineHandle);
            TerminCore.RenderTargetSetCamera(_target, cameraComponent.Ptr);
            TerminCore.RenderTargetSetDynamicResolution(_target, true);
            TerminCore.RenderTargetSetEnabled(_target, true);
            TerminCore.ViewportSetRenderTarget(_viewport, _target);
            TerminCore.DisplayAddViewport(_display, _viewport);
            _displayRef = SwigHelpers.ToSwigDisplayHandle(_display);
            _renderer.add_display(_displayRef);

            SetSize(width, height);
            SetPose(0, 0);
            SetCamera(-45, 27, 5.8);
            Console.WriteLine($"AVALONIA_POSITIONER_BACKEND {backend}");
        }
        catch
        {
            Dispose();
            throw;
        }
    }

    public Vector3 CarriageWorldPosition => _carriage.WorldMatrix.Translation;

    public void SetPose(double azimuthDegrees, double heightMeters)
    {
        _turntable.Rotation = Quaternion.CreateFromAxisAngle(Vector3.UnitZ, Radians(azimuthDegrees));
        _carriage.Position = new Vector3(0.85f, 0, 0.6f + (float)heightMeters);
        _scene!.Entities.UpdateTransforms();
    }

    public void SetCamera(double orbitDegrees, double elevationDegrees, double distanceMeters)
    {
        var yaw = Quaternion.CreateFromAxisAngle(Vector3.UnitZ, Radians(orbitDegrees));
        var pitch = Quaternion.CreateFromAxisAngle(Vector3.UnitX, -Radians(elevationDegrees));
        _camera.Rotation = yaw * pitch;
        var forward = Vector3.Transform(Vector3.UnitY, _camera.Rotation);
        _camera.Position = new Vector3(0, 0, 1.08f) - forward * (float)distanceMeters;
    }

    public void Resize(int width, int height)
    {
        if (width == _width && height == _height)
            return;
        if (!TerminCore.DisplayResize(_display, width, height))
            throw new InvalidOperationException($"Termin could not resize the display to {width}x{height}.");
        SetSize(width, height);
    }

    private void SetSize(int width, int height)
    {
        _linear = new float[checked(width * height * 4)];
        _width = width;
        _height = height;
    }

    public unsafe void Render(IntPtr address, int rowBytes)
    {
        _scene!.Entities.UpdateTransforms();
        _renderer!.render_display(_displayRef);
        fixed (float* linear = _linear)
        {
            nuint capacity = checked((nuint)rowBytes * (nuint)_height);
            if (ReadBgra(_display, _width, _height, linear, (nuint)_linear.Length, address,
                capacity, (nuint)rowBytes) == 0)
                throw new InvalidOperationException("Termin could not read the rendered frame.");
        }
    }

    private void BuildPositioner(EntityPool entities)
    {
        var shader = TerminCore.Tgfx2RegisterBuiltinShader("termin-runtime-default-color");
        var material = TerminCore.MaterialCreate(null, "Positioner vertex colors");
        var materialPtr = TerminCore.MaterialGet(material);
        if (shader.Index == uint.MaxValue || materialPtr == IntPtr.Zero ||
            TerminCore.MaterialAddPhase(materialPtr, shader, "opaque", 0) == IntPtr.Zero)
            throw new InvalidOperationException("Termin could not create the positioner material.");

        var steel = CreateBoxMesh("Steel", new Vector3(0.17f, 0.20f, 0.22f));
        var amber = CreateBoxMesh("Amber", new Vector3(0.92f, 0.33f, 0.025f));
        var blue = CreateBoxMesh("Blue", new Vector3(0.025f, 0.44f, 0.85f));

        AddBox("Base", default, new Vector3(0, 0, -0.08f), new Vector3(2.75f, 2.15f, 0.16f), steel);
        _turntable = entities.CreateEntity("Azimuth");
        AddBox("Platform", _turntable, new Vector3(0, 0, 0.12f), new Vector3(2.25f, 1.25f, 0.24f), amber);
        AddBox("Left rail", _turntable, new Vector3(0.58f, -0.38f, 1.27f), new Vector3(0.14f, 0.14f, 2.1f), steel);
        AddBox("Right rail", _turntable, new Vector3(0.58f, 0.38f, 1.27f), new Vector3(0.14f, 0.14f, 2.1f), steel);
        AddBox("Rail brace", _turntable, new Vector3(0.58f, 0, 2.32f), new Vector3(0.19f, 0.9f, 0.14f), steel);

        _carriage = entities.CreateEntity("Z lift");
        _carriage.SetParent(_turntable);
        AddBox("Carriage", _carriage, Vector3.Zero, new Vector3(0.52f, 0.89f, 0.33f), blue);
        AddBox("Mount", _carriage, new Vector3(0.3f, 0, 0), new Vector3(0.3f, 0.47f, 0.15f), blue);

        void AddBox(string name, Entity parent, Vector3 position, Vector3 scale, TcMeshHandle mesh)
        {
            var box = entities.CreateEntity(name);
            if (parent.IsValid)
                box.SetParent(parent);
            box.Position = position;
            box.Scale = scale;
            var geometry = box.AddComponentByName("MeshComponent");
            var renderer = box.AddComponentByName("MeshRenderer");
            if (!geometry.IsValid || !renderer.IsValid)
                throw new InvalidOperationException($"Termin could not create mesh components for {name}.");
            geometry.SetField("mesh", mesh);
            renderer.SetField("material", material);
        }
    }

    private static unsafe TcMeshHandle CreateBoxMesh(string name, Vector3 color)
    {
        const int floatsPerVertex = 16;
        float[] vertices = new float[24 * floatsPerVertex];
        uint[] indices = new uint[36];
        // The two in-plane vectors of each face have a cross product along its outward normal.
        (Vector3 Normal, Vector3 U, Vector3 V, float Light)[] faces =
        {
            (Vector3.UnitX, Vector3.UnitY, Vector3.UnitZ, 0.85f),
            (-Vector3.UnitX, -Vector3.UnitY, Vector3.UnitZ, 0.66f),
            (Vector3.UnitY, -Vector3.UnitX, Vector3.UnitZ, 0.73f),
            (-Vector3.UnitY, Vector3.UnitX, Vector3.UnitZ, 0.75f),
            (Vector3.UnitZ, Vector3.UnitX, Vector3.UnitY, 1.0f),
            (-Vector3.UnitZ, -Vector3.UnitX, Vector3.UnitY, 0.60f),
        };
        (float U, float V)[] corners = { (0, 0), (1, 0), (1, 1), (0, 1) };
        for (int face = 0; face < faces.Length; face++)
        {
            var (normal, u, v, light) = faces[face];
            var shaded = color * light;
            for (int corner = 0; corner < corners.Length; corner++)
            {
                var (x, y) = corners[corner];
                var position = 0.5f * normal + (x - 0.5f) * u + (y - 0.5f) * v;
                int offset = (face * 4 + corner) * floatsPerVertex;
                Span<float> vertex = vertices.AsSpan(offset, floatsPerVertex);
                vertex[0] = position.X;
                vertex[1] = position.Y;
                vertex[2] = position.Z;
                vertex[3] = normal.X;
                vertex[4] = normal.Y;
                vertex[5] = normal.Z;
                vertex[6] = x;
                vertex[7] = y;
                vertex[8] = u.X;
                vertex[9] = u.Y;
                vertex[10] = u.Z;
                vertex[11] = 1;
                vertex[12] = shaded.X;
                vertex[13] = shaded.Y;
                vertex[14] = shaded.Z;
                vertex[15] = 1;
            }

            uint first = (uint)(face * 4);
            int triangle = face * 6;
            indices[triangle] = first;
            indices[triangle + 1] = first + 1;
            indices[triangle + 2] = first + 2;
            indices[triangle + 3] = first;
            indices[triangle + 4] = first + 2;
            indices[triangle + 5] = first + 3;
        }

        var handle = TerminCore.MeshCreate(null);
        var mesh = TerminCore.MeshGet(handle);
        TcVertexLayout layout = default;
        TerminCore.VertexLayoutInit(ref layout);
        TerminCore.VertexLayoutAdd(ref layout, "position", 3, TcAttribType.Float32, 0);
        // The built-in vertex-color shader uses POSITION at 0 and COLOR0 at 1.
        TerminCore.VertexLayoutAdd(ref layout, "normal", 3, TcAttribType.Float32, 4);
        TerminCore.VertexLayoutAdd(ref layout, "uv", 2, TcAttribType.Float32, 2);
        TerminCore.VertexLayoutAdd(ref layout, "tangent", 4, TcAttribType.Float32, 3);
        TerminCore.VertexLayoutAdd(ref layout, "color", 4, TcAttribType.Float32, 1);
        fixed (float* data = vertices)
        fixed (uint* triangles = indices)
        {
            if (mesh == IntPtr.Zero || !TerminCore.MeshSetData(mesh, (IntPtr)data, 24, ref layout,
                (IntPtr)triangles, (nuint)indices.Length, name))
                throw new InvalidOperationException($"Termin could not create mesh {name}.");
        }
        return handle;
    }

    public void Dispose()
    {
        if (_disposed)
            return;
        _disposed = true;

        if (_displayRef is not null)
        {
            _renderer?.remove_display(_displayRef);
            _displayRef.Dispose();
        }
        if (_display.IsValid && _viewport.IsValid)
            TerminCore.DisplayRemoveViewport(_display, _viewport);
        if (_viewport.IsValid)
            TerminCore.ViewportFree(_viewport);
        if (_target.IsValid)
            TerminCore.RenderTargetFree(_target);
        if (_display.IsValid)
            TerminCore.DisplayFree(_display);
        _pipeline?.destroy();
        _pipeline?.Dispose();
        _scene?.Dispose();
        _renderer?.set_render_engine(null);
        _renderer?.Dispose();
        _renderEngine?.Dispose();
        _engine?.Dispose();
        if (_runtimeInitialized)
            TerminCore.Shutdown();
        if (_hostAcquired)
            Tgfx2Host.Release();
    }

    private static float Radians(double degrees) => (float)(degrees * Math.PI / 180);

    // add_pass transfers native ownership to the pipeline. In the generated
    // binding the pass proxy must relinquish its independent ownership.
    private sealed class PositionerColorPass() : ColorPass("empty", "color", "", "opaque", "ColorPass")
    {
        public void AttachTo(RenderPipeline pipeline)
        {
            pipeline.add_pass(tc_pass_ptr());
            if (pipeline.pass_count() != 1)
                throw new InvalidOperationException("Termin could not attach the positioner color pass.");
            swigCMemOwn = false;
        }
    }

    [DllImport("termin_avalonia_positioner_probe", EntryPoint = "positioner_create_offscreen_display",
        CallingConvention = CallingConvention.Cdecl)]
    private static extern TcDisplayHandle CreateOffscreenDisplay(int width, int height);

    [DllImport("termin_avalonia_positioner_probe", EntryPoint = "positioner_read_bgra",
        CallingConvention = CallingConvention.Cdecl)]
    private static extern unsafe int ReadBgra(TcDisplayHandle display, int width, int height,
        float* rgba, nuint rgbaCount, IntPtr bgra, nuint bufferBytes, nuint rowBytes);
}
