using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

public class FOVManager : MonoBehaviour
{
    public Material FOVMaterial;
    public Material FOVHalfMaterial;

    public bool RenderEnabled = true;
    public bool RenderHalfEnabled = true;

    //private FOVRenderFeature _fovFeature;

    public RenderTexture absoluteTexture;
    public RenderTexture transparentTexture;

    RenderTargetIdentifier _absoluteTarget;
    RenderTargetIdentifier _transparentTarget;

    FOVRenderPass _absolutePass;
    FOVRenderPass _transparentPass;

    //bool _inited = false;
    public static FOVManager Instance { get; private set; }

    public RenderTargetIdentifier AbsoluteTarget => _absoluteTarget;
    public RenderTargetIdentifier TransparentTarget => _transparentTarget;

    public FOVRenderPass AbsolutePass => _absolutePass;
    public FOVRenderPass TransparentPass => _transparentPass;

    void Awake()
    {
        Instance = this;
        CreateRenderTextures();

        _absolutePass = new FOVRenderPass();
        _transparentPass = new FOVRenderPass();
    }

    void Start()
    {
        PostStart();
    }

    FOVRenderFeature FindFOVRenderFeature()
    {
        return FOVRenderFeature.Instance;
    }

    public RenderTexture GetFOVTexture()
    {
        return absoluteTexture;
    }

    public RenderTexture GetFOVTextureHalf()
    {
        return transparentTexture;
    }

    void CreateRenderTextures()
    {
        if (absoluteTexture == null)
        {
            absoluteTexture = new RenderTexture(1024, 1024, 24, RenderTextureFormat.RFloat);
            absoluteTexture.filterMode = FilterMode.Bilinear;
            _absoluteTarget = new RenderTargetIdentifier(absoluteTexture);
        }

        if (transparentTexture == null)
        {
            transparentTexture = new RenderTexture(1024, 1024, 24, RenderTextureFormat.RFloat);
            transparentTexture.filterMode = FilterMode.Bilinear;
            _transparentTarget = new RenderTargetIdentifier(transparentTexture);
        }
    }

    public void GetFOVTextures(
        out RenderTargetIdentifier absoluteTexture,
        out RenderTargetIdentifier transparentTexture
    )
    {
        absoluteTexture = _absoluteTarget;
        transparentTexture = _transparentTarget;
    }

    public void PostStart()
    {
        SetupSceneObstacles();
    }

    public void EnableFOV(bool enabled = true)
    {
        RenderEnabled = enabled;
        RenderHalfEnabled = enabled;
    }

    void SetupSceneObstacles()
    {
        LayerMask mask = (1 << 0) | (1 << 6) | (1 << 7);
        var (meshRenderers, sharedMaterials) = CollectMeshRenderers(mask);

        LayerMask tmask = (1 << (int)Layers.HALF_OBSTACLES_LAYER);
        var (transparentMeshRenderers, transparentSharedMaterials) = CollectMeshRenderers(tmask);

        Debug.Log($"Count of FOV render: {meshRenderers.Count} {transparentMeshRenderers.Count}");

        AbsolutePass.Setup(
            meshRenderers,
            sharedMaterials,
            FOVMaterial,
            _absoluteTarget,
            "FOVAbsoluteRenderPass"
        );

        TransparentPass.Setup(
            transparentMeshRenderers,
            transparentSharedMaterials,
            FOVHalfMaterial,
            _transparentTarget,
            "FOVTransparentRenderPass"
        );
    }

    private (List<MeshRenderer>, List<Material[]>) CollectMeshRenderers(LayerMask mask)
    {
        var meshRenderers = new List<MeshRenderer>();
        var sharedMaterials = new List<Material[]>();
        var objs = GameObject.FindObjectsByType<GameObject>(FindObjectsSortMode.None);
        foreach (var obj in objs)
        {
            var layer = obj.layer;
            if ((mask & (1 << layer)) != 0)
            {
                var renderer = obj.GetComponent<MeshRenderer>();
                if (renderer == null)
                    continue;
                meshRenderers.Add(renderer);
                sharedMaterials.Add(renderer.sharedMaterials);
            }
        }
        return (meshRenderers, sharedMaterials);
    }

    // void Update()
    // {
    //     if (!_inited)
    //     {
    //         PostStart();
    //         _inited = true;
    //     }
    // }
}
