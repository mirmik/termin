#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System.Linq;
using System;

class InterferenceAbility : Ability
{
    public InterferenceAbility() { }

    public override void UseSelfImpl(ITimeline tl, IAbilityListPanel last_used_stamp)
    {
        var _actor = last_used_stamp.Actor();
        if (!CanUse(tl, last_used_stamp))
            return;

        // InterferenceCommand command = new InterferenceCommand(_actor.LocalStep() + 1);
        // _actor.AddExternalCommand(command);
        // last_used_stamp.SetLastUsed(this.GetType(), _actor.LocalStep());
    }
}
