#if UNITY_64
using UnityEngine;
#endif

using System;
using System.Collections.Generic;

public class PhysicalObject : ObjectOfTimeline
{
    protected ReferencedPose _non_noised_pose = new ReferencedPose(Pose.Identity, null);
    protected ReferencedPose _preevaluated_pose = new ReferencedPose(Pose.Identity, null);

    public override void FromTrent(Dictionary<string, object> dict)
    {
        _non_noised_pose.FromTrent((Dictionary<string, object>)dict["non_noised_pose"]);
        base.FromTrent(dict);
    }

    public override Dictionary<string, object> ToTrent()
    {
        Dictionary<string, object> dict = base.ToTrent();
        dict["non_noised_pose"] = _non_noised_pose.ToTrent();
        return dict;
    }

    public void SetNonNoisedReferencedPose(ReferencedPose pose)
    {
        _non_noised_pose = pose;
    }

    public ReferencedPose PreEvaluateCurrentReferencedPose()
    {
        if (PoseIsNoised() && (GetTimeline() as Timeline).step_evaluation_flag)
        {
            var position_noise = PositionNoise();
            var rotation_noise = RotationNoise();
            var pose = _non_noised_pose.LocalPose();
            pose.rotation = pose.rotation * rotation_noise;
            pose.position += position_noise;
            return new ReferencedPose(pose, _non_noised_pose.Frame);
        }

        return _non_noised_pose;
    }

    // public override Vector3 EvaluateGlobalCameraPosition()
    // {
    // 	var global_pose = GlobalCameraPose();
    // 	return global_pose.position;
    // }

    // public override Vector2 EvaluateGlobalCameraDirectionXZ()
    // {
    // 	var global_pose = GlobalCameraPose();
    // 	var vec = global_pose.rotation * Vector3.forward;
    // 	return new Vector2(vec.x, vec.z);
    // }


    override public void PreEvaluateChild()
    {
        _preevaluated_pose = PreEvaluateCurrentReferencedPose();
    }

    public override ReferencedPose CurrentReferencedPose()
    {
        if (!_preevaluated_is_valid)
            PreEvaluate();

        return _preevaluated_pose;
    }

    public Pose LocalPose()
    {
        return CurrentReferencedPose().LocalPose();
    }

    public void SetPosition(Vector3 position)
    {
        _non_noised_pose = new ReferencedPose(
            new Pose(position, _non_noised_pose.LocalRotation()),
            _non_noised_pose.Frame
        );
    }

    public void SetDirection(Vector3 dir)
    {
        Quaternion rotation = Quaternion.LookRotation(dir);
        _non_noised_pose = new ReferencedPose(
            new Pose(_non_noised_pose.LocalPosition(), rotation),
            _non_noised_pose.Frame
        );
    }

    public void SetPose(Vector3 position, Quaternion rotation)
    {
        _non_noised_pose = new ReferencedPose(new Pose(position, rotation), _non_noised_pose.Frame);
    }

    public void SetReferencedPose(ReferencedPose pose)
    {
        _non_noised_pose = pose;
        _preevaluated_pose = pose;
    }

    public void SetPose(Pose pose, string frame = null)
    {
        _non_noised_pose = new ReferencedPose(pose, _non_noised_pose.Frame);
    }

    public void SetPose(Vector3 position, Quaternion rotation, string frame)
    {
        if (frame == Name())
            throw new Exception("SetPose: pose.Frame == Name()");
        _non_noised_pose = new ReferencedPose(new Pose(position, rotation), frame);
    }

    public void SetPose(ReferencedPose pose)
    {
        _non_noised_pose = pose;
    }

    public override void CopyFrom(ObjectOfTimeline other, ITimeline newtimeline)
    {
        var obj = other as PhysicalObject;
        base.CopyFrom(other, newtimeline);
        _non_noised_pose = new ReferencedPose(obj._non_noised_pose);
        _preevaluated_pose = new ReferencedPose(obj._preevaluated_pose);
    }

    protected override bool IsStateEqualImpl(ObjectOfTimeline privobj)
    {
        var obj = (PhysicalObject)privobj;

        if (_non_noised_pose != obj._non_noised_pose)
        {
            Debug.Log(
                "ObjectOfTimeline: _pose is not equal pos:"
                    + (_non_noised_pose)
                    + " obj:"
                    + (obj._non_noised_pose)
            );
            return false;
        }

        if (_preevaluated_pose != obj._preevaluated_pose)
        {
            Debug.Log(
                "ObjectOfTimeline: _pose is not equal pos:"
                    + (_preevaluated_pose)
                    + " obj:"
                    + (obj._preevaluated_pose)
            );
            return false;
        }

        return base.IsStateEqualImpl(obj);
    }

    public void SetMovedWith(ObjectId moved_with)
    {
        SetMovedWith_WithoutInterrupt(moved_with);
        InterruptAnimatronic();
    }

    public void SetMovedWith_WithoutInterrupt(ObjectId moved_with)
    {
        if (CurrentReferencedPose().Frame == moved_with)
            return;

        var current_global_pose = GlobalPose();
        var newpose = ReferencedPose.FromGlobalPose(current_global_pose, moved_with, _timeline);
        SetCurrentReferencedPose(newpose);
    }

    public override ObjectOfTimeline Copy(ITimeline newtimeline)
    {
        PhysicalObject obj = new PhysicalObject();
        obj.CopyFrom(this, newtimeline);
        return obj;
    }

    bool PoseIsNoised()
    {
        return PositionNoiseAmplitude != 0 || RotationNoiseAmplitude != 0;
    }

    void SetCurrentReferencedPose(ReferencedPose pose)
    {
        if (PoseIsNoised())
            Debug.Log("SetCurrentReferencedPose: PoseIsNoised()");

        _non_noised_pose = pose;
        _preevaluated_pose = pose;
    }
}
