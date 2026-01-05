using System;
using System.Collections.Generic;

public abstract class ControllerScript : EventCard<ITimeline>
{
    public ControllerScript(long step) : base(step) { }

    public abstract void Execute(ITimeline tl);
}
