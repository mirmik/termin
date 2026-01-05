using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class FOVTesterController : MonoBehaviour
{
    bool _enabled = false;
    ObjectController _object = null;
    FOVManager _manager = null;
    Camera _camera;

    public void Start()
    {
        _camera = GetComponent<Camera>();
        _manager = GetComponent<FOVManager>();

        Debug.Assert(_camera != null);
        Debug.Assert(_manager != null);
    }

    public void Enable(bool enabled = true)
    {
        _enabled = enabled;
    }

    public void Disable()
    {
        _enabled = false;
    }

    public bool IsEnabled()
    {
        return _enabled;
    }

    public float GetDistance()
    {
        if (_object == null)
            return 0;
        return _object.GetSightDistance();
    }

    void SetObject(ObjectController obj)
    {
        _object = obj;
    }

    public string ObjectName()
    {
        if (_object == null)
            return "null";
        return _object.name;
    }

    public void AttachTo(GameObject actor)
    {
        var objctr = actor.GetComponent<ObjectController>();

        bool is_hero = objctr.GetObject().IsHero();
        if (is_hero)
            return;

        bool has_field_of_view = objctr.HasFieldOfView();
        if (!has_field_of_view)
        {
            return;
        }

        if (_object == objctr)
        {
            // Отключить камеру
            transform.parent = null;
            transform.position = new Vector3(0, -100, 0);
            transform.rotation = Quaternion.identity;
            Disable();
            _manager.EnableFOV(false);
            SetObject(null);
            return;
        }

        Enable();
        _manager.EnableFOV(true);
        SetObject(objctr);
    }

    public void ProgramAttachTo(GameObject actor)
    {
        var guard_view = actor.GetComponent<ObjectController>();
        bool is_hero = guard_view.GetObject().IsHero();
        if (is_hero)
            return;
        Enable();
        _manager.EnableFOV(true);
        SetObject(guard_view);
    }

    public DistructStatus DistructLevel()
    {
        if (_object == null)
            return new DistructStatus(0, DistructStateEnum.Green);

        return _object.DistructLevel();
    }

    void UpdateAngle()
    {
        var obj = _object.GetObject();
        var sa = obj.SightAngle();

        //_angle = angle;
        _camera.fieldOfView = sa;
    }

    void Update()
    {
        if (_object == null)
            return;

        var obj = _object.GetObject();
        bool hide = _object.IsNeedHide(obj);

        if ((obj.IsDead || obj.IsPreDead || hide) && _enabled)
            Disable();

        if (!obj.IsDead && !obj.IsPreDead && !hide && !_enabled)
            Enable();

        var pos = obj.CameraPose();

        UpdateAngle();

        transform.position = pos.position;
        transform.rotation = pos.rotation;
    }
}
