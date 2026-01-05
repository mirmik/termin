using System;
using System.Collections.Generic;
using UnityEngine;

public class AvatarInLocationTrigger : Trigger
{
    ObjectId avatar_name;
    ObjectId location_name;

    StoryTrigger story_trigger;

    public override long HashCode()
    {
        var a_hash = avatar_name.hash;
        var b_hash = location_name.hash;

        return a_hash + b_hash * 31 + HashCodeUtil.HashCode("AvatarInLocationTrigger");
    }

    public override Trigger Copy()
    {
        var t = new AvatarInLocationTrigger(avatar_name, location_name, story_trigger);
        t.SetExpectation(expectated);
        return t;
    }

    public AvatarInLocationTrigger(ObjectId avatar, ObjectId location, StoryTrigger story_trigger)
    {
        this.avatar_name = avatar;
        this.location_name = location;
        this.story_trigger = story_trigger;
    }

    public override void CheckTriggerImpl(ITimeline tl)
    {
        var location = tl.GetObject(location_name);
        var netpoint = location.GetComponent<NetPoint>();
        if (netpoint == null)
        {
            return;
        }

        bool in_location = netpoint.AvatarOnPoint(avatar_name);
        if (in_location)
            MarkAsExpectated(tl);
    }

    public override void Apply(ITimeline tl)
    {
        story_trigger.Trigger(tl);
    }
}
