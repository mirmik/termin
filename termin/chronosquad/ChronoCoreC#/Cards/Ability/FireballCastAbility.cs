#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System.Linq;
using System;

class FireballCastAbility : Ability
{
    float radius_of_sound = 2;
    float shoot_distance = 10;

    public FireballCastAbility(float shoot_distance)
    {
        this.shoot_distance = shoot_distance;
    }

    public override void UseOnEnvironmentImpl(
        ReferencedPoint target,
        ITimeline tl,
        IAbilityListPanel last_used_stamp,
        PrivateParameters private_parameters = null
    )
    {
        var _actor = last_used_stamp.Object();
        FireballCastCommand command = new FireballCastCommand(
            target,
            shoot_distance: shoot_distance,
            radius_of_sound: radius_of_sound,
            stamp: _actor.LocalStep() + 1
        );
        _actor.AddExternalCommand(command);
    }
}
