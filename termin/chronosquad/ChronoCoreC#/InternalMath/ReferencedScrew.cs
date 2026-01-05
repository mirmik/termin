#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System;

public struct ReferencedScrew : IEquatable<ReferencedScrew>
{
    public Vector3 lin;
    public Vector3 ang;
    public ObjectId Frame;
    public ObjectId FrameHash => Frame;

    public ReferencedScrew(Vector3 lin, Vector3 ang, string frame)
    {
        this.lin = lin;
        this.ang = ang;
        this.Frame = new ObjectId(frame);
    }

    public ReferencedScrew(Vector3 lin, Vector3 ang, ObjectId frame)
    {
        this.lin = lin;
        this.ang = ang;
        this.Frame = frame;
    }

    public ReferencedScrew(ReferencedScrew other) : this(other.lin, other.ang, other.Frame) { }

    public override string ToString()
    {
        return string.Format("ReferencedScrew({0}, {1}, {2})", lin, ang, Frame);
    }

    // equality
    public bool Equals(ReferencedScrew other)
    {
        return lin == other.lin && ang == other.ang && Frame == other.Frame;
    }

    public override bool Equals(object obj)
    {
        if (obj == null || GetType() != obj.GetType())
        {
            return false;
        }
        return Equals((ReferencedScrew)obj);
    }

    public override int GetHashCode()
    {
        if (Frame == default(ObjectId))
        {
            return lin.GetHashCode() ^ ang.GetHashCode();
        }
        return lin.GetHashCode() ^ ang.GetHashCode() ^ Frame.GetHashCode();
    }

    // operators
    static public bool operator ==(ReferencedScrew a, ReferencedScrew b)
    {
        return a.Equals(b);
    }

    static public bool operator !=(ReferencedScrew a, ReferencedScrew b)
    {
        return !a.Equals(b);
    }

    // public Screw GlobalScrew(ITimeline tl)
    // {
    // 	if (Frame == default(ObjectId))
    // 	{
    // 		return new Screw(lin:lin, ang:ang);
    // 	}
    // 	var frame = tl.GetFrame(Frame);
    // 	var frame_global_screw = tl.GetVelocityScrew(Frame);
    // 	var frame_rotation = frame.rotation;
    // 	var alin = frame_rotation * lin + frame_global_screw.lin;
    // 	var aang = frame_rotation * ang + frame_global_screw.ang;
    // 	return new Screw(lin:alin, ang:aang);
    // }


    // public static ReferencedScrew FromGlobalVelocity(Vector3 velocity, ObjectId frame, ITimeline tl)
    // {
    // 	var global_frame_velocity = tl.GetVelocity(frame).GlobalVelocity(tl);
    // 	var local_velocity = tl.GetFrame(frame)
    // 		.InverseTransformVector(velocity - global_frame_velocity);
    // 	return new ReferencedScrew(local_velocity, frame);
    // }

    public Dictionary<string, object> ToTrent()
    {
        Dictionary<string, object> dict = new Dictionary<string, object>();
        dict["lin"] = lin;
        dict["ang"] = ang;
        return dict;
    }

    public void FromTrent(Dictionary<string, object> dict)
    {
        lin = (Vector3)dict["lin"];
        ang = (Vector3)dict["ang"];
    }
}
