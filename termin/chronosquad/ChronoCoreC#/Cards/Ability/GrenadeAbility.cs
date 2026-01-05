#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System.Linq;
using System;

public class GrenadeAbility : Ability
{
    float effect_radius = 10;
    float loud_radius = 10;
    RestlessnessParameters restlessness;

    public GrenadeAbility() { }

    public GrenadeAbility(float loud_radius, float effect_radius, RestlessnessParameters retleness)
    {
        this.loud_radius = loud_radius;
        this.effect_radius = effect_radius;
        this.restlessness = retleness;
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
            new LoudSoundEvent(
                step: tl.CurrentStep() + offset,
                center: target,
                radius: loud_radius,
                noise_parameters: restlessness
            )
        );

        tl.AddEvent(
            new LoudSoundVisualEffect(
                start_step: tl.CurrentStep() + offset,
                finish_step: tl.CurrentStep()
                    + offset
                    + (long)(Utility.GAME_GLOBAL_FREQUENCY * 0.5f),
                position: target,
                maxRadius: loud_radius
            )
        );

        tl.AddEvent(
            new ExplosionEffectEvent(
                start_step: offset + tl.CurrentStep() + 1,
                position: target.GlobalPosition(tl)
            )
        );

        tl.AddEvent(
            new AudioEffect(
                start_step: offset + tl.CurrentStep() + 1,
                position: target.GlobalPosition(tl),
                "Explosion",
                1.0f
            )
        );

        tl.AddEvent(
            new ExplosionEvent(
                step: offset + tl.CurrentStep() + 1,
                center: target,
                radius: effect_radius
            )
        );
    }
}
