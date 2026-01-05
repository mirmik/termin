using System.Collections.Generic;
using UnityEngine;

public struct NetPointConnectionRec
{
    public ObjectId name;
    public bool admin_flag;

    public NetPointConnectionRec(ObjectId name, bool admin_flag)
    {
        this.name = name;
        this.admin_flag = admin_flag;
    }
}

// class ChangeNetPointFormatStateCard : EventCard<ObjectOfTimeline>
// {
// 	//bool enable_on_forward;

// 	public ChangeNetPointFormatStateCard(
// 		long step,
// 		long end
// 		) : base(step, end)
// 	{
// 		//enable_on_forward = format_this_netpoint;
// 	}

// 	public override void on_forward_enter(long current_step, ObjectOfTimeline obj)
// 	{
// 		obj.GetComponent<NetPoint>()._format_this_netpoint = true;
// 	}

// 	public override void on_forward_leave(long current_step, ObjectOfTimeline obj)
// 	{
// 		obj.GetComponent<NetPoint>()._format_this_netpoint = false;
// 	}
// 	public override void on_backward_enter(long current_step, ObjectOfTimeline obj)
// 	{
// 		obj.GetComponent<NetPoint>()._format_this_netpoint = true;
// 	}
// 	public override void on_backward_leave(long current_step, ObjectOfTimeline obj)
// 	{
// 		obj.GetComponent<NetPoint>()._format_this_netpoint = false;
// 	}

// 	public override void update(long current_step, ObjectOfTimeline obj)
// 	{
// 		obj.GetComponent<NetPoint>()._format_this_netpoint = false;
// 	}
// }

public class NetPoint : ItemComponent, IAStarNode
{
    int _format_zone_mark = 0;

    MyList<NetPointConnectionRec> linked_with = new MyList<NetPointConnectionRec>();
    public MyList<ObjectId> avatars_in_point = new MyList<ObjectId>();

    public NetPoint() : base(null) { }

    public NetPoint(ObjectOfTimeline obj) : base(obj) { }

    public MyList<ObjectId> AvatarInPoint => avatars_in_point;

    public float HeuristicDistance(IAStarNode node)
    {
        return 1.0f;
    }

    public void AttachAvatar(ObjectId avatar_name, bool is_attached)
    {
        var card = new AvatarInPointChangeCard(avatar_name, is_attached, Owner.LocalStep() + 1);
        Owner.AddCard(card);
    }

    public void StartFormatCommand(Timeline timeline, long timeline_step)
    {
        var circular_format_event = new CircularFormatEvent(
            timeline_step,
            timeline.GetNetworkMap().Graph,
            this
        );
        timeline.AddEvent(circular_format_event);
    }

    public void AttachAvatarImpl(ObjectId avatar_name, bool is_attached)
    {
        if (is_attached)
        {
            if (!avatars_in_point.Contains(avatar_name))
            {
                avatars_in_point.Add(avatar_name);
            }
        }
        else
        {
            if (avatars_in_point.Contains(avatar_name))
            {
                avatars_in_point.Remove(avatar_name);
            }
        }
    }

    public MyList<IAStarEdge> EdgesOfThisNode(MyList<IAStarEdge> edges)
    {
        var result = new MyList<IAStarEdge>();
        foreach (var edge in edges)
        {
            if (edge.Contains(this))
            {
                result.Add(edge);
            }
        }
        return result;
    }

    public override void Start()
    {
        (Owner.GetTimeline() as Timeline).GetNetworkMap().AddNetPoint(this);
    }

    public bool IsFormatThisNetpointActive()
    {
        return IsFormatedMarkActive();
    }

    public override void Promote(long local_step) { }

    void FormatThisNetpoint()
    {
        foreach (var avatar in avatars_in_point)
        {
            var obj = Owner.GetTimeline().GetObject(avatar) as Avatar;
            var timeline_step = Owner.GetTimeline().CurrentStep();
            var death_event = new DeathEvent(
                timeline_step + 1,
                obj,
                reversed: false,
                who_kill_me: Owner.Name()
            );
            Owner.GetTimeline().AddEvent(death_event);

            obj.ChangeLocation(default(ObjectId));
        }
    }

    public override void Execute(long local_step, long timeline_step)
    {
        if (IsFormatThisNetpointActive())
            FormatThisNetpoint();
    }

    public bool AvatarOnPoint(ObjectId name)
    {
        return avatars_in_point.Contains(name);
    }

    public MyList<ObjectId> GetObjects()
    {
        return avatars_in_point;
    }

    public override ItemComponent Copy(ObjectOfTimeline newowner)
    {
        var obj = new NetPoint(newowner);
        foreach (var link in linked_with)
        {
            obj.AddLink(link);
        }
        foreach (var avatar in avatars_in_point)
        {
            obj.AttachAvatarImpl(avatar, true);
        }
        return obj;
    }

    public void AddLink(NetPointConnectionRec n)
    {
        linked_with.Add(n);
    }

    public void AddLink(ObjectId n, bool admin_flag)
    {
        linked_with.Add(new NetPointConnectionRec(n, admin_flag));
    }

    public void AddConnection(NetPointConnectionRec n)
    {
        linked_with.Add(n);
    }

    public void AddConnection(NetPoint point)
    {
        linked_with.Add(new NetPointConnectionRec(point.Owner.ObjectId(), false));
    }

    public MyList<NetPointConnectionRec> GetLinks()
    {
        return linked_with;
    }

    public MyList<IAStarNode> PathFinding(NetPoint end)
    {
        return (Owner.GetTimeline() as Timeline).GetNetworkMap().PathFinding(this, end);
    }

    public void IncrementFormatedZoneMark()
    {
        _format_zone_mark++;
    }

    public void DecrementFormatedZoneMark()
    {
        _format_zone_mark--;
    }

    public bool IsFormatedMarkActive()
    {
        return _format_zone_mark > 0;
    }
}
