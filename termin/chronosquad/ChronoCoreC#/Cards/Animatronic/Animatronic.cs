using System;
using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif

[Serializable]
public abstract class Animatronic : BasicMultipleAction
{
    protected float _initial_animation_time = 0;

    protected long unchanged_start_step = 0;
    protected long unchanged_finish_step = 0;

    new public long StartStep => unchanged_start_step;
    new public long FinishStep => unchanged_finish_step;

    public long InterruptionStep => base.FinishStep;

    //public float FinishTime => FinishStep / Utility.GAME_GLOBAL_FREQUENCY;
    //public float StartTime => StartStep / Utility.GAME_GLOBAL_FREQUENCY;

    public Animatronic() { }

    public Animatronic(long start, long finish) : base(start, finish)
    {
        this.unchanged_start_step = start;
        this.unchanged_finish_step = finish;
    }

    public virtual float AnimationBooster()
    {
        return 1.0f;
    }

    public bool IsFinished(long step)
    {
        return step >= FinishStep;
    }

    public virtual Pose LocalCameraPose(ObjectOfTimeline obj, long step)
    {
        return new Pose(new Vector3(0, obj.CameraLevel, 0), Quaternion.Euler(0, 0, 0));
    }

    public virtual bool NeedToBeReassignedToAnotherCordinateSystem()
    {
        return true;
    }

    public virtual bool CanBeReassignedToAnotherCordinateSystem()
    {
        return false;
    }

    public Animatronic Clone()
    {
        return (Animatronic)MemberwiseClone();
    }

    // public virtual void ReassignToAnotherCoordinateSystem(
    // 	ITimeline tl,
    // 	ObjectOfTimeline obj,
    // 	ObjectOfTimeline current_parent,
    // 	ObjectOfTimeline new_parent
    // )
    // {
    // 	throw new Exception("ReassignToAnotherCoordinateSystem");
    // }

    public virtual bool IsLooped()
    {
        return false;
    }

    // public abstract string FrameName(Int64 stepstamp);

    public Pose ModelPose(long stepstamp, ITimeline tl)
    {
        return Pose.Identity;
    }

    public virtual void apply(ObjectOfTimeline obj, long current_step)
    {
        var vel = GetReferencedVelocityScrew(current_step, obj.GetTimeline());
        var referenced_pose = GetReferencedPose(current_step, obj.GetTimeline());
        if (obj is PhysicalObject)
        {
            (obj as PhysicalObject).SetNonNoisedReferencedPose(referenced_pose);
            (obj as PhysicalObject).SetLocalCameraPose(LocalCameraPose(obj, current_step));
        }

        obj.set_velocity(vel);
        obj.current_animation_type = GetAnimationType(current_step);

        if (obj is Actor)
        {
            (obj as Actor).croachControlComponent.IsCroach = IsCroach(obj.GetTimeline());
            (obj as Actor).croachControlComponent.IsBraced = IsBraced(
                obj.GetTimeline(),
                current_step
            );
        }
    }

    // public virtual bool NeedGrounding()
    // {
    // 	return false;
    // }

    public virtual bool IsCroach(ITimeline tl)
    {
        return false;
    }

    public virtual bool IsBraced(ITimeline tl, long step)
    {
        return false;
    }

    public virtual float OverlapTime()
    {
        return 0.25f;
    }

    public virtual bool CanBeInterruptedForAction()
    {
        return true;
    }

    public float AnimationTimeOnStep(long step)
    {
        return _initial_animation_time + TimeFromStart(step);
    }

    public float AnimationTimeOnLocalTime(float time)
    {
        return _initial_animation_time + TimeFromStart(time);
    }

    public float TimeFromStart(long step)
    {
        return (float)(step - StartStep) / Utility.GAME_GLOBAL_FREQUENCY;
    }

    public float TimeFromStart(float time)
    {
        var start_time = (float)StartStep / Utility.GAME_GLOBAL_FREQUENCY;
        return time - start_time;
    }

    public float LocalTimeForStep(long step)
    {
        return (float)(step) / Utility.GAME_GLOBAL_FREQUENCY;
    }

    public float StartLocalTime()
    {
        return LocalTimeForStep(StartStep);
    }

    public float FinishLocalTime()
    {
        return LocalTimeForStep(FinishStep);
    }

    public long StepFromAnimationStart(long step)
    {
        return step - StartStep;
    }

    public void SetInitialAnimationTime(float time_from_animation_start)
    {
        _initial_animation_time = time_from_animation_start;
    }

    public float InitialAnimationTime()
    {
        return _initial_animation_time;
    }

    abstract public AnimationType GetAnimationType(long local_step);

    public Vector3 Direction(Int64 stepstamp, ITimeline tl)
    {
        return GetReferencedPose(stepstamp, tl).LocalDirection();
    }

    public Vector3 Position(Int64 stepstamp, ITimeline tl)
    {
        return GetReferencedPose(stepstamp, tl).LocalPosition();
    }

    public abstract ReferencedPose GetReferencedPose(long stepstamp, ITimeline tl);

    public virtual ReferencedPose GetReferencedPose_RealTime(float loctime, ITimeline tl)
    {
        return GetReferencedPose((long)(loctime * Utility.GAME_GLOBAL_FREQUENCY), tl);
    }

    public virtual ReferencedScrew GetReferencedVelocityScrew(Int64 stepstamp, ITimeline tl)
    {
        return new ReferencedScrew(new Vector3(0, 0, 0), new Vector3(0, 0, 0), StartFrame(tl));
    }

    public virtual ReferencedPose FinishPose(ITimeline tl)
    {
        return GetReferencedPose(FinishStep, tl);
    }

    public ReferencedPose FinalPose(ITimeline tl)
    {
        return FinishPose(tl);
    }

    public virtual ReferencedPose StartPose(ITimeline tl)
    {
        return GetReferencedPose(StartStep, tl);
    }

    public ObjectId FinalFrame(ITimeline tl)
    {
        return FinishPose(tl).Frame;
    }

    public ObjectId StartFrame(ITimeline tl)
    {
        return StartPose(tl).Frame;
    }

    public Vector3 FinishPosition(ITimeline tl)
    {
        return FinishPose(tl).LocalPosition();
    }
}

[Serializable]
public class PunchAnimatronic : Animatronic
{
    // private Vector3 _direction;
    // private Vector3 _position;
    ReferencedPose _pose;
    private string _target_name;

    public PunchAnimatronic(
        long start_step,
        long finish_step,
        ReferencedPose pose,
        string target_name
    ) : base(start_step, finish_step)
    {
        this._pose = pose;
        this._target_name = target_name;
    }

    public string TargetName()
    {
        return _target_name;
    }

    public override ReferencedPose GetReferencedPose(long stepstamp, ITimeline tl)
    {
        return _pose;
    }

    // public override string FrameName(Int64 stepstamp)
    // {
    // 	return _pose.Frame;
    // }

    public override AnimationType GetAnimationType(long local_step)
    {
        return AnimationType.Punch;
    }

    //BEGIN################################################################
    // This code was generated by FieldScanner

    public override long HashCode()
    {
        long result = 0;
        result = FieldScanner.ModifyHash(result, _pose);
        result = FieldScanner.ModifyHash(result, _target_name);
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
        var other = obj as PunchAnimatronic;
        return _pose == other._pose
            && _target_name == other._target_name
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
