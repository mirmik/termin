#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System;

public struct ReferencedPoint : IEquatable<ReferencedPoint>, ITrentCompatible
{
    public Vector3 LocalPosition;
    public ObjectId Frame;
    public ObjectId FrameHash => Frame;

    public object ToTrent()
    {
        return new Dictionary<string, object>
        {
            { "lpos", SimpleJsonParser.Vector3ToTrent(LocalPosition) },
            { "frame", Frame.name }
        };
    }

    public void FromTrent(object obj)
    {
        var dct = (Dictionary<string, object>)obj;
        LocalPosition = SimpleJsonParser.Vector3FromTrent(dct["lpos"]);
        Frame = new ObjectId((string)dct["frame"]);
    }

    public ReferencedPoint(Vector3 position, ObjectId frame)
    {
        this.LocalPosition = position;
        this.Frame = frame;
    }

    public ReferencedPoint(Vector3 position, string frame)
    {
        if (frame == "")
        {
            frame = null;
        }

        this.LocalPosition = position;
        this.Frame = new ObjectId(frame);
    }

    public ReferencedPoint(ReferencedPoint other) : this(other.LocalPosition, other.Frame) { }

    public override string ToString()
    {
        return string.Format("ReferencedPoint({0}, {1})", LocalPosition, Frame);
    }

    // equality
    public bool Equals(ReferencedPoint other)
    {
        return LocalPosition == other.LocalPosition && Frame == other.Frame;
    }

    public override bool Equals(object obj)
    {
        if (obj == null || GetType() != obj.GetType())
        {
            return false;
        }
        return Equals((ReferencedPoint)obj);
    }

    public override int GetHashCode()
    {
        if (Frame == default(ObjectId))
        {
            return LocalPosition.GetHashCode();
        }
        return LocalPosition.GetHashCode() ^ Frame.GetHashCode();
    }

    // operators
    static public bool operator ==(ReferencedPoint a, ReferencedPoint b)
    {
        return a.Equals(b);
    }

    static public bool operator !=(ReferencedPoint a, ReferencedPoint b)
    {
        return !a.Equals(b);
    }

    public float DistanceTo(ReferencedPoint other, ITimeline tl)
    {
        if (Frame == other.Frame)
        {
            return Vector3.Distance(LocalPosition, other.LocalPosition);
        }

        var other_global_position = other.GlobalPosition(tl);
        return Vector3.Distance(GlobalPosition(tl), other_global_position);
    }

    public Vector3 GlobalPosition(ITimeline tl)
    {
        if (Frame == default(ObjectId))
        {
            return LocalPosition;
        }

        var frame_pose = tl.GetFrame(Frame);
        return frame_pose.TransformPoint(LocalPosition);
    }

    public float Distance(ReferencedPoint other, ITimeline tl)
    {
        return Vector3.Distance(GlobalPosition(tl), other.GlobalPosition(tl));
    }

    public static ReferencedPoint FromGlobalPosition(Vector3 position, ObjectId frame, ITimeline tl)
    {
        var frame_pose = tl.GetFrame(frame);
        var local_position = frame_pose.InverseTransformPoint(position);
        return new ReferencedPoint(local_position, frame);
    }
}
