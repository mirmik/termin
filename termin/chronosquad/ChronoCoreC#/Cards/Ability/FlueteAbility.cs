#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System.Linq;
using System;

class FlueteAbility : Ability
{
    float radius;

    public FlueteAbility(float radius)
    {
        this.radius = radius;
    }

    public override void UseOnEnvironmentImpl(
        ReferencedPoint target,
        ITimeline tl,
        IAbilityListPanel last_used_stamp,
        PrivateParameters private_parameters = null
    )
    {
        WalkingType walkingType = WalkingType.Walk;

        var _actor = last_used_stamp.Actor() as Actor;
        if (_actor.IsCroachControl())
        {
            walkingType = WalkingType.Croach;
        }

        FlueteCommand command = new FlueteCommand(
            target,
            _actor.LocalStep() + 1,
            radius,
            walking_type: walkingType
        );
        _actor.AddExternalCommand(command);
    }
}
