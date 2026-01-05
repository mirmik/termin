using System.Collections;
using System.Collections.Generic;
#if UNITY_64
using UnityEngine;
using UnityEngine.Rendering;
#endif

//[ExecuteInEditMode]
public class CustomGlowRenderer : MonoBehaviour
{
    static CustomGlowRenderer m_Instance; // singleton

    public static CustomGlowRenderer instance
    {
        get { return m_Instance; }
    }

    RenderTexture depthNormalsTexture;
    public RenderTargetIdentifier depthNormalsTextureID;

    RenderTexture actor_rt;
    RenderTargetIdentifier actor_rtid;
    CommandBuffer commandBuffer;
    CommandBuffer nmcmdbuf_navmesh;
    RenderTexture rt_navmesh;
    CommandBuffer nmcmdbuf;
    Material find_sight_material;
    CommandBuffer commandBuffer_triplanar;
    CommandBuffer commandBuffer_depth_normals;

    CommandBuffer geometry_map_command_buffer;

    bool _is_initialized = false;
    bool _is_initialized2 = false;
    bool _is_initialized3 = false;

    public Shader glowShader;
    public Shader phantomShader;

    Camera _camera;

    public Shader PhantomShader()
    {
        return phantomShader;
    }

    public Shader GlowShader()
    {
        return glowShader;
    }

    void Awake()
    {
        m_Instance = this;
    }

    public Material GetNavMeshMaterial()
    {
        return find_sight_material;
    }

    void Start()
    {
        find_sight_material = new Material(MaterialKeeper.Instance.GetMaterial("FindSight"));
        _camera = GetComponent<Camera>();
        if (commandBuffer == null)
        {
            commandBuffer = new CommandBuffer();
        }

        if (commandBuffer_triplanar == null)
        {
            commandBuffer_triplanar = new CommandBuffer();
        }

        if (commandBuffer_depth_normals == null)
        {
            commandBuffer_depth_normals = new CommandBuffer();
        }

        actor_rt = new RenderTexture(Screen.width, Screen.height, 16);
        actor_rt.name = "GlowRT";
        actor_rt.filterMode = FilterMode.Point;
    }

    public RenderTexture GetTexture()
    {
        return actor_rt;
    }

    public void ResetCommandBuffer()
    {
        commandBuffer.Clear();
        var glowsys = CustomGlowSystem.instance;
        commandBuffer.name = "Glow";
        actor_rtid = new RenderTargetIdentifier(actor_rt);
        commandBuffer.SetRenderTarget(actor_rtid);
        commandBuffer.ClearRenderTarget(true, true, Color.black, 1f);

        var current_timeline = GameCore.GetChronosphereController().CurrentTimelineController();
        var list_for_timeline = glowsys.m_GlowObjs[current_timeline];
        foreach (var glowobj in list_for_timeline)
        {
            int layer = 0;
            try
            {
                layer = glowobj.obj.gameObject.layer;
            }
            catch (System.Exception)
            {
                continue;
            }

            if (layer != (int)Layers.ACTOR_LAYER)
                continue;

            var guard = glowobj.obj;
            if (!guard.GetObject().IsMaterial())
            {
                continue;
            }

            var glow_material = glowobj.GlowMaterial();
            foreach (Renderer renderer in glowobj.obj.Renderers())
            {
                commandBuffer.DrawRenderer(renderer, glow_material);
            }
        }

        if (!_is_initialized)
        {
            //_camera.AddCommandBuffer(CameraEvent.AfterForwardOpaque, commandBuffer);
            _is_initialized = true;
        }
    }

    public MyList<GameObject> FindAllObjectsWithWallsMaterial()
    {
        var walls = new MyList<GameObject>();
        var all_objects = GameObject.FindObjectsByType<GameObject>(FindObjectsSortMode.None);
        foreach (var obj in all_objects)
        {
            if (obj.layer != 0)
            {
                continue;
            }

            try
            {
                var renderer = obj.GetComponent<Renderer>();
                var material = renderer.material;
                if (material.shader.name == "Triplanar/Triplanar")
                {
                    walls.Add(obj);
                    //Debug.Log("Found wall: " + obj.name);
                }
            }
            catch (System.Exception)
            {
                //Debug.Log("Error: " + e.Message);
            }
        }
        return walls;
    }

    public void ResetCommandBufferTriplanar()
    {
        commandBuffer_triplanar.Clear();
        commandBuffer_triplanar.name = "TriplanarAddPath";
        //commandBuffer_triplanar.ClearRenderTarget(true, true, Color.black, 1f);

        var walls = FindAllObjectsWithWallsMaterial();

        foreach (var obj in walls)
        {
            var renderer = obj.GetComponent<Renderer>();
            var material = renderer.material;

            // get shader
            var shader = material.shader.name;
            if (shader != "Triplanar/Triplanar")
            {
                continue;
            }

            var add_material_shader = MaterialKeeper.Instance.GetShader("Triplanar/AddPath");
            var add_material = new Material(add_material_shader);
            commandBuffer_triplanar.DrawRenderer(renderer, add_material);
        }

        if (!_is_initialized2)
        {
            //_camera.AddCommandBuffer(CameraEvent.AfterForwardOpaque, commandBuffer_triplanar);
            _is_initialized2 = true;
        }
    }

    int _count = 0;

    void Update()
    {
        // По неизвестным причинам буффер не всегда отрабатывает на
        // первом кадре, поэтому ждём несколько кадров и запускаем его
        if (_count < 3)
        {
            _count++;
            return;
        }

        if (!_is_initialized)
        {
            ResetCommandBuffer();
        }

        if (!_is_initialized2)
        {
            ResetCommandBufferTriplanar();
            ResetMyDepthNormalsRenderer();
        }

        if (!_is_initialized3)
        {
            //ResetNavMeshBlurBuffer();

            ResetGeometryMapRenderer();

            //ResetZWriteBuffer();

            _is_initialized3 = true;

            // var path = "Assets/GeometryMaps/TestCube.png";

            // // load texture
            // var texture = new Texture2D(1024, 1024);
            // var bytes = System.IO.File.ReadAllBytes(path);
            // texture.LoadImage(bytes);

            // // set texture to gobj

            // var renderer = gobj.GetComponent<Renderer>();
            // renderer.material.mainTexture = texture;
        }

        // var gobj = GameObject.Find("TestCube");

        // var m = gobj.transform.localToWorldMatrix;
        // var s = gobj.transform.localScale;
        // Shader.SetGlobalMatrix("ModelMatrix", m);
        // Shader.SetGlobalVector("ModelScale", s);
    }

    public void ResetZWriteBuffer()
    {
        var zwrite_command_buffer = new CommandBuffer();
        zwrite_command_buffer.name = "ZWrite";
        var shader = MaterialKeeper.Instance.GetShader("ZWriteOnly");
        var zmaterial = new Material(shader);

        var all_objects = GameObject.FindObjectsByType<GameObject>(FindObjectsSortMode.None);
        foreach (var obj in all_objects)
        {
            if (obj.layer != 0)
            {
                continue;
            }

            try
            {
                var renderer = obj.GetComponent<Renderer>();
                var material = renderer.material;
                zwrite_command_buffer.DrawRenderer(renderer, zmaterial);
            }
            catch (System.Exception)
            {
                //Debug.Log("Error: " + e.Message);
            }
        }

        _camera.AddCommandBuffer(CameraEvent.AfterForwardOpaque, zwrite_command_buffer);
    }

    public void ResetNavMeshBlurBuffer()
    {
        nmcmdbuf = new CommandBuffer();
        nmcmdbuf_navmesh = new CommandBuffer();
        nmcmdbuf.name = "NavMeshBlur";
        nmcmdbuf_navmesh.name = "NavMeshBlurNavMesh";

        rt_navmesh = new RenderTexture(Screen.width, Screen.height, 16);
        RenderTargetIdentifier rtid = new RenderTargetIdentifier(rt_navmesh);
        nmcmdbuf_navmesh.SetRenderTarget(rtid);
        nmcmdbuf_navmesh.ClearRenderTarget(true, true, Color.black, 1f);

        // find gameobject with name NavMeshDrawObjectExperimental
        var navmesh_draw_object = GameObject.Find("NavMeshDrawObjectExperimental");

        var postprocess_material = MaterialKeeper.Instance.GetMaterial("NavMeshBlur");

        // draw navmesh
        if (navmesh_draw_object != null)
        {
            var renderer = navmesh_draw_object.GetComponent<Renderer>();

            nmcmdbuf_navmesh.DrawRenderer(renderer, find_sight_material);
        }

        nmcmdbuf.SetGlobalTexture("_RTex", rtid);
        nmcmdbuf.SetGlobalTexture("_ActorRTex", actor_rtid);
        nmcmdbuf.Blit(
            BuiltinRenderTextureType.CameraTarget,
            BuiltinRenderTextureType.CameraTarget,
            postprocess_material
        );
    }

    void ResetGeometryMapRenderer()
    {
        // var stub_rt = new RenderTexture(1024, 1024, 16);
        // var stub_rtid = new RenderTargetIdentifier(stub_rt);

        geometry_map_command_buffer = new CommandBuffer();
        geometry_map_command_buffer.name = "GeometryMap";

        var gobjs = GameObject.FindObjectsByType<GeometryMapController>(FindObjectsSortMode.None);
        foreach (var gobj in gobjs)
        {
            var stub_rt = new RenderTexture(1024, 1024, 0);
            var stub_rtid = new RenderTargetIdentifier(stub_rt);

            var geommap = gobj.GetComponent<GeometryMapController>();
            var scale = geommap.GetScale();
            var geommap_material = geommap.GeometryMapMaterial();
            var lattency_blitter_material = geommap.LattencyBlitterMaterial();
            var geommap_texture = geommap.GetTexture();

            var current_sight_rtid = geommap.CurrentSightRTID();
            var memory_rtid = geommap.MemoryRTID();

            geometry_map_command_buffer.Blit(geommap_texture, current_sight_rtid, geommap_material);
            geometry_map_command_buffer.Blit(
                memory_rtid,
                stub_rtid,
                new Material(MaterialKeeper.Instance.GetMaterial("StubPassMaterial"))
            );
            geometry_map_command_buffer.Blit(stub_rtid, memory_rtid, lattency_blitter_material);
        }

        //_camera.AddCommandBuffer(CameraEvent.AfterForwardAlpha, geometry_map_command_buffer);
    }

    void ResetMyDepthNormalsRenderer()
    {
        depthNormalsTexture = new RenderTexture(
            Screen.width,
            Screen.height,
            16,
            RenderTextureFormat.ARGBFloat
        );

        depthNormalsTextureID = new RenderTargetIdentifier(depthNormalsTexture);
        Shader.SetGlobalTexture("_MyDepthNormalsTexture", depthNormalsTexture);
        var shader = MaterialKeeper.Instance.GetShader("MyDepthNormalShader");
        var material = new Material(shader);

        commandBuffer_depth_normals.Clear();
        commandBuffer_depth_normals.name = "DepthNormals";
        commandBuffer_depth_normals.SetRenderTarget(depthNormalsTextureID);
        commandBuffer_depth_normals.ClearRenderTarget(true, true, new Color(0, 0, 0, 0), 1f);

        // get all scene objects

        GameObject[] allObjects = GameObject.FindObjectsOfType<GameObject>();
        foreach (var obj in allObjects)
        {
            var renderer = obj.GetComponent<Renderer>();
            if (renderer == null)
            {
                continue;
            }

            if (obj.layer != 0)
            {
                continue;
            }

            try
            {
                commandBuffer_depth_normals.DrawRenderer(renderer, material);
            }
            catch (System.Exception)
            {
                //Debug.Log("Error: " + e.Message);
            }
        }
        //_camera.AddCommandBuffer(CameraEvent.AfterForwardAlpha, commandBuffer_depth_normals);
    }
}
