#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System.Linq;
using System;

public class HackAbility : Ability
{
    float _range = 1.0f;
    string _avatar_name;

    public HackAbility(float range, string avatar_name)
    {
        _range = range;
        _avatar_name = avatar_name;
    }

    public override bool CanUseAbility(ObjectOfTimeline target_actor)
    {
        var netpoint = target_actor.GetComponent<NetPoint>();
        if (netpoint == null)
            return false;
        return true;
    }

    public override void UseOnObjectImpl(
        ObjectOfTimeline target,
        ITimeline tl,
        IAbilityListPanel last_used_stamp
    )
    {
        var _actor = last_used_stamp.Actor();
        if (!CanUse(tl, last_used_stamp))
            return;

        HackCommand command = new HackCommand(
            target,
            WalkingType.Walk,
            _range,
            _actor.LocalStep(),
            HackCommandType.InjectAvatar,
            avatar_name: _avatar_name
        );
        _actor.AddExternalCommand(command);
    }
}
