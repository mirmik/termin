#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System.Linq;
using System;

class PermanentStunAbility : Ability
{
    float shoot_distance = 10;

    public PermanentStunAbility(float shoot_distance)
    {
        this.shoot_distance = shoot_distance;
    }

    public override void UseOnObjectImpl(
        ObjectOfTimeline target_actor,
        ITimeline tl,
        IAbilityListPanel last_used_stamp
    )
    {
        var _actor = last_used_stamp.Object();
        if (!CanUse(tl, last_used_stamp))
            return;

        PermanentStunCommand command = new PermanentStunCommand(
            target_actor.ObjectId(),
            shoot_distance,
            _actor.LocalStep() + 1
        );
        _actor.AddExternalCommand(command);
        //last_used_stamp.SetLastUsed(this.GetType(), _actor.LocalStep());
    }
}
