using UnityEngine;

class RecombinateTargetAbility : Ability
{
    public RecombinateTargetAbility() { }

    public override void UseOnObjectImpl(
        ObjectOfTimeline target_actor,
        ITimeline tl,
        IAbilityListPanel last_used_stamp
    )
    {
        var actor = last_used_stamp.Actor();
        var markpose = (target_actor as Actor).PromiseMarkPose();
        var markposition = markpose.ToPoint();
        var command = new RestoreReverseMarkCommand(
            markposition,
            target_actor.ObjectId(),
            tl.CurrentStep()
        );
        actor.AddExternalCommand(command);
    }
}
