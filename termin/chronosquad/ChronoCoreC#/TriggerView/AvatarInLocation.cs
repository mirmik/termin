using System;
using System.Collections.Generic;
using UnityEngine;

public class AvatarInLocation : TriggerView
{
    public string AgentName;

    public void Start()
    {
        TimelineController tc = GameCore.CurrentTimelineController();
        StoryTrigger st = CompileStoryTrigger();

        var trigger = new AvatarInLocationTrigger(
            new ObjectId(AgentName),
            new ObjectId(this.name),
            st
        );

        var timeline = tc.GetTimeline();
        timeline.AddTrigger(trigger);
    }
}
