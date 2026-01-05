using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class SoundReverberationAction : ParabolicAction
{
    public float RadiusOfSound = 2.0f;
    public float ShootDistance = 10.0f;

    RestlessnessParameters noise_parameters = new RestlessnessParameters(
        duration_of_attention: 3.0f,
        lures: false
    );

    SoundReverberationAction() : base(KeyCode.C)
    {
        SetTrajectoryType(TrajectoryType.Straight);
    }

    protected override Ability MakeAbility()
    {
        var shoot_ability = new SoundReverberationAbility(
            radius_of_sound: RadiusOfSound,
            shoot_distance: ShootDistance,
            noise_parameters: noise_parameters
        );
        _actor.GetObject().AddAbility(shoot_ability);
        return shoot_ability;
    }

    public override string TooltipText()
    {
        return "Испускает направленный звуковой луч, привлекающий противника к определённой позиции";
    }
}
