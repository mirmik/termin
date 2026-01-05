using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class NPCDialogue : MonoBehaviour
{
    public string TalkWith;
    public Collider DialogueCollider;
    ChronosphereController _chronosphere_controller;

    DialogueLogic _dialogue_logic;

    //bool actor_in_trigger = false;

    // Start is called before the first frame update
    void Start()
    {
        _chronosphere_controller = GameObject
            .Find("Timelines")
            .GetComponent<ChronosphereController>();
        var chronosphere = _chronosphere_controller.Chronosphere();
        _dialogue_logic = new DialogueLogic(chronosphere);
    }

    ControlableActor FindPlayer()
    {
        var timeline_controller = _chronosphere_controller.CurrentTimelineController();
        var timeline = _chronosphere_controller.Chronosphere().CurrentTimeline();
        var players = timeline.Heroes();

        foreach (Actor player in players)
        {
            if (player.ProtoId() == TalkWith)
            {
                var ca = timeline_controller.GetActor(player.Name());
                return ca;
            }
        }
        return null;
    }

    public void Say(string text)
    {
        var current_timeline = _chronosphere_controller.Chronosphere().CurrentTimeline();
        current_timeline.AddMessage(text);
    }

    bool PlayerInTrigger()
    {
        ControlableActor player = FindPlayer();
        var is_player_in_trigger = DialogueCollider.bounds.Contains(player.transform.position);
        return is_player_in_trigger;
    }

    // Update is called once per frame
    void Update()
    {
        return;
        // if (!PlayerInTrigger())
        // {
        // 	_dialogue_logic.DisableDialogue();
        // 	if (actor_in_trigger)
        // 	{
        // 		actor_in_trigger = false;
        // 		Say("Goodbye!");
        // 	}

        // 	return;
        // }

        // if (!actor_in_trigger)
        // {
        // 	actor_in_trigger = true;
        // 	Say("Я только сейчас понял. Ты отличаешься.");
        // }

        // _dialogue_logic.ExecDialogue();
    }
}
