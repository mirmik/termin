using System.Collections.Generic;
using System;

#if UNITY_64
using UnityEngine;
#endif

public class MovingAnimatronic : Animatronic
{
    protected ReferencedPose _start_pose;
    protected ReferencedPose _finish_pose;
    protected float _animation_duration;
    protected float _angular_speed = 360;
    protected float _animation_booster = 1.0f;
    protected AnimationType _animtype;
    protected bool _is_dragging = false;
    protected bool _is_croach = false;
    protected LookAroundSettings _look_around;

    public Vector3 InitialDirection()
    {
        return _start_pose.LocalDirection();
    }

    public Vector3 TargetDirection2()
    {
        return _finish_pose.LocalDirection();
    }

    public Quaternion TargetRotation()
    {
        return _finish_pose.LocalRotation();
    }

    public Vector3 TargetPosition()
    {
        return _finish_pose.LocalPosition();
    }

    public float time_to_rotate()
    {
        return Vector3.Angle(InitialDirection(), TargetDirection2()) / _angular_speed;
    }

    public MovingAnimatronic(
        AnimationType animtype,
        ReferencedPose start_pose,
        ReferencedPose finish_pose,
        long start_step,
        long finish_step,
        float animation_duration,
        bool is_dragging = false,
        bool is_croach = false,
        LookAroundSettings look_around = default,
        float animation_booster = 1.0f
    ) : base(start_step, finish_step)
    {
        _animation_duration = animation_duration;
        _animtype = animtype;
        _start_pose = start_pose;
        _finish_pose = finish_pose;
        _is_dragging = is_dragging;
        _is_croach = is_croach;
        _look_around = look_around;
        _animation_booster = animation_booster;

        if (start_pose.Frame != finish_pose.Frame)
        {
            Debug.LogError("MovingAnimatronic: " + start_pose.Frame + " != " + finish_pose.Frame);
            throw new Exception("MovingAnimatronic: start_pose.Frame != finish_position.Frame");
        }
    }

    public MovingAnimatronic(
        AnimationType animtype,
        ReferencedPose start_pose,
        ReferencedPoint finish_point,
        long start_step,
        long finish_step,
        float animation_duration,
        bool is_dragging = false,
        bool is_croach = false,
        LookAroundSettings look_around = default,
        float animation_booster = 1.0f
    ) : base(start_step, finish_step)
    {
        var diff = finish_point.LocalPosition - start_pose.LocalPosition();
        Quaternion q = Quaternion.LookRotation(diff);
        var finish_pose = new ReferencedPose(finish_point.LocalPosition, q, start_pose.Frame);

        _animation_duration = animation_duration;
        _animtype = animtype;
        _start_pose = start_pose;
        _finish_pose = finish_pose;
        _is_dragging = is_dragging;
        _is_croach = is_croach;
        _look_around = look_around;
        _animation_booster = animation_booster;

        if (start_pose.Frame != finish_pose.Frame)
        {
            Debug.LogError("MovingAnimatronic: " + start_pose.Frame + " != " + finish_pose.Frame);
            throw new Exception("MovingAnimatronic: start_pose.Frame != finish_position.Frame");
        }
    }

    public override bool IsLooped()
    {
        return true;
    }

    public Vector3 FinishPosition()
    {
        return _finish_pose.LocalPosition();
    }

    public Vector3 StartPosition()
    {
        return _start_pose.LocalPosition();
    }

    public Vector3 InitialPosition => _start_pose.LocalPosition();

    public ReferencedPose StartPose()
    {
        return _start_pose;
    }

    public ReferencedPose FinalPose()
    {
        return new ReferencedPose(TargetPosition(), TargetRotation(), _finish_pose.Frame);
    }

    public override ReferencedScrew GetReferencedVelocityScrew(Int64 stepstamp, ITimeline tl)
    {
        if (stepstamp < StartStep)
        {
            return new ReferencedScrew(
                new Vector3(0, 0, 0),
                new Vector3(0, 0, 0),
                _start_pose.Frame
            );
        }

        if (stepstamp > FinishStep)
        {
            return new ReferencedScrew(
                new Vector3(0, 0, 0),
                new Vector3(0, 0, 0),
                _finish_pose.Frame
            );
        }

        var diff = _finish_pose.LocalPosition() - _start_pose.LocalPosition();
        var stepdiff = FinishStep - StartStep;
        var time = stepdiff / Utility.GAME_GLOBAL_FREQUENCY;
        return new ReferencedScrew(diff / time, new Vector3(0, 0, 0), _finish_pose.Frame);
    }

    public Vector3 Position(Int64 stepstamp, ITimeline tl, ObjectId frame)
    {
        if (stepstamp < StartStep)
        {
            return InitialPosition;
        }

        if (stepstamp > FinishStep)
        {
            return TargetPosition();
        }

        float koeff = (float)(stepstamp - StartStep) / (float)(FinishStep - StartStep);
        Vector3 non_grounded = Vector3.Lerp(InitialPosition, TargetPosition(), koeff);
        return non_grounded;
        //return Grounding(non_grounded, tl, frame);
    }

    public Vector3 Position_RealTime(float time, ITimeline tl, ObjectId frame)
    {
        var start_time = StartStep / Utility.GAME_GLOBAL_FREQUENCY;
        var finish_time = FinishStep / Utility.GAME_GLOBAL_FREQUENCY;

        if (time < start_time)
        {
            return InitialPosition;
        }

        if (time > finish_time)
        {
            return TargetPosition();
        }

        float koeff = (time - start_time) / (finish_time - start_time);
        Vector3 non_grounded = Vector3.Lerp(InitialPosition, TargetPosition(), koeff);
        return non_grounded;
        //return Grounding(non_grounded, tl, frame);
    }

    Quaternion InitialRotation()
    {
        return _start_pose.LocalRotation();
    }

    public Quaternion Rotation(Int64 stepstamp, ITimeline tl)
    {
        var target_rotation = TargetRotation();
        var initial_rotation = InitialRotation();

        var time_from_start = (stepstamp - StartStep) / Utility.GAME_GLOBAL_FREQUENCY;
        if (time_from_start < time_to_rotate())
        {
            var koeff = time_from_start / time_to_rotate();
            return Quaternion.Slerp(initial_rotation, target_rotation, koeff);
        }

        return target_rotation;
    }

    public Quaternion Rotation_RealTime(float time, ITimeline tl)
    {
        var target_rotation = TargetRotation();
        var initial_rotation = InitialRotation();

        var start_time = StartStep / Utility.GAME_GLOBAL_FREQUENCY;
        var time_from_start = time - start_time;
        if (time_from_start < time_to_rotate())
        {
            var koeff = time_from_start / time_to_rotate();
            return Quaternion.Slerp(initial_rotation, target_rotation, koeff);
        }

        return target_rotation;
    }

    // public override bool NeedGrounding()
    // {
    // 	return true;
    // }

    public override ReferencedPose GetReferencedPose(long stepstamp, ITimeline tl)
    {
        var rot = Rotation(stepstamp, tl);
        return new ReferencedPose(
            Position(stepstamp, tl, _finish_pose.Frame),
            rot,
            _finish_pose.Frame
        );
    }

    public override ReferencedPose GetReferencedPose_RealTime(float loctime, ITimeline tl)
    {
        var rot = Rotation_RealTime(loctime, tl);
        return new ReferencedPose(
            Position_RealTime(loctime, tl, _finish_pose.Frame),
            rot,
            _finish_pose.Frame
        );
    }

    // public new Vector3 Direction(Int64 stepstamp, ITimeline tl)
    // {
    // 	var quat = Rotation(stepstamp, tl);
    // 	return MathUtil.QuaternionToXZDirection(quat);
    // }

    override public bool IsCroach(ITimeline tl)
    {
        return _is_croach;
    }

    public float MovingPhaseForStep(long step)
    {
        var time_from_start = AnimationTimeOnStep(step);
        var phase = time_from_start / _animation_duration;
        var fractional_part = phase - (int)phase;
        return fractional_part;
    }

    public float InitialWalkingTimeForPhase(float phase)
    {
        var offset = phase * _animation_duration;
        return offset;
    }

    public override AnimationType GetAnimationType(long local_step)
    {
        return _animtype;
    }

    public override Pose LocalCameraPose(ObjectOfTimeline obj, long local_step)
    {
        if (_look_around.angle == 0)
            return new Pose(new Vector3(0, obj.CameraLevel, 0), Quaternion.Euler(0, 0, 0));

        var step_from_start = local_step - StartStep;
        var step_from_start_in_seconds = step_from_start / Utility.GAME_GLOBAL_FREQUENCY;

        var addpose = new Pose(
            new Vector3(0, obj.CameraLevel, 0),
            Quaternion.Euler(
                0,
                Mathf.Sin(step_from_start_in_seconds * _look_around.frequency * 2 * Mathf.PI)
                    * _look_around.angle,
                0
            )
        );
        return addpose;
    }

    public override global::System.Single AnimationBooster()
    {
        return _animation_booster;
    }

    //BEGIN################################################################
    // This code was generated by FieldScanner

    public override long HashCode()
    {
        long result = 0;
        result = FieldScanner.ModifyHash(result, _start_pose);
        result = FieldScanner.ModifyHash(result, _finish_pose);
        result = FieldScanner.ModifyHash(result, _animation_duration);
        result = FieldScanner.ModifyHash(result, _angular_speed);
        result = FieldScanner.ModifyHash(result, _animation_booster);
        result = FieldScanner.ModifyHash(result, _animtype);
        result = FieldScanner.ModifyHash(result, _is_dragging);
        result = FieldScanner.ModifyHash(result, _is_croach);
        result = FieldScanner.ModifyHash(result, _look_around);
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
        var other = obj as MovingAnimatronic;
        return _start_pose == other._start_pose
            && _finish_pose == other._finish_pose
            && _animation_duration == other._animation_duration
            && _angular_speed == other._angular_speed
            && _animation_booster == other._animation_booster
            && _animtype == other._animtype
            && _is_dragging == other._is_dragging
            && _is_croach == other._is_croach
            && _look_around == other._look_around
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
