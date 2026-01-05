using System.Collections;
using System.Collections.Generic;
using System;
using UnityEngine;

public enum PatrolPointType
{
    Walk,
    Fly,
    Teleport,
    ServiceSystemCheck,
}

public enum PatrolStatePhase
{
    Move,
    RotateAfterMove,
    Jump,
    Interaction,
    Blink,
    Stand,
    MoveToObject,
    Finished
}

public struct PatrolStateStruct
{
    public int point_no;
    public long start_step;
    public PatrolPointStateStruct phase;

    public PatrolStateStruct(int point_no, PatrolPointStateStruct phase, long start_step)
    {
        this.phase = phase;
        this.point_no = point_no;
        this.start_step = start_step;
    }

    override public string ToString()
    {
        return string.Format("PatrolStateStruct({0}, {1}, {2})", point_no, phase, start_step);
    }

    public bool IsEqual(PatrolStateStruct other)
    {
        return point_no == other.point_no
            && start_step == other.start_step
            && phase.phase == other.phase.phase;
    }

    override public bool Equals(object obj)
    {
        if (obj == null)
            return false;

        if (obj.GetType() != GetType())
            return false;

        var other = (PatrolStateStruct)obj;
        return point_no == other.point_no
            && start_step == other.start_step
            && phase.phase == other.phase.phase;
    }

    //operator ==
    public static bool operator ==(PatrolStateStruct a, PatrolStateStruct b)
    {
        return a.point_no == b.point_no
            && a.start_step == b.start_step
            && a.phase.phase == b.phase.phase;
    }

    //operator !=
    public static bool operator !=(PatrolStateStruct a, PatrolStateStruct b)
    {
        return !(a == b);
    }

    public override int GetHashCode()
    {
        return point_no.GetHashCode() ^ start_step.GetHashCode() ^ phase.phase.GetHashCode();
    }
}

public struct PatrolPointStateStruct
{
    public PatrolStatePhase phase;

    public PatrolPointStateStruct(PatrolStatePhase phase)
    {
        this.phase = phase;
    }
}

public class PatrolPoint : ITrentCompatible
{
    public PatrolPointType type = PatrolPointType.Walk;
    public ReferencedPose pose;
    public float stand_time = 0.0f;
    public string interaction_object_name = null;

    //public int index = -1;

    public PatrolPoint() { }

    public PatrolPoint(
        ReferencedPose pose,
        float stand_time = 0.0f,
        string interaction_object_name = null,
        PatrolPointType patrolPointType = PatrolPointType.Walk
    )
    {
        this.pose = pose;
        this.stand_time = stand_time;
        this.type = patrolPointType;
        this.interaction_object_name = interaction_object_name;
    }

    public PatrolPoint(
        Vector3 v,
        float stand_time = 0.0f,
        string interaction_object_name = null,
        PatrolPointType patrolPointType = PatrolPointType.Walk
    )
    {
        this.pose = new ReferencedPose(new Pose(v, Quaternion.identity), "");
        this.stand_time = stand_time;
        this.type = patrolPointType;
        this.interaction_object_name = interaction_object_name;
    }

    object ITrentCompatible.ToTrent()
    {
        var dct = new Dictionary<string, object>();
        dct["pose"] = pose.ToTrent();
        dct["stand_time"] = stand_time;
        dct["type"] = (int)type;
        dct["interaction_object_name"] = interaction_object_name;
        return dct;
    }

    void ITrentCompatible.FromTrent(object obj)
    {
        var dct = obj as Dictionary<string, object>;
        pose = new ReferencedPose();
        pose.FromTrent(dct["pose"]);
        stand_time = (float)(double)dct["stand_time"];
        type = (PatrolPointType)(int)(double)dct["type"];
        interaction_object_name = (string)dct["interaction_object_name"];
    }

    public PatrolPoint(
        ReferencedPose pose,
        float stand_time,
        PatrolPointType patrolPointType,
        string interaction_object_name
    )
    {
        //this.index = index;
        this.pose = pose;
        this.stand_time = stand_time;
        this.type = patrolPointType;
        this.interaction_object_name = interaction_object_name;
    }

    // public PatrolPoint(
    // 	Pose pose,
    // 	float stand_time = 0.0f,
    // 	PatrolPointType patrolPointType = PatrolPointType.Walk,
    // 	string interaction_object_name = null)
    // {
    // 	this.pose = new ReferencedPose(pose, "");
    // 	this.stand_time = stand_time;
    // 	this.type = patrolPointType;
    // 	this.interaction_object_name = interaction_object_name;
    // }

    public PatrolPointStateStruct StartPhase()
    {
        switch (type)
        {
            case PatrolPointType.Walk:
                return new PatrolPointStateStruct(PatrolStatePhase.Move);

            case PatrolPointType.Fly:
                return new PatrolPointStateStruct(PatrolStatePhase.Jump);

            case PatrolPointType.Teleport:
                return new PatrolPointStateStruct(PatrolStatePhase.Blink);

            case PatrolPointType.ServiceSystemCheck:
                return new PatrolPointStateStruct(PatrolStatePhase.MoveToObject);

            default:
                return new PatrolPointStateStruct(PatrolStatePhase.Finished);
        }
    }

    public PatrolPointStateStruct NextPhase(
        PatrolPointStateStruct current_phase,
        bool ignore_zero_stand_time
    )
    {
        switch (type)
        {
            case PatrolPointType.Walk:
                switch (current_phase.phase)
                {
                    case PatrolStatePhase.Move:
                        return new PatrolPointStateStruct(PatrolStatePhase.RotateAfterMove);
                    case PatrolStatePhase.RotateAfterMove:
                        return new PatrolPointStateStruct(PatrolStatePhase.Stand);
                    default:
                        return new PatrolPointStateStruct(PatrolStatePhase.Finished);
                }

            case PatrolPointType.Fly:
                return new PatrolPointStateStruct(PatrolStatePhase.Finished);

            case PatrolPointType.Teleport:
                return new PatrolPointStateStruct(PatrolStatePhase.Finished);

            case PatrolPointType.ServiceSystemCheck:
                if (current_phase.phase == PatrolStatePhase.MoveToObject)
                {
                    return new PatrolPointStateStruct(PatrolStatePhase.Interaction);
                }
                else
                {
                    return new PatrolPointStateStruct(PatrolStatePhase.Finished);
                }

            default:
                return new PatrolPointStateStruct(PatrolStatePhase.Finished);
        }
    }

    public string info()
    {
        return pose.ToString();
    }

    override public string ToString()
    {
        return pose.ToString();
    }
}
