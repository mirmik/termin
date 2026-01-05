using UnityEngine;

public class OnSceneStartTrigger : TriggerView
{
    public void Start()
    {
        TimelineController tc = GameCore.CurrentTimelineController();
        StoryTrigger st = CompileStoryTrigger();

        var trigger = new TimeTrigger(1, st);

        var timeline = tc.GetTimeline();
        timeline.AddTrigger(trigger);
    }
}
