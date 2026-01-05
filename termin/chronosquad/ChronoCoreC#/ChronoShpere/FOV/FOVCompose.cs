// using System.Collections;
// using System.Collections.Generic;
// using System;

// #if UNITY_64
// using UnityEngine;
// using UnityEngine.Rendering;
// #endif

// public class FOVCompose : MonoBehaviour
// {
// 	List<FOVCommandBuffer> buffers;
// 	public RenderTexture rt;
// 	RenderTargetIdentifier rtid ;
// 	CommandBuffer commandBuffer;
// 	Material solidMaterial;
// 	Camera _camera;
// 	public Vector2Int Resolution = new Vector2Int(1024, 4800);

// 	void Awake()
// 	{
// 		_camera = GetComponent<Camera>();
// 		var objs = GameObject.FindObjectsByType<FOVCommandBuffer>();
// 		foreach (var obj in objs) {
// 			var fov_test_controller = obj.GetComponent<FOVTesterController>();
// 			if (fov_test_controller != null)
// 				continue;
// 			buffers.Add(obj);
// 		}

// 		if ( rt == null)
// 		{
// 			rt = new RenderTexture(
// 				Resolution.x * Count,
// 				Resolution.y,
// 				24,
// 				RenderTextureFormat.RFloat);
// 			rt.filterMode = FilterMode.Bilinear;
// 		}

// 		rtid = new RenderTargetIdentifier(rt);
// 		commandBuffer = new CommandBuffer();
// 	}

// 	int Count => buffers.Count;

// 	public void CreateBuffer()
// 	{
// 		commandBuffer.Clear();
// 		commandBuffer.name = "FOV";
// 		commandBuffer.SetRenderTarget(rtid);
// 		commandBuffer.ClearRenderTarget(true, true, Color.red, 1f);
// 		//commandBuffer.SetupCameraProperties(_camera);

// 		commandBuffer.SetViewProjectionMatrices(
// 			_camera.worldToCameraMatrix,
// 			_camera.projectionMatrix);

// 		for (int i = 0; i < mesh_renderers.Count; ++i)
// 		{
// 			var renderer = mesh_renderers[i];
// 			var materials = shared_materials[i];
// 			for (int j = 0; j < materials.Length; ++j)
// 			{
// 				commandBuffer.DrawRenderer(renderer, solidMaterial, j);
// 			}
// 		}
// 		//_camera.AddCommandBuffer(CameraEvent.BeforeForwardOpaque, commandBuffer);
// 	}
// }
