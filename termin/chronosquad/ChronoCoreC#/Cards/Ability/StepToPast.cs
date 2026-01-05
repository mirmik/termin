#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System.Linq;
using System;

class StepToPastAbility : Ability
{
    long _distance;

    public StepToPastAbility() { }

    public StepToPastAbility(float time_distance)
    {
        _distance = -(long)(time_distance * Utility.GAME_GLOBAL_FREQUENCY);
    }

    private void CreateNewTimeline(ObjectOfTimeline target_actor, ITimeline ttl)
    {
        var tl = ttl as Timeline;
        Action act = () =>
        {
            var chronosphere = tl.GetChronoSphere();
            var ntl = tl.Copy();
            chronosphere.AddTimeline(ntl);
            ntl.Promote(tl.CurrentStep() + _distance);
            ntl.DropTimelineToCurrentState();

            var nguard = target_actor.Copy(ntl);
            nguard.SetName(nguard.Name() + "_paststep" + UniqueIdGenerator.GetNextId());
            ntl.AddObject(nguard);
            nguard.SetObjectTimeReferencePoint(
                ntl.CurrentStep(),
                target_actor.IsReversed(),
                offset: _distance
            );
            var ev = new AnigilationEvent(ntl.CurrentStep(), nguard.Name(), reversed: true);
            ntl.AddNonDropableEvent(ev);
            ntl.SetCurrentTimeline();
        };
        tl.AddAfterStepUpdateAction(act);
    }

    // TODO: Здесь явно что-то не так с отменой события. Возможно, надо проанализировать поведение реверса и сделать
    // по аналогии

    public override void UseSelfImpl(ITimeline tl, IAbilityListPanel last_used_stamp)
    {
        var _actor = last_used_stamp.Actor();
        AnigilationCommand command = new AnigilationCommand(_actor.LocalStep());
        _actor.AddExternalCommand(command);

        // var ev = new AnigilationEvent(
        //     step: tl.CurrentStep(),
        //     object_name: _actor.Name(),
        //     reversed: false
        // );
        // tl.AddEvent(ev);

        CreateNewTimeline(_actor, tl);
    }
}
