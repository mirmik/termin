using System.Collections;
using System.Collections.Generic;
using System;
using System.Linq;

#if UNITY_64
using UnityEngine;
#endif

[Serializable]
public class UniversalJumpAnimatronic : Animatronic
{
    ReferencedPose _start_pose;
    ReferencedPose _finish_pose;
    AnimationType _animation_type;
    bool _parabolic_jump = false;
    bool _loop = false;
    float _overlap_time = 0.25f;

    public UniversalJumpAnimatronic(
        ReferencedPose start_pose,
        ReferencedPose finish_pose,
        long start_step,
        long finish_step,
        AnimationType animation_type,
        bool parabolic_jump = false,
        bool loop = false,
        float overlap_time = 0
    ) : base(start_step, finish_step)
    {
        _start_pose = start_pose;
        _finish_pose = finish_pose;
        _animation_type = animation_type;
        _parabolic_jump = parabolic_jump;
        _loop = loop;
        _overlap_time = overlap_time;
    }

    public override bool IsLooped()
    {
        return _loop;
    }

    public override bool CanBeInterruptedForAction()
    {
        return false;
    }

    public override ReferencedPose GetReferencedPose(long stepstamp, ITimeline tl)
    {
        if (_start_pose.Frame != _finish_pose.Frame)
        {
            return GetReferencedPose_Globally(stepstamp, tl);
        }

        if (stepstamp <= StartStep)
        {
            return _start_pose;
        }

        if (stepstamp >= FinishStep)
        {
            return _finish_pose;
        }

        var rot = Rotation(stepstamp, tl);
        return new ReferencedPose(Position(stepstamp, tl), rot, _finish_pose.Frame);
    }

    public ReferencedPose GetReferencedPose_Globally(long stepstamp, ITimeline tl)
    {
        if (stepstamp <= StartStep)
        {
            return _start_pose;
        }

        if (stepstamp >= FinishStep)
        {
            return _finish_pose;
        }

        var rot = Rotation(stepstamp, tl);
        return new ReferencedPose(GlobalPosition(stepstamp, tl), rot, null);
    }

    public new Vector3 Position(long stepstamp, ITimeline tl)
    {
        if (stepstamp < StartStep)
        {
            return _start_pose.LocalPosition();
        }

        if (stepstamp > FinishStep)
        {
            return _finish_pose.LocalPosition();
        }

        if (_parabolic_jump)
        {
            var start = _start_pose.LocalPosition();
            var finish = _finish_pose.LocalPosition();
            var start_xz = new Vector3(start.x, 0, start.z);
            var finish_xz = new Vector3(finish.x, 0, finish.z);
            var start_y = start.y;
            var finish_y = finish.y;

            var t = (float)(stepstamp - StartStep) / (float)(FinishStep - StartStep);
            var position_xz = Vector3.Lerp(start_xz, finish_xz, t);
            var tt = t * t;
            var position_y = start_y + (finish_y - start_y) * tt;

            var pposition = new Vector3(position_xz.x, position_y, position_xz.z);
            return pposition;
        }

        var T = (float)(stepstamp - StartStep) / (float)(FinishStep - StartStep);
        var position = Vector3.Lerp(_start_pose.LocalPosition(), _finish_pose.LocalPosition(), T);
        return position;
    }

    public override float OverlapTime()
    {
        return _overlap_time;
    }

    public Vector3 GlobalPosition(long stepstamp, ITimeline timeline)
    {
        // if (_parabolic_jump)
        // {
        // 	var start = _start_pose.LocalPosition();
        // 	var finish = _finish_pose.LocalPosition();
        // 	var start_xz = new Vector3(start.x, 0, start.z);
        // 	var finish_xz = new Vector3(finish.x, 0, finish.z);
        // 	var start_y = start.y;
        // 	var finish_y = finish.y;

        // 	var t = (float)(stepstamp - StartStep) / (float)(FinishStep - StartStep);
        // 	var position_xz = Vector3.Lerp(start_xz, finish_xz, t);
        // 	var tt = t * t;
        // 	var position_y = start_y + (finish_y - start_y) * tt;

        // 	var pposition = new Vector3(position_xz.x, position_y, position_xz.z);
        // 	return pposition;
        // }

        var T = (float)(stepstamp - StartStep) / (float)(FinishStep - StartStep);
        var position = Vector3.Lerp(
            _start_pose.GlobalPosition(timeline),
            _finish_pose.GlobalPosition(timeline),
            T
        );
        return position;
    }

    // Vector3 TargetDirection()
    // {
    // 	if (_finish_pose.LocalPosition() == _start_pose.LocalPosition())
    // 	{
    // 		return _start_pose.LocalDirection();
    // 	}

    // 	var a = _finish_pose.LocalPosition();
    // 	var b = _start_pose.LocalPosition();

    // 	var diff = a - b;
    // 	diff.y = 0;

    // 	if (diff.magnitude < 0.01f)
    // 	{
    // 		return _start_pose.LocalDirection();
    // 	}

    // 	return diff.normalized;
    // }

    public Quaternion Rotation(long stepstamp, ITimeline tl)
    {
        return _finish_pose.LocalRotation();
    }

    // public new Vector3 Direction(long stepstamp, ITimeline tl)
    // {
    // 	if (_finish_pose.LocalPosition() == _start_pose.LocalPosition())
    // 	{
    // 		return _start_pose.LocalDirection();
    // 	}

    // 	if (stepstamp < StartStep)
    // 	{
    // 		return _start_pose.LocalDirection();
    // 	}

    // 	if (stepstamp > FinishStep)
    // 	{
    // 		return TargetDirection();
    // 	}

    // 	var start_direction = _start_pose.LocalDirection();
    // 	var target_direction = TargetDirection();

    // 	var t = (float)(stepstamp - StartStep) / (float)(FinishStep - StartStep);
    // 	var direction = Vector3.Lerp(start_direction, target_direction, t);

    // 	return direction;
    // }

    override public AnimationType GetAnimationType(long local_step)
    {
        return _animation_type;
    }

    //BEGIN################################################################
    // This code was generated by FieldScanner

    public override long HashCode()
    {
        long result = 0;
        result = FieldScanner.ModifyHash(result, _start_pose);
        result = FieldScanner.ModifyHash(result, _finish_pose);
        result = FieldScanner.ModifyHash(result, _animation_type);
        result = FieldScanner.ModifyHash(result, _parabolic_jump);
        result = FieldScanner.ModifyHash(result, _loop);
        result = FieldScanner.ModifyHash(result, _overlap_time);
        result = FieldScanner.ModifyHash(result, _initial_animation_time);
        result = FieldScanner.ModifyHash(result, unchanged_start_step);
        result = FieldScanner.ModifyHash(result, unchanged_finish_step);
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
        var other = obj as UniversalJumpAnimatronic;
        return _start_pose == other._start_pose
            && _finish_pose == other._finish_pose
            && _animation_type == other._animation_type
            && _parabolic_jump == other._parabolic_jump
            && _loop == other._loop
            && _overlap_time == other._overlap_time
            && _initial_animation_time == other._initial_animation_time
            && unchanged_start_step == other.unchanged_start_step
            && unchanged_finish_step == other.unchanged_finish_step
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
