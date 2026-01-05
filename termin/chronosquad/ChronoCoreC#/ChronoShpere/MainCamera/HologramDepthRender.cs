using System.Collections;
using System.Collections.Generic;
#if UNITY_64
using UnityEngine;
using UnityEngine.Rendering;
#endif

public class HologramDepthRender : MonoBehaviour
{
    Camera main_camera;
    CommandBuffer commandBuffer;

    RenderTexture holDepthTexture;
    Material material;

    int hologramLayer = 20;

    MyList<GameObject> hologramObjects = new MyList<GameObject>();

    void FindHologramObjects()
    {
        hologramObjects.Clear();
        foreach (var obj in GameObject.FindObjectsByType<GameObject>(FindObjectsSortMode.None))
        {
            if (obj.layer == hologramLayer)
            {
                hologramObjects.Add(obj);
            }
        }
    }

    CommandBuffer MakeCommandBuffer()
    {
        CommandBuffer commandBuffer = new CommandBuffer();
        commandBuffer.name = "HologramDepthRender";

        holDepthTexture = new RenderTexture(
            Screen.width,
            Screen.height,
            24,
            RenderTextureFormat.RFloat
        );
        commandBuffer.SetRenderTarget(holDepthTexture);
        commandBuffer.ClearRenderTarget(true, true, Color.black);
        commandBuffer.SetGlobalTexture("_HologramDepthTexture", holDepthTexture);

        foreach (var obj in hologramObjects)
        {
            var renderer = obj.GetComponent<Renderer>();
            if (renderer == null)
                continue;

            commandBuffer.DrawRenderer(renderer, material);
        }

        return commandBuffer;
    }

    // Start is called before the first frame update
    void Start()
    {
        material = new Material(MaterialKeeper.Instance.GetMaterial("DepthMaterial"));

        FindHologramObjects();
        main_camera = GetComponent<Camera>();
        commandBuffer = MakeCommandBuffer();
        //main_camera.AddCommandBuffer(CameraEvent.AfterDepthTexture, commandBuffer);
    }

    // Update is called once per frame
    void Update() { }
}
