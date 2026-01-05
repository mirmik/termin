#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System.Linq;
using System;

class TrapSetupAbility : Ability
{
    float radius;

    public TrapSetupAbility(float radius)
    {
        this.radius = radius;
    }

    public override void UseOnObjectImpl(
        ObjectOfTimeline target_actor,
        ITimeline tl,
        IAbilityListPanel last_used_stamp
    )
    {
        var _actor = last_used_stamp.Actor();
        ShootCommand command = new ShootCommand(
            target_actor.ObjectId(),
            radius,
            _actor.LocalStep() + 1
        );
        _actor.AddExternalCommand(command);
    }
}
