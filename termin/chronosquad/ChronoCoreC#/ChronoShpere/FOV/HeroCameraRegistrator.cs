using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class HeroCameraRegistrator : MonoBehaviour
{
    //MainCameraShaderFilter _main_camera_shader_filter;
    FOVManager _fov_command_buffer;

    //SightCollection _sight_collection;
    Camera _camera;

    ObjectController _hero;

    bool _cached_fog_of_war = false;

    bool _is_enabled = false;

    void Start()
    {
        _fov_command_buffer = gameObject.GetComponent<FOVManager>();
        _camera = GetComponent<Camera>();
        _hero = gameObject.transform.parent.gameObject.GetComponent<ObjectController>();

        _hero.OnRemoveMe += Disable;

        _cached_fog_of_war = GameCore.GetChronosphereController().FogOfWar;
        if (_cached_fog_of_war == false)
        {
            gameObject.SetActive(false);
            return;
        }

        ShowSight();

        ChronosphereController.instance.FogOfWarChanged += SetFogOfWar;
    }

    public void SetFogOfWar(bool value)
    {
        _cached_fog_of_war = value;
        if (_cached_fog_of_war == false)
        {
            Disable();
        }
        else
        {
            ShowSight();
        }
    }

    public bool IsEnabled()
    {
        return _is_enabled;
    }

    // public void Enable()
    // {
    // 	//_fov_command_buffer.EnableCommandBuffer();
    // 	SightCollection.Instance.RegisterHeroTexture(
    // 		gameObject, _camera,
    // 		_fov_command_buffer.GetFOVTexture(),
    // 		this);
    // 	_is_enabled = true;
    // }

    public void Disable()
    {
        //_fov_command_buffer.DisableCommandBuffer();
        SightCollection.Instance.UnregisterHeroTexture(gameObject);
        _is_enabled = false;
    }

    public void ShowSight()
    {
        if (_cached_fog_of_war == false)
        {
            return;
        }

        var angle = _hero.SightAngle;
        //_fov_command_buffer.SetFOVAngle(angle);

        //var texture = _fov_command_buffer.GetFOVTexture();
        //SightCollection.Instance.RegisterHeroTexture(gameObject, _camera, texture, this);
        _is_enabled = true;
        //_fov_command_buffer.EnableCommandBuffer();
    }

    public float GetDistance()
    {
        return _hero.GetSightDistance();
    }
}
