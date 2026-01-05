using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif
public class FireWall : ItemComponent
{
    NetPoint _netpoint;

    public FireWall(ObjectOfTimeline owner) : base(owner) { }

    public override void Start()
    {
        _netpoint = _owner.GetComponent<NetPoint>();
    }

    public override ItemComponent Copy(ObjectOfTimeline owner)
    {
        return new FireWall(owner);
    }

    public override void Execute(long timeline_step, long local_step)
    {
        if (_netpoint == null)
        {
            return;
        }

        foreach (var avatar_name in _netpoint.avatars_in_point)
        {
            var avatar = Owner.GetTimeline().GetObject(avatar_name);
            if (avatar.IsDead || !avatar.IsMaterial())
            {
                continue;
            }

            if (avatar.IsHero())
            {
                var death_event = new DeathEvent(
                    timeline_step + 1,
                    avatar,
                    who_kill_me: Owner.Name(),
                    reversed: false
                );
                Owner.GetTimeline().AddEvent(death_event);
            }
        }
    }
}
