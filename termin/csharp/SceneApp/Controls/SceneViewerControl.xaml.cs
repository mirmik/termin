using System;
using System.Windows;
using System.Windows.Controls;
using OpenTK.Graphics.OpenGL4;
using OpenTK.Wpf;
using Termin.Native;
using SceneApp.Infrastructure;

namespace SceneApp.Controls;

public partial class SceneViewerControl : UserControl, IDisposable
{
    // Infrastructure
    private GlWpfBackend? _backend;
    private WpfRenderSurface? _renderSurface;
    private NativeDisplayManager? _displayManager;
    private SWIGTYPE_p_termin__GraphicsBackend? _graphics;
    private PullRenderingManager? _renderingManager;
    private RenderEngine? _renderEngine;

    // Viewport
    private TcViewportHandle _viewportHandle;
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

    public SceneViewerControl()
    {
        InitializeComponent();

        // Start GL control in constructor (like WpfTest)
        var settings = new GLWpfControlSettings
        {
            MajorVersion = 4,
            MinorVersion = 5
        };
        GlControl.Start(settings);
        GlControl.Render += GlControl_Render;
        _backend = new GlWpfBackend(GlControl);

        Loaded += OnLoaded;
        Unloaded += OnUnloaded;
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

        Console.WriteLine($"[SceneViewer] OnLoaded, size={GlControl.ActualWidth}x{GlControl.ActualHeight}");

        InitializeTermin();

        _initialized = true;
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

        // Initialize termin OpenGL backend
        if (!termin.tc_opengl_init())
        {
            throw new InvalidOperationException("Failed to initialize Termin OpenGL backend");
        }
        Console.WriteLine("[SceneViewer] tc_opengl_init OK");

        // Initialize registries
        TerminCore.MeshInit();
        TerminCore.ShaderInit();
        TerminCore.MaterialInit();
        Console.WriteLine("[SceneViewer] Registries initialized");

        GL.Enable(EnableCap.DepthTest);

        // Get graphics backend
        _graphics = termin.get_opengl_graphics();

        // Setup rendering manager
        _renderingManager = PullRenderingManager.instance();
        _renderingManager.set_graphics(_graphics);

        _renderEngine = new RenderEngine(_graphics);
        _renderingManager.set_render_engine(_renderEngine);

        // Create render surface and display manager
        _renderSurface = new WpfRenderSurface(GlControl);
        _displayManager = new NativeDisplayManager(_renderSurface, _backend!, "SceneViewer");

        // Add display to rendering manager
        var displayWrapper = SwigHelpers.WrapTcDisplayPtr(_displayManager.DisplayPtr);
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
        if (_camera == null || _pipeline == null || _internalPool == null || _displayManager == null)
        {
            Console.WriteLine("[SceneViewer] CreateViewport aborted: missing components");
            return;
        }

        // Create viewport (scene can be null initially)
        _viewportHandle = TerminCore.ViewportNew("Main", _scene?.Handle ?? TcSceneHandle.Invalid, _camera.tc_component_ptr());

        if (!_viewportHandle.IsValid)
        {
            throw new InvalidOperationException("Failed to create viewport");
        }

        // Full size viewport (relative coords 0-1)
        TerminCore.ViewportSetRect(_viewportHandle, 0.0f, 0.0f, 1.0f, 1.0f);

        // Set pipeline
        TerminCore.ViewportSetPipeline(_viewportHandle, _pipeline.handle());

        // Set internal entities
        TerminCore.ViewportSetInternalEntities(_viewportHandle, _internalPool.Handle, _internalRootId);

        // Add viewport to display
        _displayManager.AddViewport(_viewportHandle);
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
            Console.WriteLine($"[SceneViewer] Scene set: {_scene.Handle}");
        }
        else
        {
            TerminCore.ViewportSetScene(_viewportHandle, TcSceneHandle.Invalid);
            Console.WriteLine("[SceneViewer] Scene cleared");
        }
    }

    private static int _frameCount = 0;

    private void GlControl_Render(TimeSpan delta)
    {
        Console.WriteLine("[SceneViewer] GlControl_Render called");

        if (!_initialized || _renderingManager == null || _renderSurface == null || _displayManager == null) 
        {
            Console.WriteLine("[SceneViewer] GlControl_Render skipped: not initialized");
            return;
        }

        // Update camera aspect ratio
        int width = Math.Max(1, (int)GlControl.ActualWidth);
        int height = Math.Max(1, (int)GlControl.ActualHeight);
        if (_camera != null)
        {
            _camera.aspect = (double)width / height;
        }

        // Update internal entities (camera controller)
        _internalPool?.UpdateTransforms();

        // Update scene
        _scene?.Update(delta.TotalSeconds);
        _scene?.BeforeRender();

        // Cache WPF's FBO before rendering
        _renderSurface.UpdateFramebuffer();

        // Clear the screen
        GL.ClearColor(0.2f, 0.2f, 0.25f, 1.0f);
        GL.Clear(ClearBufferMask.ColorBufferBit | ClearBufferMask.DepthBufferBit);

        // Render this display
        var display = SwigHelpers.WrapTcDisplayPtr(_displayManager.DisplayPtr);
        _renderingManager.render_display(display);

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
        if (_displayManager != null && _viewportHandle.IsValid)
        {
            _displayManager.RemoveViewport(_viewportHandle);
        }

        // Free viewport
        if (_viewportHandle.IsValid)
        {
            TerminCore.ViewportFree(_viewportHandle);
            _viewportHandle = TcViewportHandle.Invalid;
        }

        // Dispose managers
        _displayManager?.Dispose();
        _displayManager = null;

        _renderSurface?.Dispose();
        _renderSurface = null;

        _internalPool?.Dispose();
        _internalPool = null;

        _initialized = false;

        GC.SuppressFinalize(this);
    }

    ~SceneViewerControl()
    {
        Dispose();
    }
}
