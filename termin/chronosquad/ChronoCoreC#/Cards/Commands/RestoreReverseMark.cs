using System;
using Unity.VisualScripting;
using UnityEngine;

public class RestoreReverseMarkCommand : ActorCommand
{
    ObjectId target_actor_name;
    ReferencedPoint _mark_position;

    public RestoreReverseMarkCommand(ReferencedPoint target, ObjectId target_view, long stamp)
        : base(stamp)
    {
        _mark_position = target;
        target_actor_name = target_view;

        Debug.Log("RestoreReverseMarkCommand: target_actor_name = " + target_actor_name);
    }

    ObjectOfTimeline TargetObject(ITimeline timeline)
    {
        return timeline.GetObject(target_actor_name);
    }

    // protected override bool ActionPhase(ObjectOfTimeline actor, ITimeline timeline)
    // {
    // 	Debug.Log("RestoreReverseMarkCommand");
    // 	var target_actor = TargetObject(timeline) as Actor;
    // 	var timeline_step_mark = target_actor.PromiseMarkTimelineStep();
    // 	var curtlstep = timeline.CurrentStep();

    // 	if (timeline_step_mark > curtlstep)
    // 	{
    // 		Debug.Log("RestoreReverseMarkCommand: timeline_step_mark > curtlstep");
    // 	}
    // 	else
    // 	{
    // 		Debug.Log("RestoreReverseMarkCommand: timeline_step_mark <= curtlstep");
    // 	}
    // 	return true;
    // }

    // bool MarkInOppositeSide(ITimeline tl)
    // {
    // 	var target_actor = TargetObject(tl) as Actor;
    // 	var mark = target_actor.PromiseMarkTimelineStep();
    // 	var current = tl.CurrentStep();

    // 	TimeDirection direction = tl.IsReversedPass() ? TimeDirection.Backward : TimeDirection.Forward;
    // 	if (direction == TimeDirection.Backward)
    // 	{
    // 		return mark > current;
    // 	}
    // 	else
    // 	{
    // 		return mark < current;
    // 	}
    // }

    // public void MovingPhase(ObjectOfTimeline actor, ITimeline timeline)
    // {
    // 	if (timeline.IsPast())
    // 		actor.DropToCurrentState();

    // 	var sposition = actor.CurrentReferencedPosition();
    // 	var start_position = sposition;

    // 	var unitpath = PathFinding.MakeUnitPathForMoving(
    // 		actor,
    // 		timeline,
    // 		start_position,
    // 		_target_position,
    // 		_start_type,
    // 		_target_type,
    // 		_braced_coordinates,
    // 		navmesh_precast: false,
    // 		use_normal_as_up: actor.UseSurfaceNormalForOrientation
    // 	);

    // 	ApplyUnitPath(actor as Actor, unitpath);
    // }

    public void ApplyUnitPath(Actor actor, UnitPath unitpath)
    {
        var _walking_type = WalkingType.Run;
        var _look_around = new LookAroundSettings();

        var timeline = actor.GetTimeline();
        var list = actor.PlanPath(unitpath, _walking_type, 0, look_around: _look_around);
        actor.ApplyAnimatronicsList(list);

        if (actor.grabbed_actor != default && actor.is_drag_grabbed_actor)
        {
            var pulled_object = timeline.GetObject(actor.grabbed_actor);
            if (pulled_object != null)
            {
                var pulled_path = PathFinding.PulledPathFrom(
                    list,
                    pulled_object.CurrentReferencedPose(),
                    timeline
                );
                pulled_object.ApplyAnimatronicsList(pulled_path);
            }
        }
    }

    float DistanceToMark(Actor actor, Timeline timeline)
    {
        var actor_global_position = actor.GlobalPosition();
        var mark_global_position = _mark_position.GlobalPosition(timeline);
        return Vector3.Distance(actor_global_position, mark_global_position);
    }

    float DistanceToObject(Actor actor, Timeline timeline)
    {
        var actor_global_position = actor.GlobalPosition();
        var target_actor = TargetObject(timeline) as Actor;
        var target_global_position = target_actor.GlobalPosition();
        return Vector3.Distance(actor_global_position, target_global_position);
    }

    void MovingToMark(Actor actor, ITimeline timeline)
    {
        if (timeline.IsPast())
            actor.DropToCurrentState();

        var animatronic = actor.CurrentAnimatronic();
        Debug.Log("animatronic = " + animatronic);
        if (animatronic is MovingAnimatronic)
        {
            return;
        }

        var sposition = actor.CurrentReferencedPosition();
        var start_position = sposition;

        var _start_type = PathFindingTarget.Standart;
        var _target_type = PathFindingTarget.Standart;
        BracedCoordinates _braced_coordinates = default;

        var unitpath = PathFinding.MakeUnitPathForMoving(
            actor,
            timeline,
            start_position,
            _mark_position,
            _start_type,
            _target_type,
            _braced_coordinates,
            navmesh_precast: false,
            use_normal_as_up: actor.UseSurfaceNormalForOrientation
        );

        ApplyUnitPath(actor, unitpath);
    }

    void MovingToObject(Actor actor, ITimeline timeline)
    {
        if (timeline.IsPast())
            actor.DropToCurrentState();

        var animatronic = actor.CurrentAnimatronic();
        if (animatronic is MovingAnimatronic)
        {
            var animpos = animatronic.FinishPose(timeline).GlobalPose(timeline).position;
            var target_position = TargetObject(timeline).GlobalPosition();
            if (Vector3.Distance(animpos, target_position) < 0.5f)
                return;
        }

        var sposition = actor.CurrentReferencedPosition();
        var start_position = sposition;

        var _start_type = PathFindingTarget.Standart;
        var _target_type = PathFindingTarget.Standart;
        BracedCoordinates _braced_coordinates = default;

        var unitpath = PathFinding.MakeUnitPathForMoving(
            actor,
            timeline,
            start_position,
            TargetObject(timeline).CurrentReferencedPosition(),
            _start_type,
            _target_type,
            _braced_coordinates,
            navmesh_precast: false,
            use_normal_as_up: actor.UseSurfaceNormalForOrientation
        );

        ApplyUnitPath(actor, unitpath);
    }

    bool MarkInFuture(ITimeline timeline)
    {
        long mark_timestamp = (TargetObject(timeline) as Actor).PromiseMarkTimelineStep();
        long current_timestamp = timeline.CurrentStep();
        return mark_timestamp >= current_timestamp;
    }

    public override bool ExecuteFirstTime(ObjectOfTimeline actor, ITimeline timeline)
    {
        //Debug.Log("RestoreReverseMarkCommand.ExecuteFirstTime");
        // long mark_timestamp = (TargetObject(timeline) as Actor).PromiseMarkTimelineStep();
        // long current_timestamp = timeline.CurrentStep();

        if (MarkInFuture(timeline))
        {
            Debug.Log(
                "RestoreReverseMarkCommand.ExecuteFirstTime: mark_timestamp >= current_timestamp"
            );
            MovingToMark(actor as Actor, timeline);
        }
        else
        {
            Debug.Log(
                "RestoreReverseMarkCommand.ExecuteFirstTime: mark_timestamp < current_timestamp"
            );
            MovingToObject(actor as Actor, timeline);
            //return true;
        }

        return false;
    }

    void StartIdle(Actor actor, ITimeline timeline)
    {
        var animatronic = actor.CurrentAnimatronic();
        if (animatronic is IdleAnimatronic)
        {
            return;
        }
        var anim = new IdleAnimatronic(
            start_step: actor.LocalStep(),
            pose: actor.CurrentReferencedPose(),
            idle_animation: AnimationType.Idle,
            local_camera_pose: Pose.Identity
        );
        Debug.Log("RestoreReverseMarkCommand.StartIdle: anim = " + anim);
        actor.SetNextAnimatronic(anim);
    }

    public void Sewing(ObjectOfTimeline actor, Timeline tl)
    {
        ObjectOfTimeline prev = actor;
        ObjectOfTimeline next = TargetObject(tl) as ObjectOfTimeline;

        var prev_local_step = prev.LocalStep();
        var next_local_step = next.LocalStep();
        var shift = prev_local_step - next_local_step;

        //next.CleanAllQueues();
        //var commands_list = next.CommandBuffer().GetCommandQueue().AsList();
        //var new_commands = new MyList<ActorCommand>();

        //var current_command = next.CommandBuffer().CurrentCommand();
        // if (current_command != null)
        // {
        // 	var clone = current_command.Clone() as ActorCommand;
        // 	clone.SetStartStep(prev_local_step + 1);
        // 	Debug.Log("RestoreReverseMarkCommand.Sewing: clone = " + clone);
        // 	prev.AddExternalCommand(clone);
        // }

        var commands_list = next.CommandBuffer().GetCommandQueue().AllNextAsList();
        foreach (var command in commands_list)
        {
            var comcopy = command.CloneWithShift(shift);
            Debug.Log("RestoreReverseMarkCommand.Sewing: comcopy = " + comcopy);
            prev.CommandBuffer().ImportCommand(comcopy);
        }

        Debug.Log("RestoreReverseMarkCommand.Sewing");
        Debug.Log("Сращиваю ветви");

        tl.RemoveObject(next);
    }

    public override bool Execute(ObjectOfTimeline actor, ITimeline timeline)
    {
        long mark_timestamp = (TargetObject(timeline) as Actor).PromiseMarkTimelineStep();
        long current_timestamp = timeline.CurrentStep();
        float duration = (mark_timestamp - current_timestamp) * Utility.GAME_GLOBAL_FREQUENCY;

        if (MarkInFuture(timeline))
        {
            float dist = DistanceToMark(actor as Actor, timeline as Timeline);
            if (dist < 0.1f)
            {
                if (Mathf.Abs(duration) < 0.1f)
                {
                    Sewing(actor, timeline as Timeline);
                    return true;
                }
                StartIdle(actor as Actor, timeline);
                return false;
            }
            MovingToMark(actor as Actor, timeline);
        }
        else
        {
            float dist = DistanceToObject(actor as Actor, timeline as Timeline);
            if (dist < 0.5f)
            {
                //if (Mathf.Abs(duration) < 0.1f)
                //{
                Sewing(actor, timeline as Timeline);
                return true;
                //}
                //return false;
            }
            MovingToObject(actor as Actor, timeline);
        }
        return false;
    }

    //BEGIN################################################################
    // This code was generated by FieldScanner

    public override long HashCode()
    {
        long result = 0;
        result = FieldScanner.ModifyHash(result, target_actor_name);
        // result = FieldScanner.ModifyHash(result, radius);
        // result = FieldScanner.ModifyHash(result, _target_position);
        // result = FieldScanner.ModifyHash(result, _target_type);
        // result = FieldScanner.ModifyHash(result, _start_type);
        // result = FieldScanner.ModifyHash(result, _walking_type);
        // result = FieldScanner.ModifyHash(result, _braced_coordinates);
        // result = FieldScanner.ModifyHash(result, _look_around);
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
        var other = obj as RestoreReverseMarkCommand;
        return target_actor_name == other.target_actor_name
            &&
            // radius == other.radius &&
            // _target_position == other._target_position &&
            // _target_type == other._target_type &&
            // _start_type == other._start_type &&
            // _walking_type == other._walking_type &&
            // _braced_coordinates == other._braced_coordinates &&
            // _look_around == other._look_around &&
            start_step == other.start_step
            && finish_step == other.finish_step
            && true;
    }

    public override int GetHashCode()
    {
        return (int)HashCode();
    }
    //END################################################################
}
