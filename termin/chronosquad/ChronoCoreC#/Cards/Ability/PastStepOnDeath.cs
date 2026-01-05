#if UNITY_64
using UnityEngine;
#endif

using System;

class PastStepOnDeath : Ability
{
    long distance;

    public PastStepOnDeath(long distance)
    {
        this.distance = distance;
    }

    public override void HookInstall(ObjectOfTimeline actor)
    {
        actor.SetDeadHook(Hook);
    }

    public bool Hook(string who_kill_me, ITimeline tl, IAbilityListPanel last_used_stamp)
    {
        var _actor = last_used_stamp.Actor();
        Action after_handler = () =>
        {
            var ntl = (_actor.GetTimeline() as Timeline).Copy();
            var actor_copy = ntl.GetActor(_actor.Name());
            var killer = ntl.GetActor(who_kill_me);
            ntl.Promote(ntl.CurrentStep() - distance);
            ntl.DropTimelineToCurrentState();
            actor_copy.HearNoise(
                ntl.CurrentStep(),
                killer.CurrentReferencedPosition(),
                new RestlessnessParameters(1.5f, lures: true)
            );

            var ability_copy = actor_copy.GetAbility<PastStepOnDeath>();
            ntl.SetCurrent();
        };

        (tl as Timeline).AddAfterStepUpdateAction(after_handler);
        return true;
    }
}
