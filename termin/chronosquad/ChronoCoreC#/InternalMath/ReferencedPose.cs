#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System;

public struct ReferencedPose : IEquatable<ReferencedPose>, ITrentCompatible
{
    public Pose pose;
    public ObjectId Frame;

    public ObjectId FrameHash => Frame;

    public ReferencedPose(Pose pose, string frame)
    {
        if (frame == "")
        {
            frame = null;
        }
        this.pose = pose;
        this.Frame = new ObjectId(frame);
    }

    public ReferencedPose(Pose pose, ObjectId frame)
    {
        this.pose = pose;
        this.Frame = frame;
    }

    public ReferencedPose(ReferencedPose other) : this(other.pose, other.Frame) { }

    public ReferencedPose(Vector3 position, Quaternion rotation, string frame)
    {
        this.pose = new Pose(position, rotation);
        this.Frame = new ObjectId(frame);
    }

    public ReferencedPose(Vector3 position, Quaternion rotation, ObjectId frame)
    {
        this.pose = new Pose(position, rotation);
        this.Frame = frame;
    }

    public ReferencedPose(Vector3 position, Vector3 direction, string frame)
    {
        var rotation = Quaternion.LookRotation(direction);
        this.pose = new Pose(position, rotation);
        this.Frame = new ObjectId(frame);
    }

    public ReferencedPose(Vector3 position, Vector3 direction, ObjectId frame)
    {
        var rotation = Quaternion.LookRotation(direction);
        this.pose = new Pose(position, rotation);
        this.Frame = frame;
    }

    public ReferencedPoint ToPoint()
    {
        return new ReferencedPoint(pose.position, Frame);
    }

    public Pose LocalPose()
    {
        return pose;
    }

    public Vector3 LocalPosition()
    {
        return pose.position;
    }

    public void SetLocalPosition(Vector3 position)
    {
        pose.position = position;
    }

    public Vector3 GlobalDirection(ITimeline tl)
    {
        if (Frame == default(ObjectId))
            return pose.rotation * Vector3.forward;

        var global_pose = GlobalPose(tl);
        return global_pose.rotation * Vector3.forward;
    }

    public Pose Divide(ReferencedPose other, ITimeline tl)
    {
        var global_pose = GlobalPose(tl);
        var other_global_pose = other.GlobalPose(tl);
        var divpose = global_pose.Divide(other_global_pose);
        return divpose;
    }

    public void SetLocalRotation(Quaternion rotation)
    {
        pose.rotation = rotation;
    }

    public Quaternion LocalRotation()
    {
        return pose.rotation;
    }

    public Vector3 LocalDirection()
    {
        return pose.rotation * Vector3.forward;
    }

    public override string ToString()
    {
        return string.Format("ReferencedPose({0}, {1})", pose, Frame);
    }

    public Pose GlobalPose(ITimeline tl)
    {
        if (Frame == default(ObjectId))
            return pose;

        var frame = tl.GetFrame(FrameHash);
        return frame * pose;
    }

    public Pose GlobalPose_RealTime(ITimeline tl)
    {
        if (Frame == default(ObjectId))
            return pose;

        var obj = tl.GetObject(FrameHash);
        var frame = obj.PoseProphet();
        return frame * pose;
    }

    public Vector3 GlobalPosition(ITimeline tl)
    {
        if (Frame == default(ObjectId))
            return pose.position;

        var frame = tl.GetFrame(FrameHash);
        return frame.TransformPoint(pose.position);
    }

    public void SetGlobalRotation(Quaternion rotation, ITimeline tl)
    {
        if (Frame == default(ObjectId))
        {
            pose.rotation = rotation;
            return;
        }

        var frame = tl.GetFrame(FrameHash);
        var local_rotation = frame.Inverse().rotation * rotation;
        pose.rotation = local_rotation;
    }

    // equality
    public bool Equals(ReferencedPose other)
    {
        return pose == other.pose && Frame == other.Frame;
    }

    public override bool Equals(object obj)
    {
        if (obj == null || GetType() != obj.GetType())
        {
            return false;
        }
        return Equals((ReferencedPose)obj);
    }

    public override int GetHashCode()
    {
        if (Frame == default(ObjectId))
        {
            return pose.GetHashCode();
        }

        return pose.GetHashCode() ^ Frame.GetHashCode();
    }

    // operators
    static public bool operator ==(ReferencedPose a, ReferencedPose b)
    {
        return a.Equals(b);
    }

    static public bool operator !=(ReferencedPose a, ReferencedPose b)
    {
        return !a.Equals(b);
    }

    public object ToTrent()
    {
        Dictionary<string, object> dict = new Dictionary<string, object>();
        dict["pose"] = pose.ToTrent();
        dict["frame"] = Frame.name;
        return dict;
    }

    public void FromTrent(object objdict)
    {
        var dict = (Dictionary<string, object>)objdict;
        pose.FromTrent((Dictionary<string, object>)dict["pose"]);
        Frame = new ObjectId((string)dict["frame"]);
    }

    public static ReferencedPose FromGlobalPose(Pose position, ObjectId frame, ITimeline tl)
    {
        if (frame == default(ObjectId))
            return new ReferencedPose(position, frame);
        var frame_pose = tl.GetFrame(frame);
        var local_pose = frame_pose.Inverse() * position;
        return new ReferencedPose(local_pose, frame);
    }
}
