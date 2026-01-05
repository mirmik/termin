using System.Collections;
using System.Collections.Generic;
using System;

#if UNITY_64
using UnityEngine;
#endif

public abstract class ThrowToEnvironmentCommand : MovingCommand
{
    public float shoot_distance;
    protected RestlessnessParameters noise_parameters;
    protected bool can_shoot_from_croach = false;

    public ThrowToEnvironmentCommand(
        ReferencedPoint target,
        float shoot_distance,
        long stamp,
        bool can_shoot_from_croach = false
    ) : base(target, WalkingType.Run, stamp: stamp, PathFindingTarget.Standart)
    {
        this.shoot_distance = shoot_distance;
        this.can_shoot_from_croach = can_shoot_from_croach;
    }

    void StartShootPhase(ObjectOfTimeline actor, ITimeline timeline)
    {
        var target_global = _target_position.GlobalPosition(timeline);
        var curstep = actor.LocalStep();

        bool croach = (actor as Actor).IsCroachControl() && can_shoot_from_croach;
        ShootAnimatronic punch = new ShootAnimatronic(
            start_step: curstep,
            finish_step: curstep + (long)Utility.GAME_GLOBAL_FREQUENCY * 1,
            pose: actor.CurrentReferencedPose(),
            direction: target_global - actor.position(),
            croach: croach
        );
        actor.SetNextAnimatronic(punch);
    }

    bool ShootPhase(ObjectOfTimeline actor, ITimeline timeline)
    {
        bool is_shoot_started = actor.CurrentAnimatronic() is ShootAnimatronic;

        if (!is_shoot_started)
        {
            StartShootPhase(actor, timeline);
            return false;
        }
        else
        {
            var start_local_time = actor.CurrentAnimatronic().StartStep;
            var current_local_time = actor.LocalStep();
            if (current_local_time - start_local_time > Utility.GAME_GLOBAL_FREQUENCY / 2)
            {
                AddEvents(actor, timeline);
                return true;
            }
            else
            {
                return false;
            }
        }
    }

    protected virtual void AddEvents(ObjectOfTimeline actor, ITimeline tl) { }

    public abstract bool IsTrajectoryClear(
        ObjectOfTimeline actor,
        ITimeline timeline,
        Vector3 target_global
    );

    public override bool Execute(ObjectOfTimeline actor, ITimeline timeline)
    {
        var current_position = actor.CurrentReferencedPosition();
        var target_global = _target_position.GlobalPosition(timeline);
        target_global += new Vector3(0, 0.5f, 0);

        if (IsTrajectoryClear(actor, timeline, target_global))
        {
            return ShootPhase(actor, timeline);
        }

        if (current_position.DistanceTo(_target_position, timeline) < 0.1f)
        {
            return true;
        }

        return false;
    }
}
