using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public enum TriggerType
{
    Dialog,
    LevelFinish
}

public class TriggerView : MonoBehaviour
{
    public TriggerType Type = TriggerType.Dialog;
    public string ScriptPath;
    public MyList<GameObject> Points;

    protected TimelineScript CompileDialogueGraph()
    {
        var path = GameCore.DialoguePathBase() + ScriptPath;
        var dg = DialogueParser.Parse(path);
        dg.SetPoints(Points);
        return dg;
    }

    protected StoryTrigger CompileStoryTrigger()
    {
        switch (Type)
        {
            case TriggerType.Dialog:
            {
                var dc = CompileDialogueGraph();
                return new StartTimelineScriptTrigger(dc);
            }
            case TriggerType.LevelFinish:
            {
                return new LevelCompleteTrigger();
            }
            default:
                return null;
        }
    }
}
