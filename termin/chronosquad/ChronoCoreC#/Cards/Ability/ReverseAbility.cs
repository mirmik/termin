#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System.Linq;
using System;

interface IBlindDraw
{
    void BlindDraw(long start_step, long finish_step, Vector3 position, Actor obj);
}

class ReverseAbility : Ability
{
    public ReverseAbility() { }

    bool HasLinked(IAbilityListPanel last_used_stamp)
    {
        var _actor = last_used_stamp.Actor();
        return _actor.LinkedInTimeWithName() != null;
    }

    public override void UseSelfImpl(ITimeline tl, IAbilityListPanel last_used_stamp)
    {
        var _actor = last_used_stamp.Actor();
        var cmd = new ReverseInTimeCommand(
            _actor.LocalStep(),
            _actor.IsReversed(),
            tl.CurrentStep(),
            _actor.Position()
        );

        var tl_direction = tl.IsReversedPass();
        var actor_direction = _actor.IsReversed();

        if (tl_direction == actor_direction)
            _actor.AddExternalCommand(cmd);
        else
            _actor.AddExternalCommandAndApplyFromReversePass(cmd);
    }
}
