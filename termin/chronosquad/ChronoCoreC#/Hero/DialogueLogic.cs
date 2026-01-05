using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class DialogueMoment
{
    public string Text;
    public string[] Options;
    public DialogueMoment[] Next;
}

public class DialogueLogic
{
    ChronoSphere _chronosphere;

    public DialogueMoment Root;
    public DialogueMoment Current;

    public DialogueLogic(ChronoSphere chronosphere)
    {
        _chronosphere = chronosphere;
    }

    void DisplayMoment(DialogueMoment moment)
    {
        //_chronosphere.DisplayDialogueOptions(moment.Options);
    }

    void Start()
    {
        Current = Root;
    }

    public void EnableDialogue() { }

    public void DisableDialogue() { }

    public void ChooseOption(int option)
    {
        Current = Current.Next[option];
        DisplayMoment(Current);
    }

    public void ExecDialogue()
    {
        DisplayMoment(Current);
    }
}
