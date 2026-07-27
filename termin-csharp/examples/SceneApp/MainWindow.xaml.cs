using System;
using System.Numerics;
using System.Windows;
using System.Windows.Threading;
using Termin.Native;

namespace SceneApp;

public partial class MainWindow : Window
{
    private Scene? _scene;
    private TcEntityId _selectedEntityId;

    // Shared resources
    private TcShaderHandle _defaultShader;
    private TcMaterialHandle _defaultMaterial;
    private bool _resourcesCreated;
    private readonly bool _smokeMode =
        Array.Exists(Environment.GetCommandLineArgs(), arg => arg == "--smoke");
    private DispatcherTimer? _smokeTimeout;
    private int _smokeFrames;

    public MainWindow()
    {
        InitializeComponent();
        SceneViewer.NativeReady += OnNativeReady;
        Closed += OnClosed;
    }

    private void OnNativeReady(object? sender, EventArgs e)
    {
        CreateNewScene();
        if (_smokeMode)
        {
            Left = -20000;
            Top = -20000;
            ShowInTaskbar = false;
            SceneViewer.RenderFrame += OnSmokeRenderFrame;
            AddCube_Click(this, new RoutedEventArgs());
            _smokeTimeout = new DispatcherTimer
            {
                Interval = TimeSpan.FromSeconds(15),
            };
            _smokeTimeout.Tick += OnSmokeTimeout;
            _smokeTimeout.Start();
        }
    }

    private void OnClosed(object? sender, EventArgs e)
    {
        SceneViewer.NativeReady -= OnNativeReady;
        SceneViewer.RenderFrame -= OnSmokeRenderFrame;
        _smokeTimeout?.Stop();
        SceneViewer.Scene = null;
        _scene?.Dispose();
        _scene = null;
        SceneViewer.Dispose();
    }

    private void OnSmokeRenderFrame(object? sender, EventArgs e)
    {
        if (++_smokeFrames < 30)
        {
            return;
        }
        Console.WriteLine(
            $"SCENEAPP_D3D11_SMOKE_OK frames={_smokeFrames} " +
            $"control_dips={SceneViewer.ActualWidth}x{SceneViewer.ActualHeight}");
        Close();
    }

    private void OnSmokeTimeout(object? sender, EventArgs e)
    {
        Console.Error.WriteLine(
            $"SCENEAPP_D3D11_SMOKE_FAILED timeout frames={_smokeFrames}");
        Environment.ExitCode = 1;
        Close();
    }

    private void CreateNewScene()
    {
        _scene?.Dispose();

        _scene = new Scene();
        SceneViewer.Scene = _scene;
        HierarchyPanel.Scene = _scene;

        // Add default entity
        var root = _scene.Entities.CreateEntity("Root");
        root.Position = Vector3.Zero;

        RefreshUI();
        StatusText.Text = "New scene created";
    }

    private void CreateResources()
    {
        if (_resourcesCreated) return;

        _defaultShader = TerminCore.Tgfx2RegisterBuiltinShader(
            "termin-runtime-default-color");
        if (_defaultShader.Index != 0xFFFFFFFF)
        {
            Console.WriteLine($"[SceneApp] Shader registered: {_defaultShader.Index}:{_defaultShader.Generation}");
        }
        else
        {
            Console.WriteLine("[SceneApp] ERROR: Failed to create shader");
        }

        // Create material with opaque phase
        _defaultMaterial = TerminCore.MaterialCreate(null, "DefaultMaterial");
        var matPtr = TerminCore.MaterialGet(_defaultMaterial);
        if (matPtr != IntPtr.Zero)
        {
            TerminCore.MaterialAddPhase(matPtr, _defaultShader, "opaque", 0);
            TerminCore.MaterialSetColor(matPtr, 0.7f, 0.5f, 0.3f, 1.0f);
            Console.WriteLine($"[SceneApp] Material created: {_defaultMaterial.Index}:{_defaultMaterial.Generation}");
        }
        else
        {
            Console.WriteLine("[SceneApp] ERROR: Failed to get material pointer");
        }

        _resourcesCreated = true;
    }

    private void NewScene_Click(object sender, RoutedEventArgs e)
    {
        CreateNewScene();
    }

    private void AddCube_Click(object sender, RoutedEventArgs e)
    {
        if (_scene == null) return;

        // Create resources on first use (after GL is initialized)
        CreateResources();

        var entity = _scene.Entities.CreateEntity($"Cube_{_scene.Entities.Count}");
        entity.Position = GetRandomPosition();

        // Add MeshComponent with cube and MeshRenderer with material
        var meshComponent = entity.AddComponentByName("MeshComponent");
        var meshRenderer = entity.AddComponentByName("MeshRenderer");
        if (meshComponent.IsValid && meshRenderer.IsValid)
        {
            var cubeMesh = TerminCore.PrimitiveUnitCube();
            Console.WriteLine($"[SceneApp] PrimitiveUnitCube: {cubeMesh.Index}:{cubeMesh.Generation}");

            // Debug mesh
            var meshPtr = TerminCore.MeshGet(cubeMesh);
            Console.WriteLine($"[SceneApp] Mesh ptr: 0x{meshPtr:X}");

            meshComponent.SetField("mesh", cubeMesh);
            meshRenderer.SetField("material", _defaultMaterial);
            Console.WriteLine($"[SceneApp] MeshRenderer: mesh={cubeMesh.Index}:{cubeMesh.Generation}, mat={_defaultMaterial.Index}:{_defaultMaterial.Generation}");
        }
        else
        {
            Console.WriteLine("[SceneApp] ERROR: MeshRenderer component not valid");
        }

        RefreshUI();
        StatusText.Text = $"Added {entity.Name}";
    }

    private void AddSphere_Click(object sender, RoutedEventArgs e)
    {
        if (_scene == null) return;

        // Create resources on first use (after GL is initialized)
        CreateResources();

        var entity = _scene.Entities.CreateEntity($"Sphere_{_scene.Entities.Count}");
        entity.Position = GetRandomPosition();

        // Add MeshComponent with sphere and MeshRenderer with material
        var meshComponent = entity.AddComponentByName("MeshComponent");
        var meshRenderer = entity.AddComponentByName("MeshRenderer");
        if (meshComponent.IsValid && meshRenderer.IsValid)
        {
            var sphereMesh = TerminCore.PrimitiveUnitSphere();
            Console.WriteLine($"[SceneApp] PrimitiveUnitSphere: {sphereMesh.Index}:{sphereMesh.Generation}");
            meshComponent.SetField("mesh", sphereMesh);
            meshRenderer.SetField("material", _defaultMaterial);
            Console.WriteLine($"[SceneApp] MeshRenderer created for {entity.Name}");
        }
        else
        {
            Console.WriteLine("[SceneApp] ERROR: MeshRenderer component not valid");
        }

        RefreshUI();
        StatusText.Text = $"Added {entity.Name}";
    }

    private void AddEmpty_Click(object sender, RoutedEventArgs e)
    {
        if (_scene == null) return;

        var entity = _scene.Entities.CreateEntity($"Entity_{_scene.Entities.Count}");
        entity.Position = GetRandomPosition();

        RefreshUI();
        StatusText.Text = $"Added {entity.Name}";
    }

    private void Delete_Click(object sender, RoutedEventArgs e)
    {
        if (_scene == null || !_selectedEntityId.IsValid) return;

        var entity = _scene.Entities.GetEntity(_selectedEntityId);
        if (entity.IsValid)
        {
            var name = entity.Name;
            _scene.Entities.DeleteEntity(_selectedEntityId);
            _selectedEntityId = TcEntityId.Invalid;
            RefreshUI();
            StatusText.Text = $"Deleted {name}";
        }
    }

    private void ResetCamera_Click(object sender, RoutedEventArgs e)
    {
        SceneViewer.ResetCamera();
    }

    private void Hierarchy_SelectionChanged(object? sender, TcEntityId entityId)
    {
        _selectedEntityId = entityId;

        if (_scene != null && entityId.IsValid)
        {
            var entity = _scene.Entities.GetEntity(entityId);
            if (entity.IsValid)
            {
                InspectorPanel.SetEntity(_scene, entity);
                return;
            }
        }
        InspectorPanel.SetEntity(null, default);
    }

    private void RefreshUI()
    {
        HierarchyPanel.Refresh();
        EntityCountText.Text = $"Entities: {_scene?.Entities.Count ?? 0}";
    }

    private static Vector3 GetRandomPosition()
    {
        var rng = new Random();
        return new Vector3(
            (float)(rng.NextDouble() * 4 - 2),
            (float)(rng.NextDouble() * 4 - 2),
            (float)(rng.NextDouble() * 2)
        );
    }
}
