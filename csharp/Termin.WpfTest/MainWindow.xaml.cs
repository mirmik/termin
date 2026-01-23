using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Windows;
using OpenTK.Graphics.OpenGL4;
using OpenTK.Mathematics;
using OpenTK.Wpf;
using Termin.Native;

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
    private float _angle;
    private bool _initialized;

    // Pipeline rendering (disabled for now - requires pass registration)
    private IntPtr _pipeline;
    private IntPtr _fboPool;
    private IntPtr _graphics;
    private Camera? _camera;
    private Scene? _scene;

    // Direct mesh rendering (fallback)
    private TcMeshHandle _meshHandle;
    private TcShaderHandle _shaderHandle;
    private IntPtr _meshPtr;
    private IntPtr _shaderPtr;

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
    }

    private void InitGL()
    {
        if (_initialized) return;
        _initialized = true;

        // Initialize termin OpenGL backend
        if (!NativeLoader.TerminOpenGLInit())
        {
            MessageBox.Show("Failed to initialize Termin OpenGL backend", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
            return;
        }

        // Initialize termin registries
        TerminCore.MeshInit();
        TerminCore.ShaderInit();
        TerminCore.MaterialInit();

        GL.Enable(EnableCap.DepthTest);

        // Get graphics backend
        _graphics = TerminOpenGL.GetGraphics();

        // Create camera using Termin.Native SWIG wrapper
        _camera = Camera.perspective_deg(60.0, 800.0 / 600.0);

        // Create scene
        _scene = new Scene();

        // Create entity (without MeshRenderer for now - just testing pipeline)
        var cubeId = _scene.Entities.CreateEntity("Cube");
        _scene.Entities.SetPosition(cubeId, new System.Numerics.Vector3(0, 0, 0));

        // Create pipeline
        InitPipeline();

        // Create mesh and shader for direct rendering
        CreateCubeMesh();
        CreateShader();
    }

    private void InitPipeline()
    {
        // Test pass registry
        var typeCount = NativeLoader.PassRegistryTypeCount();
        var passTypes = new List<string>();
        for (nuint i = 0; i < typeCount; i++)
        {
            var typeName = NativeLoader.PassRegistryTypeAt(i);
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
        }

        // Create pipeline with passes
        _pipeline = NativeLoader.PipelineCreate("default");
        if (_pipeline == IntPtr.Zero)
        {
            Console.WriteLine("[WARNING] Failed to create pipeline");
            return;
        }
        Console.WriteLine($"[Pipeline] Created at 0x{_pipeline:X}");

        // Create and add passes
        if (NativeLoader.PassRegistryHas("DepthPass"))
        {
            var depthPass = NativeLoader.PassRegistryCreate("DepthPass");
            if (depthPass != IntPtr.Zero)
            {
                NativeLoader.PassSetName(depthPass, "Depth");
                NativeLoader.PipelineAddPass(_pipeline, depthPass);
                Console.WriteLine("[Pipeline] Added DepthPass");
            }
        }

        if (NativeLoader.PassRegistryHas("ColorPass"))
        {
            var colorPass = NativeLoader.PassRegistryCreate("ColorPass");
            if (colorPass != IntPtr.Zero)
            {
                NativeLoader.PassSetName(colorPass, "Color");
                NativeLoader.PipelineAddPass(_pipeline, colorPass);
                Console.WriteLine("[Pipeline] Added ColorPass");
            }
        }

        var passCount = NativeLoader.PipelinePassCount(_pipeline);
        Console.WriteLine($"[Pipeline] Total passes: {passCount}");
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

        _shaderPtr = TerminCore.ShaderGet(_shaderHandle);
        if (_shaderPtr != IntPtr.Zero)
        {
            TerminCore.ShaderCompileGpu(_shaderPtr);
        }
    }

    private void GlControl_Render(TimeSpan delta)
    {
        InitGL();

        int width = (int)GlControl.ActualWidth;
        int height = (int)GlControl.ActualHeight;
        if (width <= 0 || height <= 0) return;

        // Update camera aspect ratio
        double aspect = width / (double)height;
        if (_camera != null)
        {
            _camera.aspect = aspect;
        }

        // Direct rendering - demonstrates mesh/shader integration
        GL.ClearColor(0.1f, 0.1f, 0.15f, 1.0f);
        GL.Clear(ClearBufferMask.ColorBufferBit | ClearBufferMask.DepthBufferBit);

        if (_shaderPtr == IntPtr.Zero || _meshPtr == IntPtr.Zero)
            return;

        // Model matrix (rotating cube)
        _angle += (float)delta.TotalSeconds * 45.0f;
        var model = Matrix4.CreateRotationY(MathHelper.DegreesToRadians(_angle)) *
                    Matrix4.CreateRotationX(MathHelper.DegreesToRadians(_angle * 0.5f));

        // View matrix - camera at (0, -3, 2) looking at origin
        var eye = new Vector3(0, -3, 2);
        var target = new Vector3(0, 0, 0);
        var up = new Vector3(0, 0, 1);
        var view = Matrix4.LookAt(eye, target, up);

        // Projection matrix
        float fov = _camera != null ? (float)_camera.fov_y : MathHelper.DegreesToRadians(60.0f);
        float near = _camera != null ? (float)_camera.near : 0.1f;
        float far = _camera != null ? (float)_camera.far : 100.0f;
        var projection = Matrix4.CreatePerspectiveFieldOfView(fov, (float)aspect, near, far);

        // Use shader and draw
        TerminCore.ShaderUseGpu(_shaderPtr);

        float[] modelData = MatrixToArray(model);
        float[] viewData = MatrixToArray(view);
        float[] projData = MatrixToArray(projection);

        TerminCore.ShaderSetMat4(_shaderPtr, "u_model", modelData, false);
        TerminCore.ShaderSetMat4(_shaderPtr, "u_view", viewData, false);
        TerminCore.ShaderSetMat4(_shaderPtr, "u_projection", projData, false);
        TerminCore.ShaderSetVec4(_shaderPtr, "u_color", 0.8f, 0.3f, 0.2f, 1.0f);

        TerminCore.MeshDrawGpu(_meshPtr);
    }

    private static float[] MatrixToArray(Matrix4 m)
    {
        return new float[]
        {
            m.M11, m.M12, m.M13, m.M14,
            m.M21, m.M22, m.M23, m.M24,
            m.M31, m.M32, m.M33, m.M34,
            m.M41, m.M42, m.M43, m.M44
        };
    }

    protected override void OnClosed(EventArgs e)
    {
        // Cleanup pipeline
        if (_fboPool != IntPtr.Zero)
        {
            TerminCore.FboPoolDestroy(_fboPool);
            _fboPool = IntPtr.Zero;
        }
        if (_pipeline != IntPtr.Zero)
        {
            TerminCore.PipelineDestroy(_pipeline);
            _pipeline = IntPtr.Zero;
        }

        // Cleanup scene
        _scene?.Dispose();
        _scene = null;

        // Cleanup camera
        _camera?.Dispose();
        _camera = null;

        // Cleanup termin resources
        TerminCore.MaterialShutdown();
        TerminCore.ShaderShutdown();
        TerminCore.MeshShutdown();
        NativeLoader.TerminOpenGLShutdown();

        base.OnClosed(e);
    }
}
