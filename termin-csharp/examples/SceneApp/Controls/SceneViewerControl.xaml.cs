using System;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Termin.Native;
using Termin.Wpf;

namespace SceneApp.Controls;

public partial class SceneViewerControl : UserControl, IDisposable
{
    // Infrastructure
    private D3D11OffscreenDisplay? _display;
    private EngineCore? _engineCore;
    private RenderingManager? _renderingManager;
    private RenderEngine? _renderEngine;
    private bool _hostLeaseHeld;
    private bool _renderingSubscribed;

    // Viewport
    private TcViewportHandle _viewportHandle;
    private TcRenderTargetHandle _renderTargetHandle = TcRenderTargetHandle.Invalid;
    private RenderPipeline? _pipeline;
    private ColorPass? _colorPass;
    private PresentToScreenPass? _presentPass;

    // Scene
    private Scene? _scene;

    // Internal entities (camera)
    private EntityPool? _internalPool;
    private TcEntityId _internalRootId;
    private CameraComponent? _camera;
    private OrbitCameraController? _orbitController;

    // State
    private bool _initialized;
    private bool _disposed;

    public event EventHandler? NativeReady;
    public event EventHandler? RenderFrame;

    public SceneViewerControl()
    {
        InitializeComponent();

        Loaded += OnLoaded;
        Unloaded += OnUnloaded;
        CompositionTarget.Rendering += OnRender;
        _renderingSubscribed = true;
    }

    public Scene? Scene
    {
        get => _scene;
        set
        {
            if (_scene != value)
            {
                _scene = value;
                // Only update if viewport exists (will be set again after init)
                if (_viewportHandle.IsValid)
                {
                    UpdateViewportScene();
                }
            }
        }
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        if (_initialized) return;

        Console.WriteLine(
            $"[SceneViewer] OnLoaded, framebuffer={RenderHost.FramebufferWidth}x{RenderHost.FramebufferHeight}");

        InitializeTermin();

        _initialized = true;
        NativeReady?.Invoke(this, EventArgs.Empty);
    }

    private void OnUnloaded(object sender, RoutedEventArgs e)
    {
        Dispose();
    }

    private void InitializeTermin()
    {
        Console.WriteLine("[SceneViewer] InitializeTermin starting...");

        // Initialize core library (scene pool, viewport pool, etc.)
        TerminCore.InitFull();
        Console.WriteLine("[SceneViewer] tc_init OK");

        string fontPath = FindSystemFont()
            ?? throw new InvalidOperationException("No Windows system TTF font was found.");
        var gpuHost = Tgfx2Host.Acquire(fontPath, BackendType.D3D11);
        _hostLeaseHeld = true;

        // Setup rendering manager
        _engineCore = new EngineCore();
        _renderingManager = _engineCore.rendering_manager();

        _renderEngine = new RenderEngine();
        _renderEngine.set_gpu_host(gpuHost);
        _renderingManager.set_render_engine(_renderEngine);

        // The display owns its offscreen surface and D3D11 textures. RenderHost
        // only borrows the generation handle while presenting and routing input.
        _display = new D3D11OffscreenDisplay(
            RenderHost.FramebufferWidth,
            RenderHost.FramebufferHeight,
            "SceneViewer");
        RenderHost.BindDisplay(_display.Handle);

        // Add display to rendering manager
        var displayWrapper = SwigHelpers.ToSwigDisplayHandle(_display.Handle);
        _renderingManager.add_display(displayWrapper);

        // Create internal entities (camera)
        CreateInternalEntities();

        // Create render pipeline
        CreatePipeline();

        // Create viewport
        CreateViewport();
    }

    private void CreateInternalEntities()
    {
        _internalPool = EntityPool.Create(16);

        var root = _internalPool.CreateEntity("InternalRoot");
        _internalRootId = root.Id;

        var cameraEntity = _internalPool.CreateEntity("Camera");
        cameraEntity.SetParent(root);
        cameraEntity.Position = new System.Numerics.Vector3(3, 3, 2);

        // Add CameraComponent
        _camera = new CameraComponent();
        _camera.set_fov_degrees(60.0);
        _camera.near_clip = 0.1;
        _camera.far_clip = 1000.0;
        cameraEntity.AddComponent(_camera);

        // Add OrbitCameraController
        _orbitController = new OrbitCameraController(
            radius: 5.0,
            min_radius: 0.5,
            max_radius: 100.0,
            prevent_moving: false
        );
        _orbitController.center_on(new Vec3(0, 0, 0));
        cameraEntity.AddComponent(_orbitController);
    }

    private void CreatePipeline()
    {
        _pipeline = new RenderPipeline("SceneViewerPipeline");

        var colorSpec = new ResourceSpec();
        colorSpec.resource = "empty";
        colorSpec.resource_type = "fbo";
        colorSpec.scale = 1.0f;
        colorSpec.samples = 4;
        _pipeline.add_spec(colorSpec);

        _colorPass = new ColorPass(
            input_res: "empty",
            output_res: "color",
            shadow_res: "",
            phase_mark: "opaque",
            pass_name: "ColorPass"
        );
        _pipeline.add_pass(_colorPass.tc_pass_ptr());

        // PresentToScreenPass - copies to screen
        _presentPass = new PresentToScreenPass("color", "OUTPUT");
        _pipeline.add_pass(_presentPass.tc_pass_ptr());
    }

    private void CreateViewport()
    {
        if (_camera == null || _pipeline == null || _internalPool == null || _display == null)
        {
            Console.WriteLine("[SceneViewer] CreateViewport aborted: missing components");
            return;
        }

        // Create viewport (scene can be null initially)
        _viewportHandle = TerminCore.ViewportNew("Main", _scene?.Handle ?? TcSceneHandle.Invalid);

        if (!_viewportHandle.IsValid)
        {
            throw new InvalidOperationException("Failed to create viewport");
        }

        // Full size viewport (relative coords 0-1)
        TerminCore.ViewportSetRect(_viewportHandle, 0.0f, 0.0f, 1.0f, 1.0f);

        _renderTargetHandle = TerminCore.RenderTargetNew("SceneViewerTarget");
        if (!_renderTargetHandle.IsValid)
        {
            throw new InvalidOperationException("Failed to create render target");
        }
        TerminCore.RenderTargetSetScene(_renderTargetHandle, _scene?.Handle ?? TcSceneHandle.Invalid);
        TerminCore.RenderTargetSetPipeline(_renderTargetHandle, _pipeline.handle());
        TerminCore.RenderTargetSetDynamicResolution(_renderTargetHandle, true);
        TerminCore.RenderTargetSetEnabled(_renderTargetHandle, true);
        TerminCore.ViewportSetRenderTarget(_viewportHandle, _renderTargetHandle);

        // Set internal entities
        TerminCore.ViewportSetInternalEntities(
            _viewportHandle,
            new TcEntityHandle
            {
                Pool = _internalPool.PoolHandle,
                Id = _internalRootId
            });

        // Add viewport to display
        _display.AddViewport(_viewportHandle);
        Console.WriteLine($"[SceneViewer] Viewport created: {_viewportHandle}");

        // Now that viewport exists, update scene if it was already set
        if (_scene != null)
        {
            Console.WriteLine("[SceneViewer] Updating viewport scene after creation");
            UpdateViewportScene();
        }
    }

    private void UpdateViewportScene()
    {
        if (!_viewportHandle.IsValid) return;

        if (_scene != null)
        {
            TerminCore.ViewportSetScene(_viewportHandle, _scene.Handle);
            if (_renderTargetHandle.IsValid)
            {
                TerminCore.RenderTargetSetScene(_renderTargetHandle, _scene.Handle);
                if (_camera != null)
                {
                    TerminCore.RenderTargetSetCamera(
                        _renderTargetHandle,
                        _camera.tc_component_ptr());
                }
            }
            Console.WriteLine($"[SceneViewer] Scene set: {_scene.Handle}");
        }
        else
        {
            TerminCore.ViewportSetScene(_viewportHandle, TcSceneHandle.Invalid);
            if (_renderTargetHandle.IsValid)
            {
                TerminCore.RenderTargetSetScene(_renderTargetHandle, TcSceneHandle.Invalid);
            }
            Console.WriteLine("[SceneViewer] Scene cleared");
        }
    }

    private static int _frameCount = 0;

    private TimeSpan _previousRenderTime;

    private void OnRender(object? sender, EventArgs e)
    {
        if (!_initialized || _renderingManager == null || _display == null)
        {
            return;
        }

        TimeSpan now = ((RenderingEventArgs)e).RenderingTime;
        double deltaSeconds = _previousRenderTime == TimeSpan.Zero
            ? 0.0
            : Math.Max(0.0, (now - _previousRenderTime).TotalSeconds);
        _previousRenderTime = now;

        RenderHost.PrepareDisplay();

        // Update camera aspect ratio
        int width = RenderHost.FramebufferWidth;
        int height = RenderHost.FramebufferHeight;
        if (_camera != null)
        {
            _camera.aspect = (double)width / height;
        }

        // Update internal entities (camera controller)
        _internalPool?.UpdateTransforms();

        // Update scene
        _scene?.Update(deltaSeconds);
        _scene?.BeforeRender();

        // Render this display
        var display = SwigHelpers.ToSwigDisplayHandle(_display.Handle);
        _renderingManager.render_display(display);
        if (RenderHost.PresentDisplay())
        {
            RenderFrame?.Invoke(this, EventArgs.Empty);
        }
        else
        {
            Console.Error.WriteLine("[SceneViewer] D3D11 display presentation failed.");
        }

        // Debug output once per second
        _frameCount++;
        if (_frameCount % 60 == 1)
        {
            Console.WriteLine($"[SceneViewer] Frame {_frameCount}, scene entities: {_scene?.Entities.Count ?? 0}, size: {width}x{height}");

            // Debug camera
            if (_camera != null)
            {
                Console.WriteLine($"[SceneViewer] Camera fov={_camera.get_fov_degrees():F1}, aspect={_camera.aspect:F2}, near={_camera.near_clip}, far={_camera.far_clip}");
            }
        }
    }

    public void ResetCamera()
    {
        _orbitController?.center_on(new Vec3(0, 0, 0));
        if (_orbitController != null)
        {
            _orbitController.radius = 5.0;
        }
    }

    public void FocusOn(double x, double y, double z, double distance = 5.0)
    {
        _orbitController?.center_on(new Vec3(x, y, z));
        if (_orbitController != null)
        {
            _orbitController.radius = distance;
        }
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;

        // Remove viewport from display
        if (_display != null && _viewportHandle.IsValid)
        {
            _display.RemoveViewport(_viewportHandle);
        }

        // Free viewport
        if (_viewportHandle.IsValid)
        {
            TerminCore.ViewportFree(_viewportHandle);
            _viewportHandle = TcViewportHandle.Invalid;
        }

        if (_renderTargetHandle.IsValid)
        {
            TerminCore.RenderTargetFree(_renderTargetHandle);
            _renderTargetHandle = TcRenderTargetHandle.Invalid;
        }

        // The borrowed handle must be released before the owning display, and
        // the display must release its textures before GraphicsHost's device.
        RenderHost.ReleaseNativeResources();
        _display?.Dispose();
        _display = null;

        _internalPool?.Dispose();
        _internalPool = null;
        _renderingManager = null;
        _renderEngine?.Dispose();
        _renderEngine = null;
        _engineCore?.Dispose();
        _engineCore = null;

        if (_hostLeaseHeld)
        {
            Tgfx2Host.Release();
            _hostLeaseHeld = false;
        }
        if (_renderingSubscribed)
        {
            CompositionTarget.Rendering -= OnRender;
            _renderingSubscribed = false;
        }
        _initialized = false;

        GC.SuppressFinalize(this);
    }

    ~SceneViewerControl()
    {
        Console.Error.WriteLine(
            "[SceneViewer] Finalized without deterministic disposal; native resources may still be live.");
    }

    private static string? FindSystemFont()
    {
        string fonts = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.Windows),
            "Fonts");
        foreach (string name in new[] { "segoeui.ttf", "arial.ttf", "tahoma.ttf" })
        {
            string path = Path.Combine(fonts, name);
            if (File.Exists(path))
            {
                return path;
            }
        }
        return null;
    }
}
