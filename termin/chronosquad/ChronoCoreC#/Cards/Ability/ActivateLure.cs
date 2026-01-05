#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System.Linq;
using System;

class ActivateLureAbility : Ability
{
    public ActivateLureAbility() { }

    public override void UseSelfImpl(ITimeline tl, IAbilityListPanel last_used_stamp)
    {
        var _actor = last_used_stamp.Actor();
        var cmd = new SetupLureCommand(_actor.LocalStep() + 1, true);
        _actor.AddExternalCommand(cmd);
    }
}

class DeactivateLureAbility : Ability
{
    public DeactivateLureAbility() { }

    public override void UseSelfImpl(ITimeline tl, IAbilityListPanel last_used_stamp)
    {
        var _actor = last_used_stamp.Actor();
        var cmd = new SetupLureCommand(_actor.LocalStep() + 1, false);
        _actor.AddExternalCommand(cmd);
    }
}
