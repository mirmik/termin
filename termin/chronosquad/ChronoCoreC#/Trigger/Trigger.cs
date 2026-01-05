using System;
using System.Collections.Generic;
using UnityEngine;

public class TriggerExpectationChangeEvent : GlobalEvent
{
    bool on_forward_status;
    long trigger_hash;

    public TriggerExpectationChangeEvent(long step, bool on_forward_status, long trigger_hash)
        : base(step)
    {
        this.on_forward_status = on_forward_status;
        this.trigger_hash = trigger_hash;
    }

    public override void on_forward_enter(long current_step, ITimeline tl)
    {
        var trigger = tl.GetTrigger(trigger_hash);
        trigger.SetExpectation(on_forward_status);
        trigger.Apply(tl);
    }

    public override void on_backward_enter(long current_step, ITimeline tl)
    {
        var trigger = tl.GetTrigger(trigger_hash);
        trigger.SetExpectation(!on_forward_status);
    }
}

public abstract class Trigger
{
    protected bool expectated = true;

    public abstract void CheckTriggerImpl(ITimeline tl);

    public void CheckTrigger(ITimeline tl)
    {
        if (expectated)
        {
            CheckTriggerImpl(tl);
        }
    }

    public abstract Trigger Copy();

    public void MarkAsExpectated(ITimeline tl)
    {
        var change = new TriggerExpectationChangeEvent(tl.CurrentStep(), false, HashCode());
        tl.AddEvent(change);
    }

    public void SetExpectation(bool status)
    {
        expectated = status;
    }

    public abstract long HashCode();

    public abstract void Apply(ITimeline tl);
}

public class TimeTrigger : Trigger
{
    long target_step;

    StoryTrigger story_trigger;

    public override long HashCode()
    {
        return HashCodeUtil.HashCode(target_step) + HashCodeUtil.HashCode("TimeTrigger");
    }

    public override Trigger Copy()
    {
        var t = new TimeTrigger(target_step, story_trigger);
        t.SetExpectation(expectated);
        return t;
    }

    public TimeTrigger(long target_step, StoryTrigger story_trigger)
    {
        this.target_step = target_step;
        this.story_trigger = story_trigger;
    }

    public override void CheckTriggerImpl(ITimeline tl)
    {
        if (tl.CurrentStep() == target_step)
        {
            var change = new TriggerExpectationChangeEvent(tl.CurrentStep(), false, HashCode());
            tl.AddEvent(change);
        }
    }

    public override void Apply(ITimeline tl)
    {
        story_trigger.Trigger(tl);
    }
}

public class BoxColliderTrig : Trigger
{
    Pose pose;
    Vector3 size;
    long name;

    StoryTrigger story_trigger;

    public override long HashCode()
    {
        var pose_hash = HashCodeUtil.HashCode(pose);
        var size_hash = HashCodeUtil.HashCode(size);
        var name_hash = HashCodeUtil.HashCode(name);

        return pose_hash
            + size_hash * 31
            + name_hash * 31 * 31
            + HashCodeUtil.HashCode("BoxColliderTrig");
    }

    public override Trigger Copy()
    {
        var t = new BoxColliderTrig(pose, size, name, story_trigger);
        t.SetExpectation(expectated);
        return t;
    }

    public BoxColliderTrig(Pose pose, Vector3 size, long name, StoryTrigger story_trigger)
    {
        this.pose = pose;
        this.size = size;
        this.name = name;
        this.story_trigger = story_trigger;
    }

    public override void CheckTriggerImpl(ITimeline tl)
    {
        var global_position = tl.GetObject(name).TorsoPosition();
        var p = pose.InverseTransformPoint(global_position);

        if (p.x < -size.x / 2 || p.x > size.x / 2)
        {
            return;
        }

        if (p.y < -size.y / 2 || p.y > size.y / 2)
        {
            return;
        }

        if (p.z < -size.z / 2 || p.z > size.z / 2)
        {
            return;
        }

        MarkAsExpectated(tl);
    }

    public override void Apply(ITimeline tl)
    {
        Debug.Log("BoxTrigger applied");
        story_trigger.Trigger(tl);
    }
}
