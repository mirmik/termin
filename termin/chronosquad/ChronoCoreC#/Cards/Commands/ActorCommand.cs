using System.Collections;
using System.Collections.Generic;
using System;

#if UNITY_64
using UnityEngine;
#endif

[Serializable]
public abstract class ActorCommand : BasicMultipleAction
{
    public virtual bool CanBeInterrupted()
    {
        return true;
    }

    public ActorCommand() { }

    public ActorCommand(long local_step) : base(local_step, long.MaxValue) { }

    public ActorCommand(long s, long f) : base(s, f) { }

    public virtual bool Execute(ObjectOfTimeline actor, ITimeline timeline)
    {
        return true;
    }

    public virtual bool ExecuteFirstTime(ObjectOfTimeline actor, ITimeline timeline)
    {
        return false;
    }

    public virtual object Clone()
    {
        return this.MemberwiseClone();
    }

    public ActorCommand CloneWithShift(long shift)
    {
        var start = StartStep;
        var shifted_start = start + shift;
        var clone = (ActorCommand)this.Clone();
        clone.SetStartStep(shifted_start);
        return clone as ActorCommand;
    }

    public virtual void CancelHandler(CommandBufferBehaviour command_buffer) { }

    public virtual void StopHandler(CommandBufferBehaviour command_buffer) { }

    public virtual bool Demasked()
    {
        return true;
    }
}
