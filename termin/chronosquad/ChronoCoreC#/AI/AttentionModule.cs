#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;
using System.Linq;
using System;

public struct RestlessnessParameters
{
    public float duration_of_attention;
    public bool lures;

    public RestlessnessParameters(float duration_of_attention, bool lures)
    {
        this.duration_of_attention = duration_of_attention;
        this.lures = lures;
    }

    public bool IsEqual(RestlessnessParameters other)
    {
        return duration_of_attention == other.duration_of_attention && lures == other.lures;
    }

    public override string ToString()
    {
        return string.Format("RestlessnessParameters({0}, {1})", duration_of_attention, lures);
    }

    // operator ==
    public static bool operator ==(RestlessnessParameters a, RestlessnessParameters b)
    {
        return a.IsEqual(b);
    }

    // operator !=
    public static bool operator !=(RestlessnessParameters a, RestlessnessParameters b)
    {
        return !a.IsEqual(b);
    }

    public override int GetHashCode()
    {
        return duration_of_attention.GetHashCode() ^ lures.GetHashCode();
    }

    public override bool Equals(object obj)
    {
        if (obj == null)
            return false;

        if (obj.GetType() != GetType())
            return false;

        var other = (RestlessnessParameters)obj;
        return duration_of_attention == other.duration_of_attention && lures == other.lures;
    }
}

// public class DisturbanceAlarmSource : AlarmSource
// {
// 	public string corpse;

// 	public DisturbanceAlarmSource(long start_step, long final_step, string corpse)
// 		: base(start_step, final_step)
// 	{
// 		this.corpse = corpse;
// 	}

// 	public bool IsEqual(FoundCorpseAlarmSource other)
// 	{
// 		return
// 			corpse == other.corpse &&
// 			base.IsEqual(other);
// 	}

// 	public override ReferencedPoint Center(ITimeline tl)
// 	{
// 		return tl.GetObject(corpse).CurrentReferencedPoint();
// 	}

// 	public override bool IsHighLevelAlarm()
// 	{
// 		return true;
// 	}

// 	public override bool IsCorpseReaction() => true;
// }


public class AttentionModule
{
    public MyList<ObjectId> founded_corpses = new MyList<ObjectId>();

    EventLine<AttentionModule> alarm_sources = new EventLine<AttentionModule>(true);

    public float CorpseAttentionTime = 4.0f;

    public AttentionModule() { }

    public EventLine<AttentionModule> AlarmSourcesList() => alarm_sources;

    public string Info()
    {
        string buf = "AttentionModule: ";
        buf += "founded_corpses: " + founded_corpses.Count;
        buf += "alarm_sources: " + alarm_sources.Count;
        return buf;
    }

    public MyList<EventCard<AttentionModule>> AlarmSources()
    {
        return alarm_sources.ActiveStates();
    }

    public AttentionModule(AttentionModule other)
    {
        founded_corpses = new MyList<ObjectId>(other.founded_corpses);
        alarm_sources = new EventLine<AttentionModule>(other.alarm_sources);
    }

    //public MyList<AlarmSource> AlarmSources() => alarm_sources;

    public bool IsSeenCorpseEarly(ObjectOfTimeline corpse)
    {
        return founded_corpses.Contains(corpse.ObjectId());
    }

    public bool IsEqual(AttentionModule other)
    {
        if (founded_corpses.Count != other.founded_corpses.Count)
            return false;
        if (alarm_sources.IsEqual(other.alarm_sources) == false)
            return false;
        for (int i = 0; i < founded_corpses.Count; i++)
        {
            if (founded_corpses[i] != other.founded_corpses[i])
                return false;
        }
        return true;
    }

    // public void AddFoundedCorpse(long curstep, ObjectId corpse)
    // {
    // 	founded_corpses.Add(corpse);
    // }

    public void FoundCorpse(long curstep, ObjectId corpse)
    {
        var alarm = new FoundCorpseAlarmSource(
            curstep,
            (long)(curstep + CorpseAttentionTime * Utility.GAME_GLOBAL_FREQUENCY),
            corpse
        );
        alarm_sources.Add(alarm);
        founded_corpses.Add(corpse);
    }

    public void ForgetCorpse(ObjectId corpse)
    {
        // в FoundCorpseAlarmSource труп тоже удаляется. Странно это
        founded_corpses.Remove(corpse);
    }

    public void FoundInterest(long curstep, ObjectId interest)
    {
        var alarm = new FoundInterestAlarmSource(
            curstep,
            (long)(curstep + 10.0f * Utility.GAME_GLOBAL_FREQUENCY),
            interest
        );
        alarm_sources.Add(alarm);
    }

    public void HearLoudSound(
        long curstep,
        ReferencedPoint center,
        RestlessnessParameters noise_parameters
    )
    {
        var alarm = new LoudSoundAlarmSource(
            curstep,
            curstep
                + (long)(noise_parameters.duration_of_attention * Utility.GAME_GLOBAL_FREQUENCY),
            center,
            lures: noise_parameters.lures
        );
        alarm_sources.Add(alarm);
    }

    public void ForgetLoudSound(ReferencedPoint center) { }

    public AlarmSource LastAlarmSource()
    {
        return alarm_sources.ActiveStates().Last() as AlarmSource;
    }

    public bool IsPanic()
    {
        return alarm_sources.ActiveStates().Count > 0;
    }

    public void Promote(long curstep)
    {
        alarm_sources.Promote(curstep, this);
    }

    public MyList<ObjectId> FoundedCorpses => founded_corpses;

    public void DropToCurrentState(long curstep)
    {
        alarm_sources.DropToCurrentState();
    }

    public void DropToCurrentStateInverted(long curstep)
    {
        alarm_sources.DropToCurrentStateInverted();
    }
}
