using System;
using System.Numerics;
using System.Windows;
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

    public MainWindow()
    {
        InitializeComponent();
        Loaded += OnLoaded;
        Closed += OnClosed;
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        CreateNewScene();
    }

    private void OnClosed(object? sender, EventArgs e)
    {
        _scene?.Dispose();
        _scene = null;
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

        // Simple shader
        string vertexShader = @"#version 330 core
layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec2 a_uv;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_normal;
out vec3 v_world_pos;

void main() {
    vec4 world_pos = u_model * vec4(a_position, 1.0);
    v_world_pos = world_pos.xyz;
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;
    gl_Position = u_projection * u_view * world_pos;
}";

        string fragmentShader = @"#version 330 core
in vec3 v_normal;
in vec3 v_world_pos;

uniform vec4 u_color;

out vec4 FragColor;

void main() {
    vec3 n = normalize(v_normal);
    vec3 light_dir = normalize(vec3(0.5, 0.8, 1.0));
    float ndotl = max(dot(n, light_dir), 0.0);
    float ambient = 0.3;
    float diffuse = 0.7 * ndotl;
    vec3 color = u_color.rgb * (ambient + diffuse);
    FragColor = vec4(color, u_color.a);
}";

        _defaultShader = TerminCore.ShaderFromSources(vertexShader, fragmentShader, null, "DefaultShader", null, null);
        var shaderPtr = TerminCore.ShaderGet(_defaultShader);
        if (shaderPtr != IntPtr.Zero)
        {
            TerminCore.ShaderCompileGpu(shaderPtr);
            Console.WriteLine($"[SceneApp] Shader compiled: {_defaultShader.Index}:{_defaultShader.Generation}");
        }
        else
        {
            Console.WriteLine("[SceneApp] ERROR: Failed to get shader pointer");
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

        // Add MeshRenderer with cube and material
        var meshRenderer = entity.AddComponentByName("MeshRenderer");
        if (meshRenderer.IsValid)
        {
            var cubeMesh = TerminCore.PrimitiveUnitCube();
            Console.WriteLine($"[SceneApp] PrimitiveUnitCube: {cubeMesh.Index}:{cubeMesh.Generation}");

            // Debug mesh
            var meshPtr = TerminCore.MeshGet(cubeMesh);
            Console.WriteLine($"[SceneApp] Mesh ptr: 0x{meshPtr:X}");

            meshRenderer.SetField("mesh", cubeMesh);
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

        // Add MeshRenderer with sphere and material
        var meshRenderer = entity.AddComponentByName("MeshRenderer");
        if (meshRenderer.IsValid)
        {
            var sphereMesh = TerminCore.PrimitiveUnitSphere();
            Console.WriteLine($"[SceneApp] PrimitiveUnitSphere: {sphereMesh.Index}:{sphereMesh.Generation}");
            meshRenderer.SetField("mesh", sphereMesh);
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
