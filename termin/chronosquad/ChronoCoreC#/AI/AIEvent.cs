using System.Collections.Generic;
#if UNITY_64
using UnityEngine;
#endif

public abstract class AiControllerEvent : EventCard<ObjectOfTimeline>
{
    public AiControllerEvent(long start_step, long finish_step) : base(start_step, finish_step) { }

    // public abstract void on_forward_enter(long step, Actor actor);
    // public abstract void on_backward_leave(long step, Actor actor);
};
