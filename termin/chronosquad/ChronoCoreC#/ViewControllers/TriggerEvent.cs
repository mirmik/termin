// using System.Collections;
// using System.Collections.Generic;
// using UnityEngine;

// public class SpeachTriggerEvent : MonoBehaviour
// {
//     DialogueGraph dialogue;
//     public string TriggerName;

//     public string PathToDialogue;

//     void Start ()
//     {
//         string pathbase = GameCore.DialoguePathBase();
//         string path = pathbase + PathToDialogue;

//         var dialogue = DialogueParser.Parse(path);


//         var timeline_controller = GameCore.CurrentTimelineController();
//         var timeline = timeline_controller.GetTimeline();
//     }

//     public void Trigger()
//     {
//         var timeline = GameCore.CurrentTimelineController().GetTimeline();
//         var narative_manager = timeline.NarativeState;
//     }
// }
