using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif
public class TrapComponent : ItemComponent
{
    float Radius = 2.0f;

    public TrapComponent(ObjectOfTimeline owner) : base(owner) { }

    public override void Start() { }

    public override ItemComponent Copy(ObjectOfTimeline owner)
    {
        return new TrapComponent(owner);
    }

    public override void Execute(long timeline_step, long local_step)
    {
        var timeline = Owner.GetTimeline();
        var enemies = timeline.Enemies();

        foreach (var enemy in enemies)
        {
            if (enemy.IsDead || enemy.IsPreDead || !enemy.IsMaterial())
            {
                continue;
            }

            float Distance = Vector3.Distance(Owner.Position(), enemy.Position());

            if (Distance < Radius)
            {
                if (Owner.CanUseAbility<ShootAbility>(Owner))
                {
                    Owner.AbilityUseOnObject<ShootAbility>(enemy);
                }
            }
        }
    }
}
