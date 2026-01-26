using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Windows;
using OpenTK.Graphics.OpenGL4;
using OpenTK.Mathematics;
using OpenTK.Wpf;
using Termin.Native;
using Termin.WpfTest.Input;

namespace Termin.WpfTest;

// Helper to pre-load native DLLs and provide direct P/Invoke
static class NativeLoader
{
    private static IntPtr _terminHandle = IntPtr.Zero;
    private static IntPtr _terminCoreHandle = IntPtr.Zero;

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr LoadLibrary(string lpFileName);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr GetProcAddress(IntPtr hModule, string lpProcName);

    // Delegate types for native functions
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    [return: MarshalAs(UnmanagedType.U1)]
    private delegate bool OpenGLInitDelegate();

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate void OpenGLShutdownDelegate();

    // Pass registry delegates
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    [return: MarshalAs(UnmanagedType.U1)]
    private delegate bool PassRegistryHasDelegate([MarshalAs(UnmanagedType.LPStr)] string typeName);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate IntPtr PassRegistryCreateDelegate([MarshalAs(UnmanagedType.LPStr)] string typeName);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate nuint PassRegistryTypeCountDelegate();

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate IntPtr PassRegistryTypeAtDelegate(nuint index);

    // Pipeline delegates
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate IntPtr PipelineCreateDelegate([MarshalAs(UnmanagedType.LPStr)] string name);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate void PipelineDestroyDelegate(IntPtr pipeline);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate void PipelineAddPassDelegate(IntPtr pipeline, IntPtr pass);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate nuint PipelinePassCountDelegate(IntPtr pipeline);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate IntPtr PipelinePassAtDelegate(IntPtr pipeline, nuint index);

    // Pass property delegates
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate void PassSetNameDelegate(IntPtr pass, [MarshalAs(UnmanagedType.LPStr)] string name);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate void PassSetEnabledDelegate(IntPtr pass, [MarshalAs(UnmanagedType.U1)] bool enabled);

    private static OpenGLInitDelegate? _openglInit;
    private static OpenGLShutdownDelegate? _openglShutdown;
    private static PassRegistryHasDelegate? _passRegistryHas;
    private static PassRegistryCreateDelegate? _passRegistryCreate;
    private static PassRegistryTypeCountDelegate? _passRegistryTypeCount;
    private static PassRegistryTypeAtDelegate? _passRegistryTypeAt;
    private static PipelineCreateDelegate? _pipelineCreate;
    private static PipelineDestroyDelegate? _pipelineDestroy;
    private static PipelineAddPassDelegate? _pipelineAddPass;
    private static PipelinePassCountDelegate? _pipelinePassCount;
    private static PipelinePassAtDelegate? _pipelinePassAt;
    private static PassSetNameDelegate? _passSetName;
    private static PassSetEnabledDelegate? _passSetEnabled;

    public static void Initialize()
    {
        string baseDir = AppDomain.CurrentDomain.BaseDirectory;

        // Load termin_core.dll first (dependency)
        var corePath = Path.Combine(baseDir, "termin_core.dll");
        _terminCoreHandle = LoadLibrary(corePath);
        if (_terminCoreHandle == IntPtr.Zero)
        {
            int error = Marshal.GetLastWin32Error();
            throw new Exception($"Failed to load termin_core.dll from {corePath}. Error: {error}");
        }

        // Then load termin.dll
        var terminPath = Path.Combine(baseDir, "termin.dll");
        _terminHandle = LoadLibrary(terminPath);
        if (_terminHandle == IntPtr.Zero)
        {
            int error = Marshal.GetLastWin32Error();
            throw new Exception($"Failed to load termin.dll from {terminPath}. Error: {error}");
        }

        // Get function pointers
        var initPtr = GetProcAddress(_terminHandle, "tc_opengl_init");
        if (initPtr == IntPtr.Zero)
        {
            throw new Exception("tc_opengl_init not found in termin.dll");
        }
        _openglInit = Marshal.GetDelegateForFunctionPointer<OpenGLInitDelegate>(initPtr);

        var shutdownPtr = GetProcAddress(_terminHandle, "tc_opengl_shutdown");
        if (shutdownPtr != IntPtr.Zero)
        {
            _openglShutdown = Marshal.GetDelegateForFunctionPointer<OpenGLShutdownDelegate>(shutdownPtr);
        }

        // Get pass registry function pointers from termin_core.dll (where tc_pass functions are)
        var hasPtr = GetProcAddress(_terminCoreHandle, "tc_pass_registry_has");
        if (hasPtr != IntPtr.Zero)
            _passRegistryHas = Marshal.GetDelegateForFunctionPointer<PassRegistryHasDelegate>(hasPtr);

        var createPtr = GetProcAddress(_terminCoreHandle, "tc_pass_registry_create");
        if (createPtr != IntPtr.Zero)
            _passRegistryCreate = Marshal.GetDelegateForFunctionPointer<PassRegistryCreateDelegate>(createPtr);

        var countPtr = GetProcAddress(_terminCoreHandle, "tc_pass_registry_type_count");
        if (countPtr != IntPtr.Zero)
            _passRegistryTypeCount = Marshal.GetDelegateForFunctionPointer<PassRegistryTypeCountDelegate>(countPtr);

        var typeAtPtr = GetProcAddress(_terminCoreHandle, "tc_pass_registry_type_at");
        if (typeAtPtr != IntPtr.Zero)
            _passRegistryTypeAt = Marshal.GetDelegateForFunctionPointer<PassRegistryTypeAtDelegate>(typeAtPtr);

        // Pipeline functions
        var pipelineCreatePtr = GetProcAddress(_terminCoreHandle, "tc_pipeline_create");
        if (pipelineCreatePtr != IntPtr.Zero)
            _pipelineCreate = Marshal.GetDelegateForFunctionPointer<PipelineCreateDelegate>(pipelineCreatePtr);

        var pipelineDestroyPtr = GetProcAddress(_terminCoreHandle, "tc_pipeline_destroy");
        if (pipelineDestroyPtr != IntPtr.Zero)
            _pipelineDestroy = Marshal.GetDelegateForFunctionPointer<PipelineDestroyDelegate>(pipelineDestroyPtr);

        var pipelineAddPassPtr = GetProcAddress(_terminCoreHandle, "tc_pipeline_add_pass");
        if (pipelineAddPassPtr != IntPtr.Zero)
            _pipelineAddPass = Marshal.GetDelegateForFunctionPointer<PipelineAddPassDelegate>(pipelineAddPassPtr);

        var pipelinePassCountPtr = GetProcAddress(_terminCoreHandle, "tc_pipeline_pass_count");
        if (pipelinePassCountPtr != IntPtr.Zero)
            _pipelinePassCount = Marshal.GetDelegateForFunctionPointer<PipelinePassCountDelegate>(pipelinePassCountPtr);

        var pipelinePassAtPtr = GetProcAddress(_terminCoreHandle, "tc_pipeline_get_pass_at");
        if (pipelinePassAtPtr != IntPtr.Zero)
            _pipelinePassAt = Marshal.GetDelegateForFunctionPointer<PipelinePassAtDelegate>(pipelinePassAtPtr);

        // Pass property functions
        var passSetNamePtr = GetProcAddress(_terminCoreHandle, "tc_pass_set_name");
        if (passSetNamePtr != IntPtr.Zero)
            _passSetName = Marshal.GetDelegateForFunctionPointer<PassSetNameDelegate>(passSetNamePtr);

        var passSetEnabledPtr = GetProcAddress(_terminCoreHandle, "tc_pass_set_enabled");
        if (passSetEnabledPtr != IntPtr.Zero)
            _passSetEnabled = Marshal.GetDelegateForFunctionPointer<PassSetEnabledDelegate>(passSetEnabledPtr);

        // Set DllImportResolver for Termin.Native assembly
        NativeLibrary.SetDllImportResolver(typeof(TerminCore).Assembly, ResolveDll);
    }

    private static IntPtr ResolveDll(string libraryName, Assembly assembly, DllImportSearchPath? searchPath)
    {
        if (libraryName == "termin_core")
        {
            return _terminCoreHandle;
        }
        if (libraryName == "termin")
        {
            return _terminHandle;
        }
        return IntPtr.Zero;
    }

    public static bool TerminOpenGLInit()
    {
        return _openglInit?.Invoke() ?? false;
    }

    public static void TerminOpenGLShutdown()
    {
        _openglShutdown?.Invoke();
    }

    // Pass registry methods
    public static bool PassRegistryHas(string typeName)
    {
        return _passRegistryHas?.Invoke(typeName) ?? false;
    }

    public static IntPtr PassRegistryCreate(string typeName)
    {
        return _passRegistryCreate?.Invoke(typeName) ?? IntPtr.Zero;
    }

    public static nuint PassRegistryTypeCount()
    {
        return _passRegistryTypeCount?.Invoke() ?? 0;
    }

    public static string? PassRegistryTypeAt(nuint index)
    {
        var ptr = _passRegistryTypeAt?.Invoke(index) ?? IntPtr.Zero;
        return ptr != IntPtr.Zero ? Marshal.PtrToStringAnsi(ptr) : null;
    }

    // Pipeline methods
    public static IntPtr PipelineCreate(string name)
    {
        return _pipelineCreate?.Invoke(name) ?? IntPtr.Zero;
    }

    public static void PipelineDestroy(IntPtr pipeline)
    {
        _pipelineDestroy?.Invoke(pipeline);
    }

    public static void PipelineAddPass(IntPtr pipeline, IntPtr pass)
    {
        _pipelineAddPass?.Invoke(pipeline, pass);
    }

    public static nuint PipelinePassCount(IntPtr pipeline)
    {
        return _pipelinePassCount?.Invoke(pipeline) ?? 0;
    }

    public static IntPtr PipelinePassAt(IntPtr pipeline, nuint index)
    {
        return _pipelinePassAt?.Invoke(pipeline, index) ?? IntPtr.Zero;
    }

    // Pass property methods
    public static void PassSetName(IntPtr pass, string name)
    {
        _passSetName?.Invoke(pass, name);
    }

    public static void PassSetEnabled(IntPtr pass, bool enabled)
    {
        _passSetEnabled?.Invoke(pass, enabled);
    }
}

public partial class MainWindow : Window
{
    private bool _initialized;
    private int _renderCount;

    // Backend и InputManager
    private GlWpfBackend? _backend;
    private InputManager? _inputManager;

    // Pipeline rendering via SWIG C++ classes
    private RenderPipeline? _renderPipeline;
    private RenderEngine? _renderEngine;
    private CameraComponent? _cameraComponent;
    private ColorPass? _colorPass;  // Keep reference to prevent GC collection
    private Scene? _scene;

    // Mesh resources
    private TcMeshHandle _meshHandle;
    private TcShaderHandle _shaderHandle;
    private TcMaterialHandle _materialHandle;
    private IntPtr _meshPtr;
    private MeshRenderer? _meshRenderer;

    public MainWindow()
    {
        // Pre-load native DLLs before any P/Invoke calls
        NativeLoader.Initialize();

        InitializeComponent();

        var settings = new GLWpfControlSettings
        {
            MajorVersion = 4,
            MinorVersion = 5
        };
        GlControl.Start(settings);

        // Создаём backend и input manager
        _backend = new GlWpfBackend(GlControl);
        _inputManager = new InputManager(_backend);
        
        Console.WriteLine("[Init] Backend and InputManager created");
    }

    private void InitGL()
    {
        if (_initialized) return;
        _initialized = true;

        // Initialize termin OpenGL backend
        if (!termin.tc_opengl_init())
        {
            MessageBox.Show("Failed to initialize Termin OpenGL backend", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
            return;
        }

        // Initialize termin registries
        TerminCore.MeshInit();
        TerminCore.ShaderInit();
        TerminCore.MaterialInit();

        // Initialize C# component and pass external body callbacks
        ComponentExternalBody.Initialize();
        PassExternalBody.Initialize();

        GL.Enable(EnableCap.DepthTest);

        // Get graphics backend (SWIG helper)
        var graphics = termin.get_opengl_graphics();

        // Create render engine
        _renderEngine = new RenderEngine(graphics);

        // Create scene
        _scene = new Scene();

        // Create camera entity with CameraComponent
        var cameraEntityId = _scene.Entities.CreateEntity("Camera");
        _scene.Entities.SetPosition(cameraEntityId, new System.Numerics.Vector3(0, -3, 1));

        _cameraComponent = new CameraComponent();
        _cameraComponent.set_fov_degrees(60.0);
        _cameraComponent.near_clip = 0.1;
        _cameraComponent.far_clip = 100.0;

        // Register C# wrapper as external body (prevents GC while C++ holds reference)
        var cameraBodyPtr = ComponentExternalBody.Register(_cameraComponent);
        _cameraComponent.set_external_body(cameraBodyPtr);

        // Add component to entity
        var cameraComponentPtr = _cameraComponent.tc_component_ptr();
        TerminCore.EntityPoolAddComponent(_scene.Entities.Handle, cameraEntityId, cameraComponentPtr);
        Console.WriteLine("[Init] Created CameraComponent and added to entity");

        // Create mesh and shader
        CreateCubeMesh();
        CreateShader();
        CreateMaterial();

        // Create cube entity with MeshRenderer
        var cubeId = _scene.Entities.CreateEntity("Cube");
        _scene.Entities.SetPosition(cubeId, new System.Numerics.Vector3(0, 0, 0));
        
        _meshRenderer = new MeshRenderer();
        _meshRenderer.set_mesh_by_name("cube");
        _meshRenderer.set_material_by_name("cube_material");

        // Register C# wrapper as external body
        var meshBodyPtr = ComponentExternalBody.Register(_meshRenderer);
        _meshRenderer.set_external_body(meshBodyPtr);

        // Add component to entity
        var meshComponentPtr = _meshRenderer.tc_component_ptr();
        TerminCore.EntityPoolAddComponent(_scene.Entities.Handle, cubeId, meshComponentPtr);
        Console.WriteLine("[Init] Created MeshRenderer and added to entity");

        // Create render pipeline
        InitPipeline();
    }

    private void CreateMaterial()
    {
        // Create a simple material with our shader
        _materialHandle = TerminCore.MaterialCreate(null, "cube_material");
        var matPtr = TerminCore.MaterialGet(_materialHandle);
        if (matPtr != IntPtr.Zero)
        {
            // Add phase with shader
            TerminCore.MaterialAddPhase(matPtr, _shaderHandle, "opaque", 0);
            TerminCore.MaterialSetColor(matPtr, 0.8f, 0.3f, 0.2f, 1.0f);
            Console.WriteLine("[Init] Created material");
        }
    }

    private void InitPipeline()
    {
        // Test pass registry
        var typeCount = termin.tc_pass_registry_type_count();
        var passTypes = new List<string>();
        for (uint i = 0; i < typeCount; i++)
        {
            var typeName = termin.tc_pass_registry_type_at(i);
            if (typeName != null)
                passTypes.Add(typeName);
        }

        if (typeCount > 0)
        {
            Console.WriteLine($"[Pass Registry] {typeCount} types registered:");
            foreach (var t in passTypes)
                Console.WriteLine($"  - {t}");
        }
        else
        {
            Console.WriteLine("[WARNING] Pass registry is empty - passes not registered!");
            return;
        }

        // Create RenderPipeline (SWIG class with specs and FBO pool)
        _renderPipeline = new RenderPipeline("default");
        Console.WriteLine($"[RenderPipeline] Created: {_renderPipeline.name()}");

        // Add resource specs
        var colorSpec = new ResourceSpec();
        colorSpec.resource = "color";
        colorSpec.resource_type = "fbo";
        colorSpec.scale = 1.0f;
        colorSpec.samples = 1;
        _renderPipeline.add_spec(colorSpec);

        var depthSpec = new ResourceSpec();
        depthSpec.resource = "depth";
        depthSpec.resource_type = "fbo";
        depthSpec.scale = 1.0f;
        depthSpec.samples = 1;
        _renderPipeline.add_spec(depthSpec);

        // Create and add ColorPass (SWIG class)
        // Render to "color" FBO, then blit to screen
        _colorPass = new ColorPass(
            input_res: "empty",
            output_res: "color",
            shadow_res: "",
            phase_mark: "opaque",
            pass_name: "Color"
        );

        // Register C# wrapper as external body (prevents GC while C++ holds reference)
        var passBodyPtr = PassExternalBody.Register(_colorPass);
        _colorPass.set_external_body(passBodyPtr);

        _renderPipeline.add_pass(_colorPass.tc_pass_ptr());
        Console.WriteLine("[RenderPipeline] Added ColorPass");

        var passCount = _renderPipeline.pass_count();
        Console.WriteLine($"[RenderPipeline] Total passes: {passCount}");
    }

    private unsafe void CreateCubeMesh()
    {
        // Cube vertices: position (3) + normal (3) + uv (2) = 8 floats per vertex
        float[] vertices = {
            // Front face (Z+)
            -0.5f, -0.5f,  0.5f,   0, 0, 1,   0, 0,
             0.5f, -0.5f,  0.5f,   0, 0, 1,   1, 0,
             0.5f,  0.5f,  0.5f,   0, 0, 1,   1, 1,
            -0.5f,  0.5f,  0.5f,   0, 0, 1,   0, 1,
            // Back face (Z-)
            -0.5f, -0.5f, -0.5f,   0, 0,-1,   1, 0,
            -0.5f,  0.5f, -0.5f,   0, 0,-1,   1, 1,
             0.5f,  0.5f, -0.5f,   0, 0,-1,   0, 1,
             0.5f, -0.5f, -0.5f,   0, 0,-1,   0, 0,
            // Top face (Y+)
            -0.5f,  0.5f, -0.5f,   0, 1, 0,   0, 1,
            -0.5f,  0.5f,  0.5f,   0, 1, 0,   0, 0,
             0.5f,  0.5f,  0.5f,   0, 1, 0,   1, 0,
             0.5f,  0.5f, -0.5f,   0, 1, 0,   1, 1,
            // Bottom face (Y-)
            -0.5f, -0.5f, -0.5f,   0,-1, 0,   0, 0,
             0.5f, -0.5f, -0.5f,   0,-1, 0,   1, 0,
             0.5f, -0.5f,  0.5f,   0,-1, 0,   1, 1,
            -0.5f, -0.5f,  0.5f,   0,-1, 0,   0, 1,
            // Right face (X+)
             0.5f, -0.5f, -0.5f,   1, 0, 0,   0, 0,
             0.5f,  0.5f, -0.5f,   1, 0, 0,   0, 1,
             0.5f,  0.5f,  0.5f,   1, 0, 0,   1, 1,
             0.5f, -0.5f,  0.5f,   1, 0, 0,   1, 0,
            // Left face (X-)
            -0.5f, -0.5f, -0.5f,  -1, 0, 0,   1, 0,
            -0.5f, -0.5f,  0.5f,  -1, 0, 0,   0, 0,
            -0.5f,  0.5f,  0.5f,  -1, 0, 0,   0, 1,
            -0.5f,  0.5f, -0.5f,  -1, 0, 0,   1, 1,
        };

        uint[] indices = {
            0, 1, 2, 2, 3, 0,       // front
            4, 5, 6, 6, 7, 4,       // back
            8, 9, 10, 10, 11, 8,   // top
            12, 13, 14, 14, 15, 12, // bottom
            16, 17, 18, 18, 19, 16, // right
            20, 21, 22, 22, 23, 20  // left
        };

        _meshHandle = TerminCore.MeshCreate(null);
        _meshPtr = TerminCore.MeshGet(_meshHandle);

        if (_meshPtr == IntPtr.Zero) return;

        TcVertexLayout layout = TerminCore.VertexLayoutPosNormalUv();

        fixed (float* vertPtr = vertices)
        fixed (uint* idxPtr = indices)
        {
            TerminCore.MeshSetData(
                _meshPtr,
                (IntPtr)vertPtr,
                (nuint)24,
                ref layout,
                (IntPtr)idxPtr,
                (nuint)indices.Length,
                "cube"
            );
        }

        TerminCore.MeshUploadGpu(_meshPtr);
    }

    private void CreateShader()
    {
        string vertexShaderSource = @"#version 450 core
layout (location = 0) in vec3 position;
layout (location = 1) in vec3 normal;
layout (location = 2) in vec2 uv;

out vec3 v_normal;
out vec2 v_uv;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

void main() {
    gl_Position = u_projection * u_view * u_model * vec4(position, 1.0);
    v_normal = mat3(u_model) * normal;
    v_uv = uv;
}
";

        string fragmentShaderSource = @"#version 450 core
in vec3 v_normal;
in vec2 v_uv;

out vec4 FragColor;

uniform vec4 u_color;

void main() {
    vec3 lightDir = normalize(vec3(1.0, 1.0, 1.0));
    float diff = max(dot(normalize(v_normal), lightDir), 0.0);
    float ambient = 0.3;
    float lighting = ambient + diff * 0.7;
    FragColor = vec4(u_color.rgb * lighting, u_color.a);
}
";

        _shaderHandle = TerminCore.ShaderFromSources(
            vertexShaderSource,
            fragmentShaderSource,
            null,
            "simple_lit",
            null
        );

        var shaderPtr = TerminCore.ShaderGet(_shaderHandle);
        if (shaderPtr != IntPtr.Zero)
        {
            TerminCore.ShaderCompileGpu(shaderPtr);
        }
    }

    private void GlControl_Render(TimeSpan delta)
    {
        try
        {
            InitGL();

            int width = (int)GlControl.ActualWidth;
            int height = (int)GlControl.ActualHeight;
            if (width <= 0 || height <= 0) return;

            // Update camera aspect ratio
            double aspect = width / (double)height;
            if (_cameraComponent != null)
            {
                _cameraComponent.aspect = aspect;
            }

            // Update scene (for entity transforms)
            _scene?.Update(delta.TotalSeconds);
            _scene?.BeforeRender();

            // Pipeline rendering
            if (_renderPipeline != null && _renderEngine != null && _cameraComponent != null && _backend != null)
            {
                // Save WPF's FBO before rendering (pipeline will change it)
                int wpfFbo = _backend.GetCurrentFboId();

                // Wrap scene handle for SWIG
                var scenePtr = _scene?.Handle ?? IntPtr.Zero;
                var sceneWrapper = SwigHelpers.WrapVoidPtr(scenePtr);

                // Render via pipeline
                _renderEngine.render_to_screen(
                    _renderPipeline,
                    width,
                    height,
                    sceneWrapper,
                    _cameraComponent
                );

                // Blit color FBO to WPF's FBO via backend
                _backend.BlitFromPipeline(_renderPipeline, "color", wpfFbo);

                _renderCount++;
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[Render] Exception: {ex}");
        }
    }

    protected override void OnClosed(EventArgs e)
    {
        // Cleanup input first
        _inputManager?.Dispose();
        _inputManager = null;

        _backend?.Dispose();
        _backend = null;

        // Cleanup scene first (this will properly remove components from entities)
        _scene?.Dispose();
        _scene = null;

        // Then cleanup SWIG objects in reverse order of creation
        _meshRenderer?.Dispose();
        _meshRenderer = null;

        _cameraComponent?.Dispose();
        _cameraComponent = null;

        _renderEngine?.Dispose();
        _renderEngine = null;

        _renderPipeline?.Dispose();
        _renderPipeline = null;

        // Cleanup termin resources
        TerminCore.MaterialShutdown();
        TerminCore.ShaderShutdown();
        TerminCore.MeshShutdown();
        termin.tc_opengl_shutdown();

        base.OnClosed(e);
    }
}
