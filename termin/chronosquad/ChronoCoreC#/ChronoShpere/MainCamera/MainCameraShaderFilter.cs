using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

public class MainCameraShaderFilter : MonoBehaviour
{
    public Material CameraMaterial;

    Camera _main_camera;
    CustomGlowRenderer _custom_glow_renderer;

    RedCircleShaderEffect redCircleShaderEffect = new RedCircleShaderEffect();

    float fov;
    float aspect;
    float nearClipPlane;
    float farClipPlane;
    float height = 1920.0f;
    float width = 1640.0f;

    float grid_radial_distance = 0.0f;
    float grid_multer_radial = 0.0f;
    float grid_multer_area = 0.0f;

    ChronoSphere _chronosphere;

    bool _blue_modifier_enabled = false;
    Vector3 _blue_modifier_center = new Vector3(0.0f, 0.0f, 0.0f);
    float _blue_modifier_radius = 0;
    float _blue_modifier_start_time = 0;

    // bool _red_modifier_enabled = false;
    // Vector3 _red_modifier_center = new Vector3(0.0f, 0.0f, 0.0f);
    // float _red_modifier_radius = 0;
    // float _red_modifier_start_time = 0;

    bool _zone_modifier_enabled = false;
    Vector3 _zone_modifier_center = new Vector3(0.0f, 0.0f, 0.0f);
    float _zone_modifier_radius = 0;
    float _zone_modifier_start_time = 0;

    public bool EnableVolumeFog = false;

    //Dictionary<GameObject, RenderTexture> sight_textures;

    // public void RegisterHeroTexture(GameObject go, RenderTexture rt)
    // {
    // 	sight_textures.Add(go, rt);
    // }

    public void CleanEffects()
    {
        redCircleShaderEffect.CleanEffects();
    }

    float CurrentTime()
    {
        return _chronosphere.CurrentTimeline().CurrentTime();
    }

    public void ProgramBlueCammeraEffect(bool enable, float radius, Vector3 center)
    {
        if (enable && _blue_modifier_enabled == false)
        {
            _blue_modifier_start_time = CurrentTime();
        }

        _blue_modifier_enabled = enable;
        _blue_modifier_center = center;
        _blue_modifier_radius = radius;
    }

    public void ProgramRedCammeraEffect(bool enable, float radius, Vector3 center)
    {
        redCircleShaderEffect.SetEnabled(enable);
        redCircleShaderEffect.SetupEffect(radius, center);
    }

    public void ProgramZoneCammeraEffect(bool enable, float radius, Vector3 center)
    {
        if (enable && _zone_modifier_enabled == false)
        {
            _zone_modifier_start_time = CurrentTime();
        }

        _zone_modifier_enabled = enable;
        _zone_modifier_center = center;
        _zone_modifier_radius = radius;
    }

    private void Awake()
    {
        _main_camera = GetComponent<Camera>();
        _main_camera.depthTextureMode = DepthTextureMode.DepthNormals;
        _custom_glow_renderer = GetComponent<CustomGlowRenderer>();

        // get camera fov angle and aspect ratio
        fov = _main_camera.fieldOfView;
        aspect = _main_camera.aspect;

        // distance from camera to near clip plane
        nearClipPlane = _main_camera.nearClipPlane;
        farClipPlane = _main_camera.farClipPlane;

        // clip zone width and height at near clip plane
        float height = 2.0f * Mathf.Tan(fov * 0.5f * Mathf.Deg2Rad) * nearClipPlane;
        float width = height * aspect;
    }

    // void LateUpdate()
    // {
    // }

    void Start()
    {
        _chronosphere = GameCore.Chronosphere();
    }

    void InitPauseModeIfNeeded(bool is_pause_mode)
    {
        if (is_pause_mode)
            return;

        grid_radial_distance = 0.0f;
        grid_multer_radial = 0.0f;
        grid_multer_area = 0.0f;
    }

    void RuntimeUpdate(bool is_pause_mode)
    {
        grid_radial_distance += Time.deltaTime * 100.0f;
        grid_multer_radial += Time.deltaTime * 1.5f;
        grid_multer_area += Time.deltaTime * 0.5f;

        grid_multer_radial = Mathf.Clamp(grid_multer_radial, 0.0f, 1.0f);
        grid_multer_area = Mathf.Clamp(grid_multer_area, 0.0f, 1.0f);
    }

    private void OnRenderImage(RenderTexture source, RenderTexture destination)
    {
        var glowTexture = _custom_glow_renderer.GetTexture();
        var cameraPosition = _main_camera.transform.position;
        float current_world_speed = _chronosphere.time_multiplier();
        bool is_pause_mode = _chronosphere.is_pause_mode();

        RuntimeUpdate(is_pause_mode);
        InitPauseModeIfNeeded(is_pause_mode);

        CameraMaterial.SetTexture("_GlowMap", glowTexture);
        CameraMaterial.SetFloat("_VolumetricFogEnabled", EnableVolumeFog ? 1.0f : 0.0f);
        CameraMaterial.SetInt("time_frozen", is_pause_mode ? 1 : 0);
        CameraMaterial.SetFloat("current_world_speed", current_world_speed);
        CameraMaterial.SetFloat("fov", fov);
        CameraMaterial.SetFloat("aspect", aspect);
        CameraMaterial.SetFloat("nearClipPlane", nearClipPlane);
        CameraMaterial.SetFloat("farClipPlane", _main_camera.farClipPlane);
        CameraMaterial.SetFloat("height", height);
        CameraMaterial.SetFloat("width", width);
        CameraMaterial.SetVector("cameraPosition", cameraPosition);
        CameraMaterial.SetFloat("grid_radial_distance", grid_radial_distance);
        CameraMaterial.SetFloat("grid_multer_radial", grid_multer_radial);
        CameraMaterial.SetFloat("grid_multer_area", grid_multer_area);

        Shader.SetGlobalVector("BlueModifierCenter", _blue_modifier_center);
        Shader.SetGlobalInt("BlueModifierEnabled", _blue_modifier_enabled ? 1 : 0);
        Shader.SetGlobalFloat("BlueModifierRadius", _blue_modifier_radius);
        Shader.SetGlobalFloat(
            "BlueModifierTimeFromStart",
            CurrentTime() - _blue_modifier_start_time
        );

        // Shader.SetGlobalVector("RedModifierCenter", _red_modifier_center);
        // Shader.SetGlobalInt("RedModifierEnabled", _red_modifier_enabled ? 1 : 0);
        // Shader.SetGlobalFloat("RedModifierRadius", _red_modifier_radius);
        // Shader.SetGlobalFloat("RedModifierTimeFromStart", CurrentTime() - _red_modifier_start_time);
        redCircleShaderEffect.OnRender();

        Shader.SetGlobalVector("ZoneModifierCenter", _zone_modifier_center);
        Shader.SetGlobalInt("ZoneModifierEnabled", _zone_modifier_enabled ? 1 : 0);
        Shader.SetGlobalFloat("ZoneModifierRadius", _zone_modifier_radius);
        Shader.SetGlobalFloat(
            "ZoneModifierTimeFromStart",
            CurrentTime() - _zone_modifier_start_time
        );

        Graphics.Blit(source, destination, CameraMaterial);

        CleanEffects();
    }
}
