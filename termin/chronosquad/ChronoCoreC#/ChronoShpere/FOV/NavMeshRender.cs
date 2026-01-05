using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class NavMeshRender : MonoBehaviour
{
    Material _material;
    Camera _fov_camera;

    //RenderTexture _renderTexture;
    GameObject _fov_tester;
    RenderTexture _fov_renderTexture;
    RenderTexture _fov_renderTextureHalf;
    FOVTesterController _fov_tester_controller;
    FOVManager _fov_manager;

    void Start()
    {
        _fov_tester = GameObject.Find("FOVTester");
        if (_fov_tester == null)
        {
            Debug.LogWarning("FOVTester not found");
            return;
        }

        _material = GetComponent<Renderer>().material;

        _fov_camera = _fov_tester.GetComponent<Camera>();
        Debug.Assert(_fov_camera != null, "FOVTester camera not found");

        _fov_tester_controller = _fov_tester.GetComponent<FOVTesterController>();
        Debug.Assert(_fov_tester_controller != null, "FOVTesterController not found");

        _fov_manager = _fov_tester.GetComponent<FOVManager>();
        Debug.Assert(_fov_manager != null, "FOVManager not found");

        _fov_renderTexture = _fov_manager.GetFOVTexture();
        _fov_renderTextureHalf = _fov_manager.GetFOVTextureHalf();
        _fov_renderTexture.filterMode = FilterMode.Point;
        _fov_renderTextureHalf.filterMode = FilterMode.Point;
    }

    void UpdateMaterial(Material material)
    {
        Matrix4x4 fovProjectionMatrix = _fov_camera.projectionMatrix;
        Matrix4x4 fovViewMatrix = _fov_camera.worldToCameraMatrix;
        Vector3 cameraPosition = _fov_camera.transform.position;
        int _sight_collection_size = SightCollection.Instance.Count();
        var distruct_level = _fov_tester_controller.DistructLevel();
        bool enabled = _fov_tester_controller.IsEnabled();
        material.SetInt("Enabled", enabled ? 1 : 0);
        material.SetInt("SightCollectionSize", _sight_collection_size);
        Shader.SetGlobalInt("SightCollectionSize", _sight_collection_size);

        if (_sight_collection_size >= 1)
        {
            Shader.SetGlobalTexture("Sight0", SightCollection.Instance.GetTexture(0));
            Shader.SetGlobalMatrix("Sight0_ViewMatrix", SightCollection.Instance.GetViewMatrix(0));
            Shader.SetGlobalMatrix("Sight0_ProjMatrix", SightCollection.Instance.GetProjMatrix(0));
            Shader.SetGlobalFloat("Sight0_Distance", SightCollection.Instance.GetDistance(0));
            Shader.SetGlobalVector(
                "Sight0_CameraPosition",
                SightCollection.Instance.GetPosition(0)
            );
        }

        if (_sight_collection_size >= 2)
        {
            Shader.SetGlobalTexture("Sight1", SightCollection.Instance.GetTexture(1));
            Shader.SetGlobalMatrix("Sight1_ViewMatrix", SightCollection.Instance.GetViewMatrix(1));
            Shader.SetGlobalMatrix("Sight1_ProjMatrix", SightCollection.Instance.GetProjMatrix(1));
            Shader.SetGlobalFloat("Sight1_Distance", SightCollection.Instance.GetDistance(1));
            Shader.SetGlobalVector(
                "Sight1_CameraPosition",
                SightCollection.Instance.GetPosition(1)
            );
        }

        if (_sight_collection_size >= 3)
        {
            Shader.SetGlobalTexture("Sight2", SightCollection.Instance.GetTexture(2));
            Shader.SetGlobalMatrix("Sight2_ViewMatrix", SightCollection.Instance.GetViewMatrix(2));
            Shader.SetGlobalMatrix("Sight2_ProjMatrix", SightCollection.Instance.GetProjMatrix(2));
            Shader.SetGlobalFloat("Sight2_Distance", SightCollection.Instance.GetDistance(2));
            Shader.SetGlobalVector(
                "Sight2_CameraPosition",
                SightCollection.Instance.GetPosition(2)
            );
        }

        if (_sight_collection_size >= 4)
        {
            Shader.SetGlobalTexture("Sight3", SightCollection.Instance.GetTexture(3));
            Shader.SetGlobalMatrix("Sight3_ViewMatrix", SightCollection.Instance.GetViewMatrix(3));
            Shader.SetGlobalMatrix("Sight3_ProjMatrix", SightCollection.Instance.GetProjMatrix(3));
            Shader.SetGlobalFloat("Sight3_Distance", SightCollection.Instance.GetDistance(3));
            Shader.SetGlobalVector(
                "Sight3_CameraPosition",
                SightCollection.Instance.GetPosition(3)
            );
        }

        if (_sight_collection_size >= 5)
        {
            Shader.SetGlobalTexture("Sight4", SightCollection.Instance.GetTexture(4));
            Shader.SetGlobalMatrix("Sight4_ViewMatrix", SightCollection.Instance.GetViewMatrix(4));
            Shader.SetGlobalMatrix("Sight4_ProjMatrix", SightCollection.Instance.GetProjMatrix(4));
            Shader.SetGlobalFloat("Sight4_Distance", SightCollection.Instance.GetDistance(4));
            Shader.SetGlobalVector(
                "Sight4_CameraPosition",
                SightCollection.Instance.GetPosition(4)
            );
        }

        material.SetTexture("FovTex2", _fov_renderTexture);
        material.SetTexture("FovTex2_transparent", _fov_renderTextureHalf);
        material.SetVector("CameraPosition", cameraPosition);
        material.SetMatrix("FovViewMatrix", fovViewMatrix);
        material.SetMatrix("FovProjMatrix", fovProjectionMatrix);
        material.SetFloat("DistrunctDistance", distruct_level.level);
        material.SetFloat(
            "DistrunctRedViolet",
            distruct_level.type == DistructStateEnum.Red ? 1
                : distruct_level.type == DistructStateEnum.Violet ? 2
                : 0
        );

        material.SetFloat("FovSightDistance", _fov_tester_controller.GetDistance());
    }

    void Update()
    {
        if (_fov_camera == null)
        {
            return;
        }

        UpdateMaterial(_material);
        UpdateMaterial(CustomGlowRenderer.instance.GetNavMeshMaterial());
    }

    // Dictionary<GameObject, RenderTexture> sight_textures;

    // public void RegisterHeroTexture(GameObject go, RenderTexture rt)
    // {
    // 	sight_textures.Add(go, rt);
    // }
}
