using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class ExplosionGrenadeAction : ParabolicAction
{
    public float DurationOfAttention = 3.0f;

    public ExplosionGrenadeAction() : base(keycode: KeyCode.G) { }

    public override string TooltipText()
    {
        return "Бросить гранату";
    }

    protected override Ability MakeAbility()
    {
        return new GrenadeAbility(
            loud_radius: LoudRadius,
            effect_radius: EffectRadius,
            new RestlessnessParameters(duration_of_attention: DurationOfAttention, lures: false)
        );
    }

    protected override void ProgramEffectExtension(bool enable, Vector3 center)
    {
        _main_camera_shader_filter.ProgramRedCammeraEffect(enable, EffectRadius, center);
    }
}
