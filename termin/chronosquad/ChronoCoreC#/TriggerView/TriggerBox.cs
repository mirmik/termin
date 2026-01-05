using System;
using System.Collections.Generic;
using UnityEngine;

public class TriggerBox : TriggerView
{
    public string AgentName;

    public void Start()
    {
        TimelineController tc = GameCore.CurrentTimelineController();
        StoryTrigger st = CompileStoryTrigger();

        var trigger = new BoxColliderTrig(
            new Pose(transform.position, transform.rotation),
            transform.localScale,
            Utility.StringHash(AgentName),
            st
        );

        var timeline = tc.GetTimeline();
        timeline.AddTrigger(trigger);
    }
}
