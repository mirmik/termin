using UnityEngine;

public class UniqShaderEffect
{
    bool _locked = false;

    public void Lock()
    {
        _locked = true;
    }

    public void Unlock()
    {
        _locked = false;
    }

    public bool IsLocked()
    {
        return _locked;
    }

    protected static float CurrentTime()
    {
        return GameCore.Chronosphere().CurrentTimeline().CurrentTime();
    }
}

public class RedCircleShaderEffect : UniqShaderEffect
{
    bool enabled_on_this_cycle = false;
    bool _modifier_enabled = false;
    float _modifier_start_time;
    Vector3 _modifier_center;
    float _modifier_radius;

    public void SetEnabled(bool enable)
    {
        if (enable && _modifier_enabled == false)
        {
            _modifier_start_time = CurrentTime();
        }
        _modifier_enabled = enable;
    }

    public void SetupEffect(float radius, Vector3 center)
    {
        _modifier_center = center;
        _modifier_radius = radius;
        enabled_on_this_cycle = true;
    }

    public void OnRender()
    {
        Shader.SetGlobalVector("RedModifierCenter", _modifier_center);
        Shader.SetGlobalInt("RedModifierEnabled", enabled_on_this_cycle ? 1 : 0);
        Shader.SetGlobalFloat("RedModifierRadius", _modifier_radius);
        Shader.SetGlobalFloat("RedModifierTimeFromStart", CurrentTime() - _modifier_start_time);
    }

    public void CleanEffects()
    {
        enabled_on_this_cycle = false;
    }
}
