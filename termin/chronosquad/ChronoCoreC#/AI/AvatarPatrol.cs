using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class AvatarPatrolAiController : AiController
{
    public AvatarPatrolAiController(ObjectOfTimeline obj) : base(obj) { }

    void IdlePhase(long step)
    {
        var avatar = GetObject() as Avatar;
        var netpoint = avatar.CurrentNetPoint();
        var links = netpoint.GetLinks();

        // pseudorandom
        long pseudorandom = Easing.PseudoRandomInt(step);
        int index = (int)(pseudorandom % links.Count);
        var link = links[index];

        avatar.MoveCommand(link.name);
    }

    void CommandReaction(long timeline_step, long local_step, ITimeline timeline)
    {
        var avatar = GetObject() as Avatar;
        var netpoint = avatar.CurrentNetPoint();
        var links = netpoint.GetLinks();

        var animatronic = avatar.CurrentAnimatronic();
        var current_command = avatar.CommandBuffer().CurrentCommand();
        if (animatronic is IdleAnimatronic && current_command == null)
        {
            IdlePhase(local_step);
        }
    }

    MyList<Avatar> GetHeroesInCurrentNetPoint(ITimeline tl)
    {
        var avatar = GetObject() as Avatar;
        var netpoint = avatar.CurrentNetPoint();
        var heroes = new MyList<Avatar>();
        foreach (var objname in netpoint.GetObjects())
        {
            var obj = tl.GetObject(objname);
            if (obj is Avatar)
            {
                var hero = obj as Avatar;
                if (hero.IsHero())
                {
                    heroes.Add(hero);
                }
            }
        }
        return heroes;
    }

    public override void Execute(long timeline_step, long local_step, ITimeline timeline)
    {
        // bool prevent = WorldReaction(timeline_step, local_step, timeline);
        // if (prevent)
        // 	return;

        CommandReaction(timeline_step, local_step, timeline);
    }
}
