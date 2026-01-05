using System.Collections.Generic;
using System;

#if UNITY_64
using UnityEngine;
#endif

public class ElliminateCommandState : CommandSpecificState
{
    public bool is_kill_phase_started = false;

    public ElliminateCommandState(bool is_kill_phase_started)
    {
        this.is_kill_phase_started = is_kill_phase_started;
    }
}

public class EliminateCommand : ClosestCommand
{
    float punch_time = 0.5f;

    public EliminateCommand(
        ObjectId target_actor,
        WalkingType walktype,
        float punch_distance,
        float punch_time,
        long stamp
    ) : base(target_actor, walktype, punch_distance, stamp)
    {
        this.punch_time = punch_time;
    }

    void StartEliminatePhase(ObjectOfTimeline actor, ITimeline timeline)
    {
        var target_actor = TargetObject(timeline);
        var curstep = actor.LocalStep();
        PunchAnimatronic punch = new PunchAnimatronic(
            start_step: curstep,
            finish_step: curstep + (long)(punch_time * Utility.GAME_GLOBAL_FREQUENCY),
            pose: new ReferencedPose(
                actor.position(),
                target_actor.position() - actor.position(),
                actor.MovedWith()
            ),
            target_name: target_actor.Name()
        );
        actor.SetNextAnimatronic(punch);
    }

    public override bool ActionPhase(ObjectOfTimeline actor, ITimeline timeline)
    {
        bool is_shoot_started = actor.CurrentAnimatronic() is PunchAnimatronic;
        var target_actor = TargetObject(timeline);

        if (!is_shoot_started)
        {
            StartEliminatePhase(actor, timeline);
            return false;
        }
        else
        {
            if (target_actor.IsStunned() == false)
            {
                StunTarget(
                    actor,
                    timeline,
                    0.0f,
                    length: (long)(punch_time * Utility.GAME_GLOBAL_FREQUENCY / 2)
                );
            }

            var start_local_time = actor.CurrentAnimatronic().StartStep;
            var current_local_time = actor.LocalStep();
            if (
                current_local_time - start_local_time
                > punch_time * Utility.GAME_GLOBAL_FREQUENCY / 2
            )
            {
                KillTarget(actor, timeline, 0.0f);
                return true;
            }
            else
            {
                return false;
            }
        }
    }

    public override bool IsActionStarted(ObjectOfTimeline actor)
    {
        if (actor.CurrentAnimatronic() is PunchAnimatronic)
        {
            var punch = actor.CurrentAnimatronic() as PunchAnimatronic;
            var target = punch.TargetName();
            var target_actor = TargetObject(actor.GetTimeline());

            if (target_actor.Name() == target)
            {
                return true;
            }

            return false;
        }
        else
        {
            return false;
        }
    }

    bool IsAirStrike(ObjectOfTimeline actor)
    {
        var current_animatronic = actor.CurrentAnimatronic();
        var jump_animatronic = current_animatronic as UniversalJumpAnimatronic;

        if (jump_animatronic == null)
        {
            return false;
        }

        var animtype = jump_animatronic.GetAnimationType(actor.LocalStep());

        if (animtype == AnimationType.SkyStrike_FleetPhase)
        {
            return true;
        }

        return false;
    }

    bool IsEliminatePhaseStarted(ObjectOfTimeline actor)
    {
        var current_command_state = actor.GetCommandSpecificState();
        if (current_command_state is ElliminateCommandState)
        {
            var state = current_command_state as ElliminateCommandState;
            return state.is_kill_phase_started;
        }
        return false;
    }

    public override bool Execute(ObjectOfTimeline actor, ITimeline timeline)
    {
        if (IsActionStarted(actor))
        {
            return ActionPhase(actor, timeline);
        }

        { // AirStrike
            if (IsEliminatePhaseStarted(actor))
            {
                return true;
            }

            if (IsAirStrike(actor))
            {
                ElliminateCommandState state = new ElliminateCommandState(true);
                var current_command_state = actor.GetCommandSpecificState();
                var card = new CommandSpecificStateChange(
                    prev_state: current_command_state,
                    next_state: state,
                    stamp: actor.LocalStep()
                );
                actor.AddCard(card);
                KillTarget(actor, timeline, 0.0f);
            }
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

    public void StunTarget(
        ObjectOfTimeline actor,
        ITimeline timeline,
        float absolute_offset,
        long length
    )
    {
        var target_actor = timeline.GetObject(TargetActorName());
        target_actor.AddCard(new StunEvent(step: timeline.CurrentStep(), length: length));
    }

    public void KillTarget(ObjectOfTimeline actor, ITimeline timeline, float absolute_offset)
    {
        var target_actor = timeline.GetObject(TargetActorName());
        timeline.AddEvent(
            new DeathEvent(
                step: timeline.CurrentStep()
                    + (long)(
                        absolute_offset * actor.ReverseMultiplier() * Utility.GAME_GLOBAL_FREQUENCY
                    ),
                actor: target_actor,
                who_kill_me: actor.Name(),
                reversed: target_actor.IsReversed()
            )
        );
    }

    //BEGIN################################################################
    // This code was generated by FieldScanner

    public override long HashCode()
    {
        long result = 0;
        result = FieldScanner.ModifyHash(result, punch_time);
        result = FieldScanner.ModifyHash(result, _action_distance);
        result = FieldScanner.ModifyHash(result, target_actor_name);
        result = FieldScanner.ModifyHash(result, can_use_air_strike);
        result = FieldScanner.ModifyHash(result, walktype);
        result = FieldScanner.ModifyHash(result, use_interaction_pose);
        result = FieldScanner.ModifyHash(result, start_step);
        result = FieldScanner.ModifyHash(result, finish_step);
        return result;
    }

    public override bool Equals(object obj)
    {
        if (obj == null)
            return false;
        if (obj.GetType() != GetType())
            return false;
        var other = obj as EliminateCommand;
        return punch_time == other.punch_time
            && _action_distance == other._action_distance
            && target_actor_name == other.target_actor_name
            && can_use_air_strike == other.can_use_air_strike
            && walktype == other.walktype
            && use_interaction_pose == other.use_interaction_pose
            && start_step == other.start_step
            && finish_step == other.finish_step
            && true;
    }

    public override int GetHashCode()
    {
        return (int)HashCode();
    }
    //END################################################################
}
