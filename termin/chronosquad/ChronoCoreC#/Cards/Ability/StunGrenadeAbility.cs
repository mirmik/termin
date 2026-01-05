using UnityEngine;
using System.Collections.Generic;
using System.Linq;
using System;

// Кажется, тут должен быть стан

public class StunGrenadeAbility : Ability
{
    float effect_radius = 10;

    //float loud_radius = 10;
    //RestlessnessParameters restlessness;

    public StunGrenadeAbility() { }

    public StunGrenadeAbility(float effect_radius)
    {
        this.effect_radius = effect_radius;
    }

    public override void UseOnEnvironmentImpl(
        ReferencedPoint target,
        ITimeline tl,
        IAbilityListPanel last_used_stamp,
        PrivateParameters private_parameters = null
    )
    {
        ParabolicActionPrivateParameters throw_private_parameters =
            private_parameters as ParabolicActionPrivateParameters;

        long offset = (long)(Utility.GAME_GLOBAL_FREQUENCY * throw_private_parameters.time * 0.5f);

        tl.AddEvent(
            new CoinProjectileEvent(
                start_step: tl.CurrentStep() + 1,
                final_step: tl.CurrentStep()
                    + (long)(Utility.GAME_GLOBAL_FREQUENCY * throw_private_parameters.time * 0.5f),
                path: throw_private_parameters.path
            )
        );

        tl.AddEvent(
            new StunInRadiusEvent(
                step: offset + tl.CurrentStep() + 1,
                center: target,
                radius: effect_radius
            )
        );
    }
}
