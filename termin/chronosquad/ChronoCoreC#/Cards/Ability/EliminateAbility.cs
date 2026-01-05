#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System.Linq;
using System;

class EliminateAbility : Ability
{
    public float animation_time = 1.0f;
    float _range;
    WalkingType walktype = WalkingType.Run;

    public EliminateAbility(float range)
    {
        _range = range;
    }

    public override void UseOnObjectImpl(
        ObjectOfTimeline target_actor,
        ITimeline tl,
        IAbilityListPanel last_used_stamp
    )
    {
        var _actor = last_used_stamp.Actor();
        EliminateCommand command = new EliminateCommand(
            target_actor.ObjectId(),
            walktype,
            _range,
            animation_time,
            _actor.LocalStep() + 1
        );
        _actor.AddExternalCommand(command);
    }
}
