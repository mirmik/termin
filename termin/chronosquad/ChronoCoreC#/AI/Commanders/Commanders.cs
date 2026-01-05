using System;
using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif

public class ExternalCommand
{
    public ActorCommand command;

    public ExternalCommand(ActorCommand command)
    {
        this.command = command;
    }
}

public abstract class BasicAiCommander
{
    EventLine<BasicAiCommander> changes = new EventLine<BasicAiCommander>(true);

    public void AddCard(EventCard<BasicAiCommander> card)
    {
        changes.Add(card);
    }

    public EventLine<BasicAiCommander> Changes => changes;

    public int CountOfCards()
    {
        return changes.CountOfCards();
    }

    public virtual string Info()
    {
        return "BasicAiCommander";
    }

    public BasicAiCommander() { }

    public abstract BasicAiCommander Copy();

    public void Promote(long curstep)
    {
        changes.Promote(curstep, this);
    }

    public virtual void CopyFrom(BasicAiCommander other)
    {
        changes = new EventLine<BasicAiCommander>(other.changes);
    }

    public abstract bool WhatIShouldDo(
        BasicAiController actor,
        long timeline_step,
        long local_step
    );
};
