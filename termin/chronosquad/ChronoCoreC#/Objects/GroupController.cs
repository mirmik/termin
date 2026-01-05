using System.Collections.Generic;
using System;

#if UNITY_64
using UnityEngine;
#endif

public class GroupController : PhysicalObject
{
    MyList<string> objects = new MyList<string>();
    GroupStrategy _current_strategy;

    public override void FromTrent(Dictionary<string, object> dict)
    {
        base.FromTrent(dict);
        //objects = (MyList<string>)dict["objects"];
    }

    public void StartSearch(long step)
    {
        AddCard(new SearchStrategy(step, new MyList<Vector3>()));
    }

    public MyList<Actor> Members()
    {
        var members = new MyList<Actor>();
        foreach (var member_name in objects)
        {
            var member = GetTimeline().GetActor(member_name);
            members.Add(member);
        }
        return members;
    }

    public MyList<string> ActorList()
    {
        return objects;
    }

    public void AddMember(Actor actor)
    {
        objects.Add(actor.Name());
    }

    public override void PromoteExtended(long local_step) { }

    public ActorCommand WhatIShouldDo(BasicAiController actor, long timeline_step, long local_step)
    {
        return null;
        //    changes.Execute(timeline_step, this);
    }

    public void PassiveExecute(long local_step, long timeline_step) { }

    public override void ExecuteExtended(long timeline_step, long local_step)
    {
        if (_current_strategy != null)
        {
            _current_strategy.Execute(this.GetTimeline(), this);
        }
        else
        {
            PassiveExecute(local_step, timeline_step);
        }
    }

    public void SetChilds(MyList<Actor> childs)
    {
        foreach (var child in childs)
        {
            AddMember(child);
        }
    }

    // public override void DropToCurrentState()
    // {
    // }

    public GroupStrategy GetStrategy()
    {
        return _current_strategy;
    }

    public void SetStrategy(GroupStrategy strategy)
    {
        _current_strategy = strategy;
    }

    public override ObjectOfTimeline Copy(ITimeline newtimeline)
    {
        GroupController obj = new GroupController();
        obj.CopyFrom(this, newtimeline);
        return obj;
    }

    public void CopyFrom(GroupController other, ITimeline newtimeline)
    {
        base.CopyFrom(other, newtimeline);

        objects = new MyList<string>(other.objects);
        _current_strategy = other._current_strategy;
    }
}
