#if UNITY_64
using UnityEngine;
#endif

using System;
using System.Collections.Generic;

public abstract class GameAction : MonoBehaviour
{
    [System.NonSerialized]
    protected GameObject _gun_renderer = null;

    [System.NonSerialized]
    protected LineRenderer _line_renderer = null;

    [System.NonSerialized]
    protected MainCameraShaderFilter _main_camera_shader_filter;

    public Material GunLineMaterial;
    protected float GunLineWidth = 0.1f;
    protected float LineWidth = 0.1f;

    public Texture2D icon;

    //public Activity _activity;

    public virtual void Init()
    //void Awake()
    {
        ManualAwake();
        //_activity = new Activity(icon);
    }

    public GameObject FindInChildOrCreate(string name)
    {
        var child = this.transform.Find(name);
        if (child == null)
        {
            child = new GameObject(name).transform;
            child.parent = this.transform;
            child.localPosition = Vector3.zero;
        }
        return child.gameObject;
    }

    public GameObject FindInChildOrCreate(string name, out bool founded)
    {
        var child = this.transform.Find(name);
        if (child == null)
        {
            child = new GameObject(name).transform;
            child.parent = this.transform;
            child.localPosition = Vector3.zero;
            founded = false;
        }
        else
        {
            founded = true;
        }
        return child.gameObject;
    }

    protected virtual void ManualAwake()
    {
        //	_actor = this.GetComponent<ObjectController>();
        _main_camera_shader_filter = Camera.main.GetComponent<MainCameraShaderFilter>();
    }

    protected virtual void ProgramEffectExtension(bool enable, Vector3 center) { }

    protected void DisableEffectRings()
    {
        ProgramBlueCammeraEffect(false, this.transform.position, 0);
        ProgramEffectExtension(false, this.transform.position);
    }

    protected void ProgramBlueCammeraEffect(bool enable, Vector3 center, float radius)
    {
        _main_camera_shader_filter.ProgramBlueCammeraEffect(enable, radius, center);
    }

    protected void ProgramZoneCammeraEffect(bool enable, Vector3 center, float radius)
    {
        _main_camera_shader_filter.ProgramZoneCammeraEffect(enable, radius, center);
    }

    protected void ClearEffects()
    {
        ProgramBlueCammeraEffect(false, this.transform.position, 0);
        ProgramEffectExtension(false, this.transform.position);
        ProgramZoneCammeraEffect(false, this.transform.position, 0);
    }

    protected void setup_renderer()
    {
        _gun_renderer = FindInChildOrCreate("Ability.GunRenderer");
        _line_renderer = _gun_renderer.GetOrAddComponent<LineRenderer>();
        _line_renderer.enabled = false;
        _line_renderer.material = GunLineMaterial;
        _line_renderer.startWidth = GunLineWidth;
        _line_renderer.endWidth = GunLineWidth;
    }

    public void SetGunLinePoints(MyList<Vector3> points)
    {
        if (points == null || points.Count == 0)
        {
            _line_renderer.positionCount = 0;
            _line_renderer.enabled = false;
            return;
        }

        _line_renderer.enabled = true;
        _line_renderer.startWidth = GunLineWidth;
        _line_renderer.endWidth = GunLineWidth;

        _line_renderer.positionCount = points.Count;
        _line_renderer.SetPositions(points.ToArray());
    }

    protected void setup_line_renderer()
    {
        setup_renderer();
    }

    public virtual bool CanUseOnObject(GameObject other)
    {
        return true;
    }

    virtual public float GetFillPercent()
    {
        return 100;
    }

    virtual public float CooldownTime()
    {
        return 0.0f;
    }

    public virtual void OnEnvironmentClick(ClickInformation click) { }

    public virtual void OnActorClick(GameObject actor, ClickInformation click) { }

    public virtual void OnIconClick() { }

    public virtual void Cancel() { }

    public virtual string TooltipText()
    {
        return "";
    }

    public virtual void UpdateActive() { }

    public virtual bool MouseScrollInterrupt()
    {
        return false;
    }
}
