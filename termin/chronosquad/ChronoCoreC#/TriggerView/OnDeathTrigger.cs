using System;
using System.Collections.Generic;
using UnityEngine;

public class AddOnDeathTrigger : MonoBehaviour
{
    public string PathToDialogue;
    public string SayText;

    //TimelineScript timeline_trigger;
    StoryTrigger _trigger = null;

    void Start()
    {
        TimelineScript dc = CompileDialogueGraph();
        _trigger = new StartTimelineScriptTrigger(dc);

        var objctr = GetComponent<ObjectController>();
        objctr.GetObject().AddOnDeathTrigger(_trigger);
    }

    TimelineScript CompileDialogueGraph()
    {
        if (SayText != null && SayText.Length > 0)
        {
            var dg2 = new DialogueGraph();
            var node = new DialogueNode();
            node.text = SayText;
            dg2.entrance = node;
            var ts = new TimelineScriptApplyDialogueGraph(dg2);
            return ts;
        }

        var path = GameCore.DialoguePathBase() + PathToDialogue;
        var dg = DialogueParser.Parse(path);
        return dg;
    }

    // public void Start()
    // {
    // 	TimelineController tc = GameCore.CurrentTimelineController();
    // 	StoryTrigger st = new StartDialogTrigger(dc);

    // 	var trigger = new BoxColliderTrig(
    // 		new Pose(transform.position, transform.rotation),
    // 		transform.localScale,
    // 		TriggerObjectName,
    // 		st);

    // 	var timeline = tc.GetTimeline();
    // 	timeline.AddTrigger(trigger);
    // }
}
