using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

public class FOVRenderPass : ScriptableRenderPass
{
    private RenderTargetIdentifier destination;
    private Material material;
    private List<MeshRenderer> meshRenderers;
    private List<Material[]> sharedMaterials;
    private string profilerTag;

    public void Setup(
        List<MeshRenderer> meshRenderers,
        List<Material[]> sharedMaterials,
        Material material,
        RenderTargetIdentifier destination,
        string profilerTag = "FOVRenderPass"
    )
    {
        this.meshRenderers = meshRenderers;
        this.sharedMaterials = sharedMaterials;
        this.material = material;
        this.destination = destination;
        this.profilerTag = profilerTag;
    }

    public override void Execute(ScriptableRenderContext context, ref RenderingData renderingData)
    {
        if (meshRenderers == null || sharedMaterials == null || material == null)
            return;

        CommandBuffer cmd = CommandBufferPool.Get(profilerTag);
        cmd.SetRenderTarget(destination);
        cmd.ClearRenderTarget(true, true, Color.clear);

        for (int i = 0; i < meshRenderers.Count; ++i)
        {
            var renderer = meshRenderers[i];
            var materials = sharedMaterials[i];
            for (int j = 0; j < materials.Length; ++j)
            {
                cmd.DrawRenderer(renderer, material, j);
            }
        }

        context.ExecuteCommandBuffer(cmd);
        CommandBufferPool.Release(cmd);
    }
}
