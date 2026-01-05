#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System.Linq;
using System;

class HastAbility : Ability
{
    public HastAbility() { }

    public override void UseSelfImpl(ITimeline tl, IAbilityListPanel last_used_stamp)
    {
        var _actor = last_used_stamp.Actor();
        var cmd = new TimeModifierCommand(9, _actor.LocalStep() + 1);
        _actor.AddExternalCommand(cmd);
    }
}
