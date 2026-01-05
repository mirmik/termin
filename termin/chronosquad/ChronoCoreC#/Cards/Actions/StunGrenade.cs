using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class StunGrenadeAction : ParabolicAction
{
    //public float DurationOfAttention = 3.0f;

    public StunGrenadeAction() : base(keycode: KeyCode.S) { }

    public override string TooltipText()
    {
        return "Станящая граната";
    }

    protected override Ability MakeAbility()
    {
        return new StunGrenadeAbility(effect_radius: EffectRadius);
    }

    protected override void ProgramEffectExtension(bool enable, Vector3 center)
    {
        _main_camera_shader_filter.ProgramRedCammeraEffect(enable, EffectRadius, center);
    }
}
