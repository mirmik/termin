#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System.Linq;
using System;

class RemoteRebootAbility : Ability
{
    float shoot_distance;

    public RemoteRebootAbility(float shoot_distance)
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

        RemoteRebootShootCommand command = new RemoteRebootShootCommand(
            target_actor.ObjectId(),
            shoot_distance,
            _actor.LocalStep() + 1,
            ignore_obstacles: false
        );
        _actor.AddExternalCommand(command);
    }
}
