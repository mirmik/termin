#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System.Linq;
using System;

class DisguiseAbility : Ability
{
    float offset_time;

    public DisguiseAbility(float time)
    {
        offset_time = time;
    }

    public override void UseSelfImpl(ITimeline tl, IAbilityListPanel last_used_stamp)
    {
        var _actor = last_used_stamp.Actor();
        var cmd = new DisguiseCommand(_actor.LocalStep());
        _actor.AddExternalCommand(cmd);
    }
}
