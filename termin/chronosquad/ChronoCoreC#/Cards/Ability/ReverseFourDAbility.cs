#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System.Linq;
using System;

class ReverseFourDAbility : Ability
{
    public ReverseFourDAbility() { }

    // bool HasLinked(IAbilityListPanel last_used_stamp)
    // {
    // 	var _actor = last_used_stamp.Actor();
    // 	return _actor.LinkedInTimeWithName() != null;
    // }

    public override void UseSelfImpl(ITimeline itl, IAbilityListPanel last_used_stamp)
    {
        Timeline tl = itl as Timeline;
        var ntc = tl; //tl.Copy();

        var chronosphere = tl.GetChronoSphere();
        var actor_id = last_used_stamp.Actor().ObjectId();
        var actor = ntc.GetActor(actor_id);
        var copy = actor.TearWithReverse();

        //ntc.SetReversedPass(true);

        bool timeline_if_reversed = tl.IsReversedPass();
        //if (active_is_reversed == timeline_if_reversed)
        //{
        chronosphere.TimeReverseImmediate();
        ntc.SetReversedPass(!tl.IsReversedPass());
        //}

        ntc.SetCurrentTimeline();
        ntc.DropLastTimelineStep();

        chronosphere.Select(copy);
    }
}
