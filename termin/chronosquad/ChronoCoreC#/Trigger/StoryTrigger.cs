using UnityEngine;

public class StoryTrigger
{
    public virtual void Trigger(ITimeline tl)
    {
        Debug.LogError("StoryTrigger Trigger");
    }
}

public class StartDialogTrigger : StoryTrigger
{
    public DialogueGraph Dialogue;

    public StartDialogTrigger(DialogueGraph dialogue)
    {
        Dialogue = dialogue;
    }

    public override void Trigger(ITimeline tl)
    {
        var current_step = tl.CurrentStep();
        (tl as Timeline).NarativeState.AddDialogue(Dialogue, current_step);
    }
}

public class StartTimelineScriptTrigger : StoryTrigger
{
    public TimelineScript script;

    public StartTimelineScriptTrigger(TimelineScript script)
    {
        this.script = script;
    }

    public override void Trigger(ITimeline tl)
    {
        var current_step = tl.CurrentStep();
        script.ApplyForTimeline(tl);
    }
}

public class StartScriptTrigger : StoryTrigger
{
    public ControllerScript Script;

    public StartScriptTrigger(ControllerScript script)
    {
        Script = script;
    }

    public override void Trigger(ITimeline tl)
    {
        Script.Execute(tl);
    }
}

public class LevelCompleteTrigger : StoryTrigger
{
    public LevelCompleteTrigger() { }

    public override void Trigger(ITimeline tl)
    {
        GameCore.LevelComplete();
    }
}
