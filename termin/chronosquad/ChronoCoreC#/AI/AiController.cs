using System;
using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif

public abstract class AiController
{
    protected bool _is_enabled = true;
    public AttentionModule attention_module = new AttentionModule();
    protected ObjectOfTimeline actor;

    public AiController(ObjectOfTimeline actor)
    {
        this.actor = actor;
    }

    public virtual void ConfusedWhileGrabbedAnother(long duration, ObjectId grabber) { }

    public virtual string Info()
    {
        string s = "AiController";
        if (!_is_enabled)
            s += " disabled";
        else
            s += " enabled";
        //s += "Changes: " + changes.CountOfCards();
        s += "Actor: " + actor.Name();
        return s;
    }

    public AttentionModule AttentionModule()
    {
        return attention_module;
    }

    public void SetEnabled(bool value)
    {
        _is_enabled = value;
    }

    public bool IsEnabled()
    {
        return _is_enabled;
    }

    // public EventLine<ObjectOfTimeline> Changes
    // {
    // 	get { return changes; }
    // }

    public virtual bool IsAlarmState()
    {
        return false;
    }

    public virtual bool IsQuestionState()
    {
        return false;
    }

    // public virtual int CountOfCards()
    // {
    // 	//int count = changes.CountOfCards();
    // 	//return count;
    // }

    public virtual void DropToCurrentState(long local_step)
    {
        //changes.DropToCurrentState();
    }

    public AttentionModule GetAttentionModule()
    {
        return attention_module;
    }

    public virtual void DropToCurrentStateInverted(long local_step)
    {
        //changes.DropToCurrentStateInverted();
    }

    public ObjectOfTimeline GetObject()
    {
        return actor;
    }

    public virtual void Promote(long curstep, ITimeline tl)
    {
        //changes.Promote(curstep, actor);
    }

    public abstract void Execute(long timeline_step, long local_step, ITimeline timeline);

    virtual public void HearNoise(
        long step,
        ReferencedPoint center,
        RestlessnessParameters noise_parameters
    ) { }

    public void AddChange(AiControllerEvent card)
    {
        actor.AddCard(card);
    }

    public virtual void CleanArtifacts() { }

    public void AddCard(AiControllerEvent card)
    {
        actor._changes.Add(card);
    }

    public void CopyFrom(AiController other, ObjectOfTimeline newactor)
    {
        _is_enabled = other._is_enabled;
        this.actor = newactor;
    }

    public virtual AiController Copy(ObjectOfTimeline newactor)
    {
        throw new NotImplementedException();
    }

    public bool IsEqual(AiController other)
    {
        if (other == null)
            return false;
        if (other.GetType() != GetType())
            return false;
        if (other._is_enabled != _is_enabled)
            return false;
        //if (!changes.IsEqual(other.changes))
        //	return false;
        return true;
    }
}
