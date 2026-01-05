using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif

public class Avatar : PhysicalObject
{
    private ObjectId _attached_to = default(ObjectId);

    public Avatar() { }

    public ObjectId Location => _non_noised_pose.Frame;

    public void SetLocation(ObjectId location)
    {
        _non_noised_pose = new ReferencedPose(
            new Pose(Vector3.zero, Quaternion.identity),
            location
        );
        _preevaluated_pose = _non_noised_pose;
    }

    public void ChangeLocation(ObjectId new_location, long offset = 0)
    {
        if (new_location == default(ObjectId))
            return;

        var loc = Location;
        long step = LocalStep();

        var animatronic = new AvatarMoveAnimatronic(
            start_location: loc,
            finish_location: new_location,
            start_step: step + offset,
            finish_step: step + offset + (long)(Utility.GAME_GLOBAL_FREQUENCY * 0.3f)
        );
        SetNextAnimatronic(animatronic, false);
    }

    public void ChangeLocation(string new_location, long offset = 0)
    {
        ChangeLocation(new ObjectId(new_location), offset);
    }

    public override void CheckAnotherSeenOrHearImpl()
    {
        var location = LocationObject();
        if (location == null)
            return;

        bool has_eyes = HasOculars();
        if (has_eyes)
        {
            CheckAnotherSeenOrHearImpl_Avatar();
        }
    }

    void CheckAnotherSeenOrHearImpl_Avatar()
    {
        var enemies = _timeline.Enemies();
        var location = LocationObject();
        foreach (var enemy in enemies)
        {
            if (enemy.AnybodyCanSeeMe() == CanSee.See)
                continue;

            var distance = Vector3.Distance(GlobalPosition(), enemy.GlobalPosition());
            if (distance < 1.0f)
            {
                enemy.SetAnybodyCanSeeMe(CanSee.See);
                continue;
            }

            var cansee = (_timeline as Timeline).present.IsCanSee(
                location._timeline_index,
                enemy._timeline_index
            );
            if (cansee == CanSee.See)
            {
                enemy.SetAnybodyCanSeeMe(CanSee.See);
                continue;
            }

            if (enemy.AnybodyCanSeeMe() == CanSee.Hear)
                continue;

            var canhear = GameCore.IsCanHear(location, enemy, HearRadius);
            if (canhear)
            {
                enemy.SetAnybodyCanSeeMe(CanSee.Hear);
                continue;
            }
        }
    }

    public ObjectOfTimeline LocationObject()
    {
        return _timeline.GetObject(Location);
    }

    public NetPoint CurrentNetPoint()
    {
        return _timeline.GetObject(Location).GetComponent<NetPoint>();
    }

    public override ObjectOfTimeline Copy(ITimeline newtimeline)
    {
        Avatar avatar = new Avatar();
        avatar.CopyFrom(this, newtimeline);
        return avatar;
    }

    public override void CopyFrom(ObjectOfTimeline other, ITimeline newtimeline)
    {
        var avatar = other as Avatar;
        base.CopyFrom(avatar, newtimeline);
        _attached_to = (other as Avatar)._attached_to;
    }

    public override void PromoteExtended(long local_step)
    {
        if (Location == default(ObjectId))
            return;

        var frame = _non_noised_pose.Frame;
        if (frame == default(ObjectId))
            return;

        if (_attached_to != frame)
        {
            ChangeFrame(_attached_to, frame);
        }
    }

    public bool HasOculars()
    {
        bool is_moving = CurrentAnimatronic() is AvatarMoveAnimatronic;

        if (is_moving)
            return false;

        var location = LocationObject();
        if (location == null)
            return false;

        return location.HasEyes();
    }

    void ChangeFrame(ObjectId previous, ObjectId next)
    {
        if (previous == next)
            return;

        if (previous != default(ObjectId))
        {
            var previous_netpoint = _timeline.GetObject(previous).GetComponent<NetPoint>();
            previous_netpoint?.AttachAvatarImpl(ObjectId(), false);
        }

        if (next != default(ObjectId))
        {
            var next_netpoint = _timeline.GetObject(next).GetComponent<NetPoint>();
            next_netpoint?.AttachAvatarImpl(ObjectId(), true);
        }
    }

    public bool IsLocationHasNetPoint(string location)
    {
        return _timeline.GetObject(location).HasComponent<NetPoint>();
    }

    public void MoveControlled(Vector3 pos)
    {
        if (IsDead || IsPreDead)
            return;

        var controlled = _timeline.GetObject(_dirrect_controlled);
        var actor = controlled as Actor;
        actor.MoveToCommand(pos);
    }

    public MyList<IAStarNode> PathFinding(string end)
    {
        var start = CurrentNetPoint();
        var end_point = _timeline.GetObject(end).GetComponent<NetPoint>();
        return start.PathFinding(end_point);
    }

    public MyList<IAStarNode> PathFinding(NetPoint end)
    {
        var start = CurrentNetPoint();
        return start.PathFinding(end);
    }

    public void MoveToNetworkPoint(NetPoint point, bool ignore_pathfinding = false)
    {
        var location_object = point.Owner;
        bool location_is_camera = location_object is CameraObject;
        bool location_is_door = location_object is AutomaticDoorObject;

        if (location_is_camera)
        {
            Debug.Log("SetLocation: " + Name() + " " + LocalStep());
            var EnableAiControllerEvent = new EnableAiControllerEvent(LocalStep(), false);
            location_object.AddCard(EnableAiControllerEvent);
        }

        // if (location_is_door)
        // {
        // 	var card = new SetControlledHostCard(
        // 		LocalStep() + 1,
        // 		name: location_object.Name(),
        // 		attached_on_forward: true);
        // 	AddCard(card);
        // }

        if (IsDead || IsPreDead)
            return;

        var step = LocalStep();
        ObjectId loc = Location;

        if (ignore_pathfinding)
        {
            var new_location = point.Owner.ObjectId();
            long finish_step = step + (long)(Utility.GAME_GLOBAL_FREQUENCY * 0.3f);
            var animatronic = new AvatarMoveAnimatronic(
                start_location: loc,
                finish_location: new_location,
                start_step: step,
                finish_step: finish_step
            );
            SetNextAnimatronic(animatronic, false);
            return;
        }

        var path = PathFinding(point);
        for (int i = 1; i < path.Count; i++)
        {
            var netpoint = path[i] as NetPoint;
            var new_location = netpoint.Owner.ObjectId();

            long finish_step = step + (long)(Utility.GAME_GLOBAL_FREQUENCY * 0.3f);
            var animatronic = new AvatarMoveAnimatronic(
                start_location: loc,
                finish_location: new_location,
                start_step: step,
                finish_step: finish_step
            );
            step = finish_step;
            loc = new_location;
            SetNextAnimatronic(animatronic, false);
        }
    }

    public void MoveCommand(ObjectId target, bool ignore_pathfinding = false)
    {
        var command = new AvatarMoveCommand(
            target,
            LocalStep() + 1,
            ignore_pathfinding: ignore_pathfinding
        );
        AddExternalCommand(command);
    }
}
