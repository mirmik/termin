#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System.Linq;
using System;

class ParasiteAbility : Ability
{
    float _range = 1.0f;
    ParasiteMode _parasiteMode;

    public ParasiteAbility(float range, ParasiteMode parasiteMode)
    {
        //_range = range;
        _parasiteMode = parasiteMode;
    }

    public override void UseOnObjectImpl(
        ObjectOfTimeline target_actor,
        ITimeline tl,
        IAbilityListPanel last_used_stamp
    )
    {
        var _actor = last_used_stamp.Actor();
        ParasiteCommand command = new ParasiteCommand(
            target_actor.ObjectId(),
            WalkingType.Walk,
            _range,
            _actor.LocalStep() + 1,
            parasiteMode: _parasiteMode
        );
        _actor.AddExternalCommand(command);
    }
}
