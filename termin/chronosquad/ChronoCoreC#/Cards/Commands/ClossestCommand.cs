using System.Collections.Generic;
using System;

#if UNITY_64
using UnityEngine;
#endif

abstract public class ClosestCommand : MovingToObjectCommand // TODO: Нарушение логики наследования. Нужно переименовать?
{
    protected float _action_distance;

    //bool use_interaction_pose = false;

    public ClosestCommand(
        ObjectId target_actor,
        WalkingType walktype,
        float action_distance,
        long stamp,
        bool use_interaction_pose = false
    ) : base(target_actor, walktype, stamp, use_interaction_pose)
    {
        _action_distance = action_distance;
    }

    public abstract bool ActionPhase(ObjectOfTimeline actor, ITimeline timeline);
    public abstract bool IsActionStarted(ObjectOfTimeline actor);

    public bool IsCloseDistance(ObjectOfTimeline actor, ITimeline timeline)
    {
        var target_actor = TargetObject(timeline);
        var target_actor_position = target_actor.Position();
        var actor_position = actor.Position();
        var distance = Vector3.Distance(target_actor_position, actor_position);
        return distance < _action_distance;
    }

    public override bool Execute(ObjectOfTimeline actor, ITimeline timeline)
    {
        if (IsActionStarted(actor))
        {
            return ActionPhase(actor, timeline);
        }

        var current_animatronic = actor.CurrentAnimatronic();
        if (IsCloseDistance(actor, timeline) && current_animatronic.CanBeInterruptedForAction())
        {
            return ActionPhase(actor, timeline);
        }
        else
        {
            MovingPhase(actor, timeline);
            return false;
        }
    }
}
