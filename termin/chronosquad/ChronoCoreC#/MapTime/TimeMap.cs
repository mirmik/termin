using System;
using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif

public class TimelineMap
{
    ChronoSphere _chronosphere;

    public TimelineMap(ChronoSphere chronosphere)
    {
        _chronosphere = chronosphere;
    }

    public MyList<Tuple<long, long, long>> Intervals()
    {
        MyList<Tuple<long, long, long>> list = new MyList<Tuple<long, long, long>>();
        foreach (var tl in _chronosphere.Timelines())
        {
            var positive = tl.Value.LastPositiveTimelineStep();
            var negative = tl.Value.LastNegativeTimelineStep();
            var entrance = tl.Value.PrimaryEntranceStep();
            list.Add(new Tuple<long, long, long>(negative, positive, entrance));
        }
        return list;
    }

    public MyList<Timeline> TimelinesInDrawOrder()
    {
        MyList<Timeline> list = new MyList<Timeline>();
        foreach (var tl in _chronosphere.Timelines())
        {
            var child_timelines = tl.Value.ChildTimelines;
            foreach (var child in child_timelines)
            {
                var child_tl = _chronosphere.Timelines()[child.child_timeline_key];
                list.Add(child_tl);
            }
        }
        return list;
    }
}
