using System.Collections;
using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif

public abstract class ActorBehaviour
{
    protected Actor actor;

    public ActorBehaviour(Actor actor)
    {
        this.actor = actor;
    }

    public Actor Actor()
    {
        return actor;
    }

    public virtual void Promote(Step curstep, ITimeline tl) { }

    abstract public void DropToCurrentState(long local_step);
    abstract public void DropToCurrentStateInverted(long local_step);

    public abstract ActorBehaviour Copy(Actor newactor);

    virtual public void HearNoise(long step, Vector3 center) { }

    public abstract void CleanArtifacts();
    public abstract void Execute(Step timeline_step, Step local_step, Timeline timeline);
}
