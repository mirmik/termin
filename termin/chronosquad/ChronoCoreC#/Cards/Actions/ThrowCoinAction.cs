using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class ThrowCoinAction : ParabolicAction
{
    public float DurationOfAttention = 3.0f;

    public ThrowCoinAction() : base(keycode: KeyCode.C) { }

    public override string TooltipText()
    {
        return "Бросить монетку";
    }

    protected override Ability MakeAbility()
    {
        return new ThrowCoinAbility(
            radius: LoudRadius,
            new RestlessnessParameters(duration_of_attention: DurationOfAttention, lures: false)
        );
    }

    protected override void ProgramEffectExtension(bool enable, Vector3 center) { }
}
