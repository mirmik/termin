// using System.Collections;
// using System.Collections.Generic;
// using UnityEngine;
// using UnityEngine.Rendering;
// using UnityEngine.Rendering.Universal;

// public class FOVCommandBuffer : MonoBehaviour
// {
//     public bool EnableOnStart = false;
//     public bool RenderHalf = true;
//     public Vector2Int Resolution;

//     public RenderTexture Rt;
//     public RenderTexture RtTransparent;
//     private FOVRenderPass _fovRenderPass;
//     private FOVRenderPass _fovRenderPassTransparent;
//     private Material _solidMaterial;
//     private Material _tSolidMaterial;
//     private bool _isInitialized = false;
//     private bool _isEnabled = false;
//     private float _angle = 120;

//     private List<MeshRenderer> _meshRenderers = new List<MeshRenderer>();
//     private List<Material[]> _sharedMaterials = new List<Material[]>();

//     private List<MeshRenderer> _transMeshRenderers = new List<MeshRenderer>();
//     private List<Material[]> _transSharedMaterials = new List<Material[]>();

//     private Camera _camera;
//     private RenderTargetIdentifier _rtid;
//     private RenderTargetIdentifier _transRtid;

//     void Awake()
//     {
//         // _camera = GetComponent<Camera>();

//         if (Rt == null)
//         {
//             Rt = new RenderTexture(Resolution.x, Resolution.y, 24, RenderTextureFormat.RFloat);
//             Rt.filterMode = FilterMode.Bilinear;
//         }

//         if (RtTransparent == null)
//         {
//             RtTransparent = new RenderTexture(
//                 Resolution.x,
//                 Resolution.y,
//                 24,
//                 RenderTextureFormat.RFloat
//             );
//             RtTransparent.filterMode = FilterMode.Bilinear;
//         }

//         // _rtid = new RenderTargetIdentifier(Rt);
//         // _transRtid = new RenderTargetIdentifier(RtTransparent);

//         // _solidMaterial = new Material(MaterialKeeper.Instance.GetMaterial("FovSolid"));
//         // _tSolidMaterial = new Material(MaterialKeeper.Instance.GetMaterial("FovSolid"));

//         // _fovRenderPass = new FOVRenderPass();
//         // _fovRenderPassTransparent = new FOVRenderPass();
//     }

//     void Start()
//     {
//         // if (EnableOnStart)
//         // {
//         //     EnableCommandBuffer();
//         // }
//     }

//     public RenderTexture GetFOVTexture()
//     {
//         return Rt;
//     }

//     public RenderTexture GetFOVTextureHalf()
//     {
//         return RtTransparent;
//     }

//     public void CollectMeshRenderers()
//     {
//         // var objs = GameObject.FindObjectsByType<GameObject>(FindObjectsSortMode.None);
//         // _meshRenderers.Clear();
//         // _sharedMaterials.Clear();

//         // foreach (var obj in objs)
//         // {
//         //     var layer = obj.layer;
//         //     if (
//         //         layer == 0
//         //         || layer == 6
//         //         || layer == 7
//         //         || layer == (int)Layers.ACTOR_NON_TRANSPARENT_LAYER
//         //     )
//         //     {
//         //         var renderer = obj.GetComponent<MeshRenderer>();
//         //         if (renderer == null)
//         //             continue;
//         //         _meshRenderers.Add(renderer);
//         //     }
//         // }

//         // foreach (var renderer in _meshRenderers)
//         // {
//         //     var materials = renderer.sharedMaterials;
//         //     _sharedMaterials.Add(materials);
//         // }
//     }

//     public void OnO()
//     {
//         // _fovRenderPass.Setup(
//         //     _rtid,
//         //     _solidMaterial,
//         //     _meshRenderers,
//         //     _sharedMaterials,
//         //     "FOVRenderPass"
//         // );

//         // RenderPipelineManager.beginCameraRendering += ExecuteFOVRenderPass;
//     }

//     public void CollectMeshRenderersTransparent()
//     {
//         // var objs = GameObject.FindObjectsByType<GameObject>(FindObjectsSortMode.None);
//         // List<GameObject> transparentObjs = new List<GameObject>();
//         // _transMeshRenderers.Clear();
//         // _transSharedMaterials.Clear();

//         // foreach (var obj in objs)
//         // {
//         //     var layer = obj.layer;
//         //     if (layer == 14)
//         //         transparentObjs.Add(obj);
//         // }

//         // foreach (var obj in transparentObjs)
//         // {
//         //     var renderer = obj.GetComponent<MeshRenderer>();
//         //     if (renderer == null)
//         //         continue;

//         //     _transMeshRenderers.Add(renderer);
//         // }

//         // foreach (var renderer in _transMeshRenderers)
//         // {
//         //     var materials = renderer.sharedMaterials;
//         //     _transSharedMaterials.Add(materials);
//         // }
//     }

//     public void OnT()
//     {
//         // _fovRenderPassTransparent.Setup(
//         //     _transRtid,
//         //     _tSolidMaterial,
//         //     _transMeshRenderers,
//         //     _transSharedMaterials,
//         //     "FOVRenderPassTransparent"
//         // );

//         // RenderPipelineManager.beginCameraRendering += ExecuteFOVRenderPassTransparent;
//     }

//     public void DisableCommandBuffer()
//     {
//         // if (!_isEnabled)
//         //     return;

//         // RenderPipelineManager.beginCameraRendering -= ExecuteFOVRenderPass;
//         // if (RenderHalf)
//         //     RenderPipelineManager.beginCameraRendering -= ExecuteFOVRenderPassTransparent;

//         // _isEnabled = false;
//     }

//     public void EnableCommandBuffer()
//     {
//         // if (_isEnabled)
//         //     return;

//         // OnO();
//         // if (RenderHalf)
//         //     OnT();
//         // _isEnabled = true;
//         // _camera.enabled = true;
//     }

//     public void SetFOVAngle(float angle)
//     {
//         // _angle = angle;
//         // _camera.fieldOfView = angle;
//     }

//     void Update()
//     {
//         // if (!_isInitialized)
//         // {
//         //     CollectMeshRenderers();
//         //     CollectMeshRenderersTransparent();

//         //     SetFOVAngle(_angle);
//         //     _isInitialized = true;
//         //     if (EnableOnStart)
//         //         EnableCommandBuffer();
//         // }
//     }

//     private void ExecuteFOVRenderPass(ScriptableRenderContext context, Camera camera)
//     {
//         // if (camera == _camera)
//         // {
//         //     _fovRenderPass.Execute(
//         //         context,
//         //         ref camera.GetUniversalAdditionalCameraData().renderingData
//         //     );
//         // }
//         // else
//         // {
//         //     Debug.Log("camera != _camera");
//         // }
//     }

//     private void ExecuteFOVRenderPassTransparent(ScriptableRenderContext context, Camera camera)
//     {
//         // if (camera == _camera)
//         // {
//         //     _fovRenderPassTransparent.Execute(
//         //         context,
//         //         ref camera.GetUniversalAdditionalCameraData().renderingData
//         //     );
//         // }
//         // else
//         // {
//         //     Debug.Log("camera != _camera");
//         // }
//     }
// }
