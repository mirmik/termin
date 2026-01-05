using UnityEngine;

class RecombinateMarkAbility : Ability
{
    public RecombinateMarkAbility() { }

    TimeDirection DirectionToMark(ObjectOfTimeline target_actor, ITimeline tl)
    {
        var mark = (target_actor as Actor).PromiseMarkTimelineStep();
        var current = tl.CurrentStep();
        return (mark > current) ? TimeDirection.Forward : TimeDirection.Backward;
    }

    public override void UseOnObjectImpl(
        ObjectOfTimeline target_actor,
        ITimeline tl,
        IAbilityListPanel last_used_stamp
    )
    {
        // long mark_timestamp = (target_actor as Actor).PromiseMarkTimelineStep();
        // long current_timestamp = tl.CurrentStep();
        // if (mark_timestamp < current_timestamp)

        var markpose = (target_actor as Actor).PromiseMarkPose();
        var actor = last_used_stamp.Actor();
        var command = new RestoreReverseMarkCommand(
            markpose.ToPoint(),
            target_actor.ObjectId(),
            tl.CurrentStep()
        );
        actor.AddExternalCommand(command);
    }
}
