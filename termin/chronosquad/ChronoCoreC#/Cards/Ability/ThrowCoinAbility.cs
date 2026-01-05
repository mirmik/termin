#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System.Linq;
using System;

// public interface IShootDrawer
// {
//     void DrawShoot(Vector3 to, long timeline_step, Actor actor);
// }

public class PrivateParameters { }

public class ParabolicActionPrivateParameters : PrivateParameters
{
    public ParabolicCurve3d path;
    public float time;

    public ParabolicActionPrivateParameters(ParabolicCurve3d path, float time)
    {
        this.path = path;
        this.time = time;
    }
}

public class ThrowCoinAbility : Ability
{
    float radius = 10;
    RestlessnessParameters noise_parameters;

    public ThrowCoinAbility() { }

    public ThrowCoinAbility(float radius, RestlessnessParameters noise_parameters)
    {
        this.radius = radius;
        this.noise_parameters = noise_parameters;
    }

    // public ShootAbility(string actor, float shoot_distance, IShootDrawer shoot_drawer)
    // {
    //     this.shoot_drawer = shoot_drawer;
    //     this.shoot_distance = shoot_distance;
    // }

    public override void UseOnEnvironmentImpl(
        ReferencedPoint target,
        ITimeline tl,
        IAbilityListPanel last_used_stamp,
        PrivateParameters private_parameters = null
    )
    {
        ParabolicActionPrivateParameters throw_coin_private_parameters =
            private_parameters as ParabolicActionPrivateParameters;

        var _actor = last_used_stamp.Actor();
        if (!CanUse(tl, last_used_stamp))
            return;

        var projev = new CoinProjectileEvent(
            start_step: tl.CurrentStep() + 1,
            final_step: tl.CurrentStep()
                + (long)(Utility.GAME_GLOBAL_FREQUENCY * throw_coin_private_parameters.time * 0.5f),
            path: throw_coin_private_parameters.path
        );
        tl.AddEvent(projev);

        long offset = (long)(
            Utility.GAME_GLOBAL_FREQUENCY * throw_coin_private_parameters.time * 0.5f
        );
        var ev = new LoudSoundEvent(
            step: tl.CurrentStep() + offset,
            center: target,
            radius: radius,
            noise_parameters: noise_parameters
        );
        tl.AddEvent(ev);

        var effect = new LoudSoundVisualEffect(
            start_step: tl.CurrentStep() + offset,
            finish_step: tl.CurrentStep() + offset + (long)(Utility.GAME_GLOBAL_FREQUENCY * 0.5f),
            position: target,
            maxRadius: radius
        );
        tl.AddEvent(effect);
    }

    public override void SetParameter(string name, float value)
    {
        if (name == "radius")
        {
            radius = value;
            return;
        }

        throw new Exception("Unknown parameter: " + name);
    }
}
