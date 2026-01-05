using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.SceneManagement;

public class FOVRenderFeature : ScriptableRendererFeature
{
    private static FOVRenderFeature _instance;

    //private FOVRenderPass _absolutePass;
    //private FOVRenderPass _transparentPass;

    //RenderTargetIdentifier _absoluteTarget;
    //RenderTargetIdentifier _transparentTarget;

    //public FOVRenderPass AbsolutePass => _absolutePass;
    //public FOVRenderPass TransparentPass => _transparentPass;

    //public bool enabled = true;

    public static FOVRenderFeature Instance => _instance;
    public static Action OnCreate;

    FOVManager[] _fovManagers;

    public override void Create()
    {
        if (!Application.isPlaying)
            return;

        SceneManager.sceneLoaded += (scene, mode) =>
        {
            Clear();
        };

        SceneManager.sceneUnloaded += (scene) =>
        {
            Clear();
        };

        //Debug.Log("FOVRenderFeature.Create");
        _instance = this;

        OnCreate?.Invoke();
    }

    void Clear()
    {
        //_passes.Clear();
        _fovManagers = null;
    }

    public FOVManager[] FindAllFOVManagers()
    {
        return GameObject.FindObjectsOfType<FOVManager>();
    }

    public void ReInit()
    {
        _fovManagers = FindAllFOVManagers();
        //Debug.Log("FOVRenderFeature.ReInit " + _fovManagers.Length);

        // foreach (var fovManager in _fovManagers)
        // {
        //     bool en = fovManager.RenderEnabled;
        //     bool ten = fovManager.RenderHalfEnabled;

        //     if (en)
        //     {
        //         var pass = new FOVRenderPass();
        //         pass.renderPassEvent = RenderPassEvent.AfterRenderingOpaques;
        //         pass.SetupRender(fovManager.AbsoluteTarget, "AbsoluteFOVRenderPass");
        //         _passes.Add(pass);
        //     }

        //     if (ten)
        //     {
        //         var pass = new FOVRenderPass();
        //         pass.renderPassEvent = RenderPassEvent.AfterRenderingOpaques;
        //         pass.SetupRender(fovManager.TransparentTarget, "TransparentFOVRenderPass");
        //         _passes.Add(pass);
        //     }
        // }
    }

    public override void AddRenderPasses(
        ScriptableRenderer renderer,
        ref RenderingData renderingData
    )
    {
        if (!Application.isPlaying)
            return;

        if (_fovManagers == null)
            return;

        foreach (var manager in _fovManagers)
        {
            if (manager.RenderEnabled)
            {
                var pass = manager.AbsolutePass;
                pass.renderPassEvent = RenderPassEvent.AfterRenderingOpaques;
                renderer.EnqueuePass(pass);
            }

            if (manager.RenderHalfEnabled)
            {
                var pass = manager.TransparentPass;
                pass.renderPassEvent = RenderPassEvent.AfterRenderingOpaques;
                renderer.EnqueuePass(pass);
            }
        }
    }
}
