using System;
using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif

class ActorOfGroupCommander : BasicAiCommander
{
    long commander_name = 0;

    GroupController group_controller = null;

    public override BasicAiCommander Copy()
    {
        ActorOfGroupCommander buf = new ActorOfGroupCommander();
        buf.CopyFrom(this);
        return buf;
    }

    void UpdateGroupControllerIfNeed(ObjectOfTimeline actor)
    {
        var tl = actor.GetTimeline();

        if (group_controller == null || group_controller.GetTimeline() != tl)
        {
            group_controller = tl.GetObject(commander_name) as GroupController;
        }
    }

    public override bool WhatIShouldDo(
        BasicAiController aiController,
        long timeline_step,
        long local_step
    )
    {
        var actor = aiController.GetObject();
        UpdateGroupControllerIfNeed(actor);

        if (actor.IsMove())
            return false;

        var cmd = group_controller.WhatIShouldDo(aiController, timeline_step, local_step);

        if (cmd == null)
            return false;

        aiController.GetObject().AddInternalCommand(cmd);
        return true;
    }
}
