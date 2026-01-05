#if UNITY_64
using UnityEngine;
#endif

using System;

public struct BracedCoordinates
{
    public ReferencedPose APose;
    public ReferencedPose BPose;
    public ReferencedPose CPose;
    public ReferencedPose DPose;
    public ReferencedPose EPose;
    public Vector3 Position;
    public Quaternion Rotation;
    public Quaternion OppositeRotation;
    public Vector3 NavPosition;
    public Vector3 TopPosition;
    public Vector3? BotPosition;
    public ReferencedPoint TargetPoint;
    public CornerLeanZoneType CornerLean;

    public BracedCoordinates(
        Vector3 braced_hit = default,
        Quaternion rotation = default,
        Vector3 top_position = default,
        Vector3 nav_position = default,
        Vector3? bot_position = null,
        ReferencedPoint target_point = default
    )
    {
        Position = braced_hit;
        Rotation = rotation;
        OppositeRotation = Quaternion.Euler(-rotation.eulerAngles);
        TopPosition = top_position;
        NavPosition = nav_position;
        BotPosition = bot_position;
        CornerLean = CornerLeanZoneType.None;
        TargetPoint = target_point;
        APose = new ReferencedPose();
        BPose = new ReferencedPose();
        CPose = new ReferencedPose();
        DPose = new ReferencedPose();
        EPose = new ReferencedPose();
    }

    public string info()
    {
        return $"BracedCoordinates(Position: {Position}, Rotation: {Rotation}, TopPosition: {TopPosition}, NavPosition: {NavPosition}, BotPosition: {BotPosition})";
    }

    override public string ToString()
    {
        return info();
    }

    override public bool Equals(object obj)
    {
        throw new NotImplementedException();
    }

    static public bool IsEqual(Quaternion a, Quaternion b)
    {
        if (
            a.x == 0.0f
            && a.y == 0.0f
            && a.z == 0.0f
            && a.w == 0.0f
            && b.x == 0.0f
            && b.y == 0.0f
            && b.z == 0.0f
            && b.w == 0.0f
        )
        {
            return true;
        }

        return a == b;
    }

    //operator ==
    public static bool operator ==(BracedCoordinates a, BracedCoordinates b)
    {
        return a.Position == b.Position
            && IsEqual(a.Rotation, b.Rotation)
            && IsEqual(a.OppositeRotation, b.OppositeRotation)
            && a.TopPosition == b.TopPosition
            && a.NavPosition == b.NavPosition
            && a.BotPosition == b.BotPosition
            && a.CornerLean == b.CornerLean
            && a.APose == b.APose
            && a.BPose == b.BPose
            && a.CPose == b.CPose
            && a.DPose == b.DPose
            && a.EPose == b.EPose;
    }

    //operator !=
    public static bool operator !=(BracedCoordinates a, BracedCoordinates b)
    {
        return !(a == b);
    }

    public override int GetHashCode()
    {
        return Position.GetHashCode()
            ^ Rotation.GetHashCode()
            ^ OppositeRotation.GetHashCode()
            ^ TopPosition.GetHashCode()
            ^ NavPosition.GetHashCode()
            ^ BotPosition.GetHashCode()
            ^ CornerLean.GetHashCode()
            ^ APose.GetHashCode()
            ^ BPose.GetHashCode()
            ^ CPose.GetHashCode()
            ^ DPose.GetHashCode()
            ^ EPose.GetHashCode();
    }
}
