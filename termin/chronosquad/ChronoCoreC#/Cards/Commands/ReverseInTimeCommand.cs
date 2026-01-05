using System.Collections;
using System.Collections.Generic;
using System;

#if UNITY_64
using UnityEngine;
#endif

[Serializable]
public class ReverseInTimeCommand : ActorCommand
{
    protected bool active_is_reversed = false;

    protected long timeline_step;
    protected Vector3 actor_position;

    long TimelineStep()
    {
        return timeline_step;
    }

    public ReverseInTimeCommand(
        long add_step,
        bool active_is_reversed,
        long timeline_step,
        Vector3 actor_position
    ) : base(add_step)
    {
        this.active_is_reversed = active_is_reversed;
        this.timeline_step = timeline_step;
        this.actor_position = actor_position;
        //copy_postfix = UniqueIdGenerator.GetNextId().ToString();
    }

    protected string GenerateCopyName(string actor)
    {
        return actor + UniqueIdGenerator.GetNextId().ToString();
    }

    BlindEffect MakeBlindEvent()
    {
        return new BlindEffect(
            start_step: (long)(timeline_step - 0.5 * Utility.GAME_GLOBAL_FREQUENCY),
            finish_step: (long)(timeline_step + 0.5 * Utility.GAME_GLOBAL_FREQUENCY),
            position: actor_position,
            material_name: "BlinkShaderMat"
        );
    }

    protected virtual void CreateReversedCopy(Actor _actor, Timeline tl)
    {
        string copy_name = GenerateCopyName(_actor.Name());

        var chronosphere = _actor.Chronosphere();
        var timeline_step = tl.CurrentStep();

        var blind_event = MakeBlindEvent();
        tl.AddNonDropableEvent(blind_event);

        var primary_event = PrimaryAnigilationEvent(_actor);
        tl.AddNonDropableEvent(primary_event);

        Action act = () =>
        {
            var ntc = tl.Copy();

            bool timeline_if_reversed = tl.IsReversedPass();
            if (active_is_reversed == timeline_if_reversed)
            {
                chronosphere.TimeReverseImmediate();
                ntc.SetReversedPass(!tl.IsReversedPass());
            }

            ntc.SetCurrentTimeline();
            ntc.DropLastTimelineStep();

            var guard_id = _actor.Name();
            var ntc_guard = ntc.GetActor(guard_id);

            var copy = ntc_guard.Copy(ntc) as Actor;

            copy.SetName(copy_name);
            ntc.AddObject(copy);

            copy.SetObjectTimeReferencePoint(timeline_step, !copy.IsReversed());
            bool copy_is_reversed = copy.IsReversed();

            copy.DropToCurrentStateInverted();

            copy.CommandBuffer().GetCommandQueue().Remove(typeof(ReverseInTimeCommand), StartStep);

            chronosphere.Select(copy);

            if (ntc_guard.PrimaryChildName() != null)
            {
                copy.SetPrimaryChild(ntc_guard.PrimaryChildName());
                ((Actor)ntc_guard.PrimaryChild()).SetParentGuardName(copy.Name());
            }
            ntc_guard.SetPrimaryChild(copy.Name());
            copy.SetParentGuardName(ntc_guard.Name());

            var card2 = SecondaryAnigilationEvent(ntc_guard);
            ntc.AddNonDropableEvent(card2);

            ntc.DropLastTimelineStep(
                copy_is_reversed ? TimeDirection.Backward : TimeDirection.Forward
            );
        };
        tl.AddAfterStepUpdateAction(act);
    }

    protected void AnigilationOnly(Actor _actor, ITimeline tl)
    {
        var chronosphere = _actor.Chronosphere();
        var timeline_step = tl.CurrentStep();

        var blind_event = MakeBlindEvent();
        tl.AddNonDropableEvent(blind_event);

        var card = new AnigilationEvent(
            step: timeline_step,
            object_name: _actor.Name(),
            reversed: _actor.IsReversed()
        );
        tl.AddNonDropableEvent(card);

        var card2 = new AnigilationEvent(
            step: timeline_step,
            object_name: GenerateCopyName(_actor.Name()),
            reversed: _actor.IsReversed()
        );
        tl.AddNonDropableEvent(card2);
    }

    protected bool IsEffectExist(Actor _actor, Timeline tl)
    {
        var primary_hash = PrimaryAnigilationEvent(_actor).HashCode();
        return tl.ContainsNonDropableEvent(primary_hash);
    }

    protected AnigilationEvent PrimaryAnigilationEvent(Actor actor)
    {
        var timeline_step = TimelineStep();
        var ev = new AnigilationEvent(
            step: timeline_step,
            object_name: actor.Name(),
            reversed: active_is_reversed
        );
        return ev;
    }

    protected AnigilationEvent SecondaryAnigilationEvent(Actor actor)
    {
        var timeline_step = TimelineStep();
        return new AnigilationEvent(
            step: timeline_step,
            object_name: actor.PrimaryChildName(),
            reversed: active_is_reversed
        );
    }

    public override bool ExecuteFirstTime(ObjectOfTimeline obj, ITimeline ttl)
    {
        var tl = ttl as Timeline;
        var actor = obj as Actor;
        bool timeline_if_reversed = tl.IsReversedPass();
        bool copy_is_exist = IsEffectExist(actor, tl);

        if (!copy_is_exist)
        {
            CreateReversedCopy(actor, tl);
        }
        else
        {
            AnigilationOnly(actor, tl);
        }

        return true;
    }

    public override void CancelHandler(CommandBufferBehaviour behaviour)
    {
        var actor = behaviour.Actor();
        var timeline = actor.GetTimeline() as Timeline;

        var primary_hash = PrimaryAnigilationEvent(actor).HashCode();
        var secondary_hash = SecondaryAnigilationEvent(actor).HashCode();

        timeline.RemoveNonDropableEvent(primary_hash);
        timeline.RemoveNonDropableEvent(secondary_hash);
        timeline.RemoveNonDropableEvent(MakeBlindEvent().HashCode());

        string copyname = actor.PrimaryChildName();
        actor.CancelLinkedSpawning(copyname);
    }

    //BEGIN################################################################
    // This code was generated by FieldScanner

    public override long HashCode()
    {
        long result = 0;
        result = FieldScanner.ModifyHash(result, active_is_reversed);
        result = FieldScanner.ModifyHash(result, timeline_step);
        result = FieldScanner.ModifyHash(result, actor_position);
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
        var other = obj as ReverseInTimeCommand;
        return active_is_reversed == other.active_is_reversed
            && timeline_step == other.timeline_step
            && actor_position == other.actor_position
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
