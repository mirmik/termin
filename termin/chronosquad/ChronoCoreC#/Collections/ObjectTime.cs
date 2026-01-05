using System.Collections.Generic;
using System;

#if UNITY_64
using UnityEngine;
#endif

public class ObjectTime
{
    long _timeline_zero = 0;
    long _broken_timeline_zero = 0;
    long _non_finished_offset = 0;
    long _finished_offset = 0;
    bool _is_reversed = false;
    MultipleActionList<TimeModifier> _modifiers = new MultipleActionList<TimeModifier>(true);

    public ObjectTime() { }

    public MultipleActionList<TimeModifier> Modifiers => _modifiers;

    public Dictionary<string, object> ToTrent()
    {
        Dictionary<string, object> dict = new Dictionary<string, object>();
        dict["timeline_zero"] = _timeline_zero;
        dict["broken_timeline_zero"] = _broken_timeline_zero;
        dict["non_finished_offset"] = _non_finished_offset;
        dict["finished_offset"] = _finished_offset;
        dict["is_reversed"] = _is_reversed;
        dict["modifiers"] = _modifiers.ToTrent();
        return dict;
    }

    public void FromTrent(Dictionary<string, object> dict)
    {
        _timeline_zero = (long)dict["timeline_zero"];
        _broken_timeline_zero = (long)dict["broken_timeline_zero"];
        _non_finished_offset = (long)dict["non_finished_offset"];
        _finished_offset = (long)dict["finished_offset"];
        _is_reversed = (bool)dict["is_reversed"];
        _modifiers.FromTrent((Dictionary<string, object>)dict["modifiers"]);
    }

    public bool IsEqual(ObjectTime other)
    {
        // var this_modifiers = _modifiers.AsList();
        // var other_modifiers = other._modifiers.AsList();

        if (_modifiers.Count != other._modifiers.Count)
        {
            return false;
        }

        // for (int i = 0; i < this_modifiers.Count; ++i)
        // {
        // 	if (!this_modifiers[i].IsEqual(other_modifiers[i]))
        // 	{
        // 		return false;
        // 	}
        // }

        return true;
    }

    public ObjectTime(ObjectTime other)
    {
        _timeline_zero = other._timeline_zero;
        _broken_timeline_zero = other._broken_timeline_zero;
        _non_finished_offset = other._non_finished_offset;
        _finished_offset = other._finished_offset;
        _modifiers = new MultipleActionList<TimeModifier>(other._modifiers);
        _is_reversed = other._is_reversed;
    }

    public void SetReferencePoint(
        long new_timeline_zero,
        bool newdirection_is_reversed,
        long offset = 0
    )
    {
        long dist = new_timeline_zero - _timeline_zero - offset;
        long broken_dist = _is_reversed ? -dist : dist;
        _broken_timeline_zero += broken_dist;
        _timeline_zero = new_timeline_zero;
        _is_reversed = newdirection_is_reversed;
    }

    public long TimelineZero => _timeline_zero;
    public long BrokenTimelineZero => _broken_timeline_zero;
    public long NonFinishedOffset => _non_finished_offset;
    public long FinishedOffset => _finished_offset;
    public bool IsReversed => _is_reversed;

    public long Offset
    {
        get { return _non_finished_offset + _finished_offset; }
    }

    // b (broken)
    // |   /
    // |  /
    // | .
    // |  \
    // |   \ (timeline_zero)
    // |----.
    // |   / | (broken_timeline_zero)
    // |  /  |
    // | /   |
    // |/    |
    // ------------------------------ t (timeline)
    public long TimelineToBroken(long nonbroken_timeline_step)
    {
        long dist = nonbroken_timeline_step - _timeline_zero;
        long broken_dist = _is_reversed ? -dist : dist;
        long broken = broken_dist + _broken_timeline_zero;
        return broken;
    }

    public long ToBroken(long s)
    {
        return TimelineToBroken(s);
    }

    public void Clean()
    {
        _modifiers.Clean();
    }

    public float ToBroken_Time(float nonbroken_timeline_time)
    {
        float dist = nonbroken_timeline_time - TimelineZero_Time();
        float broken_dist = _is_reversed ? -dist : dist;
        float broken = broken_dist + BrokenTimelineZero_Time();
        return broken;
    }

    public float TimelineZero_Time()
    {
        return (float)_timeline_zero / Utility.GAME_GLOBAL_FREQUENCY;
    }

    public float BrokenTimelineZero_Time()
    {
        return (float)_broken_timeline_zero / Utility.GAME_GLOBAL_FREQUENCY;
    }

    public long BrokenToTimeline(long broken)
    {
        long broken_dist = broken - _broken_timeline_zero;
        long dist = _is_reversed ? -broken_dist : broken_dist;
        long nonbroken_timeline_step = _timeline_zero + dist;
        return nonbroken_timeline_step;
    }

    public long BrokenPointInTimeline()
    {
        return _broken_timeline_zero;
    }

    public string info()
    {
        string text = "";
        long _timeline_zero = TimelineZero;
        long _broken_timeline_zero = BrokenTimelineZero;
        long _non_finished_offset = NonFinishedOffset;
        long _finished_offset = FinishedOffset;
        bool _is_reversed = IsReversed;

        text += "timeline_zero: " + _timeline_zero + "\n";
        text += "broken_timeline_zero: " + _broken_timeline_zero + "\n";
        text += "non_finished_offset: " + _non_finished_offset + "\n";
        text += "finished_offset: " + _finished_offset + "\n";
        text += "is_reversed: " + _is_reversed + "\n";

        // text += "sorted by start: \n";
        // foreach (var modifier in _modifiers.AsList())
        // {
        // 	text += modifier.info() + "\n";
        // }

        // text += "sorted by finish: \n";
        // foreach (var modifier in _modifiers.AsListByFinish())
        // {
        // 	text += modifier.info() + "\n";
        // }

        text += "by_start pos: " + _modifiers.ByStartIteratorPosition() + "\n";
        text += "by_finish pos: " + _modifiers.ByFinishIteratorPosition() + "\n";

        return text;
    }

    public void AddModifier(TimeModifier modifier) => _modifiers.Add(modifier);

    public MyList<TimeModifier> ActiveModifiers() => _modifiers.ActiveStates();

    public long TimelineToLocal(long step)
    {
        var broken_step = TimelineToBroken(step);
        return BrokenToLocal(broken_step);
    }

    public long BrokenToLocal(long broken_step)
    {
        return _non_finished_offset + _finished_offset + broken_step;
    }

    // public long LocalToTimeline(long step)
    // {
    // 	var broken_step = step - _non_finished_offset - _finished_offset;
    // 	var tlstep = BrokenToTimeline(broken_step);
    // 	Debug.Log("LocalToTimeline step: " + step + " broken_step: " + broken_step + " tlstep: " + tlstep);
    // 	return tlstep;
    // }

    public float NonFinishedOffset_Time()
    {
        return _non_finished_offset / Utility.GAME_GLOBAL_FREQUENCY;
    }

    public float FinishedOffset_Time()
    {
        return _finished_offset / Utility.GAME_GLOBAL_FREQUENCY;
    }

    public float TimelineToLocal_Time(float time)
    {
        var broken_time = ToBroken_Time(time);
        return NonFinishedOffset_Time() + FinishedOffset_Time() + broken_time;
    }

    public float TimelineToLocal_Seconds(float t)
    {
        return TimelineToLocal((long)(t * Utility.GAME_GLOBAL_FREQUENCY))
            / Utility.GAME_GLOBAL_FREQUENCY;
    }

    public void UpdateOffset(long step)
    {
        long result = 0;
        foreach (var modifier in ActiveModifiers())
        {
            if (modifier == null)
                continue;

            var modoffset = modifier.TimeOffset(step);
            result += modoffset;
        }
        _non_finished_offset = result;
    }

    public Step TimelineToLocal(Step step)
    {
        return new Step(TimelineToLocal(step.step), step.direction);
    }

    public void Promote(long timeline_step)
    {
        long broken_step = ToBroken(timeline_step);
        //Step broken = new Step(broken_step, timeline_step.direction);

        MyList<TimeModifier> added;
        MyList<TimeModifier> goned;
        TimeDirection direction;
        _modifiers.Promote(broken_step, out added, out goned, out direction);

        if (direction == TimeDirection.Forward)
        {
            foreach (var modifier in goned)
            {
                if (modifier == null)
                    continue;

                _finished_offset += modifier.TimeOffsetOnFinish();
            }
        }
        else
        {
            foreach (var modifier in added)
            {
                if (modifier == null)
                    continue;

                _finished_offset -= modifier.TimeOffsetOnFinish();
            }
        }

        UpdateOffset(broken_step);
    }

    public void DropToCurrentState()
    {
        _modifiers.DropToCurrentState();
    }

    public void DropToCurrentStateInverted()
    {
        _modifiers.DropToCurrentStateInverted();
    }

    public int CountOfModifiers()
    {
        return _modifiers.Count;
    }

    public float CurrentTimeMultiplier()
    {
        float result = 1.0f;
        foreach (var modifier in ActiveModifiers())
        {
            if (modifier == null)
                continue;

            result *= modifier.Multiplier();
        }
        return result;
    }

    public void AddBrokenOffsetToLocalTime(long offset)
    {
        // _finished_offset += offset;
    }
}
