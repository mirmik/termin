// using System.Collections;
// using System.Collections.Generic;
// using System;

// #if UNITY_64
// using UnityEngine;
// using UnityEngine.Rendering;
// #endif

// public class FOVCommandBuffer : MonoBehaviour
// {
//     public bool EnableOnStart = false;
//     public bool RenderHalf = true;
//     public Vector2Int Resolution;

//     public RenderTexture rt;
//     public RenderTexture rt_transparent;
//     CommandBuffer commandBuffer;
//     CommandBuffer commandBuffer_transparent;
//     bool _is_initialized = false;
//     Material solidMaterial;
//     Material tSolidMaterial;
//     bool _enabled = false;

//     float angle = 120;

//     MyList<MeshRenderer> mesh_renderers = new MyList<MeshRenderer>();
//     MyList<Material[]> shared_materials = new MyList<Material[]>();

//     MyList<MeshRenderer> trans_mesh_renderers = new MyList<MeshRenderer>();
//     MyList<Material[]> trans_shared_materials = new MyList<Material[]>();

//     Camera _camera;
//     RenderTargetIdentifier rtid;
//     RenderTargetIdentifier trans_rtid;

//     void Awake()
//     {
//         _camera = GetComponent<Camera>();

//         if (rt == null)
//         {
//             rt = new RenderTexture(Resolution.x, Resolution.y, 24, RenderTextureFormat.RFloat);
//             rt.filterMode = FilterMode.Bilinear;
//         }

//         if (rt_transparent == null)
//         {
//             rt_transparent = new RenderTexture(
//                 Resolution.x,
//                 Resolution.y,
//                 24,
//                 RenderTextureFormat.RFloat
//             );
//             rt_transparent.filterMode = FilterMode.Bilinear;
//         }

//         rtid = new RenderTargetIdentifier(rt);
//         trans_rtid = new RenderTargetIdentifier(rt_transparent);
//         commandBuffer = new CommandBuffer();
//         commandBuffer_transparent = new CommandBuffer();
//     }

//     void Start()
//     {
//         solidMaterial = new Material(MaterialKeeper.Instance.GetMaterial("FovSolid"));
//         tSolidMaterial = new Material(MaterialKeeper.Instance.GetMaterial("FovSolid"));
//     }

//     public RenderTexture GetFOVTexture()
//     {
//         return rt;
//     }

//     public RenderTexture GetFOVTextureHalf()
//     {
//         return rt_transparent;
//     }

//     public void CollectMeshRenderers()
//     {
//         var objs = GameObject.FindObjectsByType<GameObject>(FindObjectsSortMode.None);
//         mesh_renderers.Clear();
//         shared_materials.Clear();

//         foreach (var obj in objs)
//         {
//             var layer = obj.layer;
//             if (
//                 layer == 0
//                 || layer == 6
//                 || layer == 7
//                 || layer == (int)Layers.ACTOR_NON_TRANSPARENT_LAYER
//             )
//             {
//                 var renderer = obj.GetComponent<MeshRenderer>();
//                 if (renderer == null)
//                     continue;
//                 mesh_renderers.Add(renderer);
//             }
//         }

//         foreach (var renderer in mesh_renderers)
//         {
//             var materials = renderer.sharedMaterials;
//             shared_materials.Add(materials);
//         }
//     }

//     public void OnO()
//     {
//         commandBuffer.Clear();
//         commandBuffer.name = "FOV_CommandBuffer_" + gameObject.name;
//         commandBuffer.SetupCameraProperties(_camera);

//         commandBuffer.SetRenderTarget(rtid);
//         commandBuffer.ClearRenderTarget(true, true, Color.red, 1f);
//         for (int i = 0; i < mesh_renderers.Count; ++i)
//         {
//             var renderer = mesh_renderers[i];
//             var materials = shared_materials[i];
//             for (int j = 0; j < materials.Length; ++j)
//             {
//                 commandBuffer.DrawRenderer(renderer, solidMaterial, j);
//             }
//         }
//         _camera.AddCommandBuffer(CameraEvent.BeforeForwardOpaque, commandBuffer);
//     }

//     public void CollectMeshRenderersTransparent()
//     {
//         var objs = GameObject.FindObjectsByType<GameObject>(FindObjectsSortMode.None);
//         MyList<GameObject> transparent_objs = new MyList<GameObject>();
//         trans_mesh_renderers.Clear();
//         trans_shared_materials.Clear();

//         foreach (var obj in objs)
//         {
//             var layer = obj.layer;
//             if (layer == 14)
//                 transparent_objs.Add(obj);
//         }

//         foreach (var obj in transparent_objs)
//         {
//             var renderer = obj.GetComponent<MeshRenderer>();
//             if (renderer == null)
//                 continue;

//             trans_mesh_renderers.Add(renderer);
//         }

//         foreach (var renderer in trans_mesh_renderers)
//         {
//             var materials = renderer.sharedMaterials;
//             trans_shared_materials.Add(materials);
//         }
//     }

//     public void OnT()
//     {
//         commandBuffer_transparent.Clear();

//         commandBuffer_transparent.name = "FOV2_CommandBuffer_" + gameObject.name;
//         commandBuffer_transparent.SetupCameraProperties(_camera);

//         commandBuffer_transparent.SetRenderTarget(trans_rtid);
//         commandBuffer_transparent.ClearRenderTarget(true, true, Color.red, 1f);
//         for (int i = 0; i < trans_mesh_renderers.Count; ++i)
//         {
//             var renderer = trans_mesh_renderers[i];
//             var materials = trans_shared_materials[i];
//             for (int j = 0; j < materials.Length; ++j)
//             {
//                 commandBuffer_transparent.DrawRenderer(renderer, tSolidMaterial, j);
//             }
//         }

//         _camera.AddCommandBuffer(CameraEvent.BeforeForwardOpaque, commandBuffer_transparent);
//     }

//     public void DisableCommandBuffer()
//     {
//         if (!_enabled)
//             return;

//         _camera.RemoveCommandBuffer(CameraEvent.BeforeForwardOpaque, commandBuffer);

//         if (RenderHalf)
//             _camera.RemoveCommandBuffer(CameraEvent.BeforeForwardOpaque, commandBuffer_transparent);

//         _enabled = false;
//     }

//     public void EnableCommandBuffer()
//     {
//         if (_enabled)
//             return;

//         OnO();
//         if (RenderHalf)
//             OnT();
//         _enabled = true;
//         _camera.enabled = true;
//     }

//     public void SetAngle(float angle)
//     {
//         this.angle = angle;
//         _camera.fieldOfView = angle;
//     }

//     void Update()
//     {
//         if (!_is_initialized)
//         {
//             CollectMeshRenderers();
//             CollectMeshRenderersTransparent();

//             SetAngle(angle);
//             _is_initialized = true;
//             if (EnableOnStart)
//                 EnableCommandBuffer();
//         }
//     }
// }
