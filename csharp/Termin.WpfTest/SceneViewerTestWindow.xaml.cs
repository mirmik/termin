using System;
using System.Windows;
using Termin.Native;

namespace Termin.WpfTest
{
    public partial class SceneViewerTestWindow : Window
    {
        private Scene? _scene;
        private int _entityCount;

        // Resources
        private TcMeshHandle _cubeMesh;
        private TcMeshHandle _sphereMesh;
        private TcShaderHandle _shader;
        private TcMaterialHandle _material;
        private bool _resourcesCreated;

        public SceneViewerTestWindow()
        {
            InitializeComponent();

            Loaded += OnLoaded;
        }

        private void OnLoaded(object sender, RoutedEventArgs e)
        {
            // Create scene
            _scene = new Scene();
            SceneViewer.Scene = _scene;

            // Create resources after scene viewer is initialized
            CreateResources();

            // Add a default cube
            AddCube_Click(this, new RoutedEventArgs());
        }

        private unsafe void CreateResources()
        {
            if (_resourcesCreated) return;

            // Get shared unit primitives from registry
            _cubeMesh = TerminCore.PrimitiveUnitCube();
            _sphereMesh = TerminCore.PrimitiveUnitSphere();

            // Create simple shader
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

            _shader = TerminCore.ShaderFromSources(vertexShader, fragmentShader, null, "SimpleShader", null, null);
            var shaderPtr = TerminCore.ShaderGet(_shader);
            if (shaderPtr != IntPtr.Zero)
            {
                TerminCore.ShaderCompileGpu(shaderPtr);
            }

            // Create material
            _material = TerminCore.MaterialCreate(null, "SimpleMaterial");
            var matPtr = TerminCore.MaterialGet(_material);
            if (matPtr != IntPtr.Zero)
            {
                TerminCore.MaterialAddPhase(matPtr, _shader, "opaque", 0);
                TerminCore.MaterialSetColor(matPtr, 0.7f, 0.5f, 0.3f, 1.0f);
            }

            _resourcesCreated = true;
        }

        private void AddCube_Click(object sender, RoutedEventArgs e)
        {
            if (_scene == null || !_resourcesCreated) return;

            var entity = _scene.Entities.CreateEntity($"Cube_{++_entityCount}");

            // Random position
            var rng = new Random();
            float x = (float)(rng.NextDouble() * 4 - 2);
            float y = (float)(rng.NextDouble() * 4 - 2);
            float z = (float)(rng.NextDouble() * 2);
            entity.Position = new System.Numerics.Vector3(x, y, z);

            // Add MeshRenderer
            var meshRenderer = entity.AddComponentByName("MeshRenderer");
            if (meshRenderer.IsValid)
            {
                meshRenderer.SetField("mesh", _cubeMesh);
                meshRenderer.SetField("material", _material);
            }
        }

        private void AddSphere_Click(object sender, RoutedEventArgs e)
        {
            if (_scene == null || !_resourcesCreated) return;

            var entity = _scene.Entities.CreateEntity($"Sphere_{++_entityCount}");

            // Random position
            var rng = new Random();
            float x = (float)(rng.NextDouble() * 4 - 2);
            float y = (float)(rng.NextDouble() * 4 - 2);
            float z = (float)(rng.NextDouble() * 2);
            entity.Position = new System.Numerics.Vector3(x, y, z);

            // Add MeshRenderer
            var meshRenderer = entity.AddComponentByName("MeshRenderer");
            if (meshRenderer.IsValid)
            {
                meshRenderer.SetField("mesh", _sphereMesh);
                meshRenderer.SetField("material", _material);
            }
        }

        private void ResetCamera_Click(object sender, RoutedEventArgs e)
        {
            SceneViewer.ResetCamera();
        }
    }
}
