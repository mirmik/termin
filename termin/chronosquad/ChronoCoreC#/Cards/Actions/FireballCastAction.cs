using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class FireballCastAction : TargetChooseAction
{
    public float ShootDistance = 50.0f;

    FireballCastAction() : base(KeyCode.G) { }

    protected override Ability MakeAbility()
    {
        var ability = new FireballCastAbility(shoot_distance: ShootDistance);
        return ability;
    }

    public override string TooltipText()
    {
        return "Выстрелить фаерболом";
    }

    protected override void ActionTo(GameObject other)
    {
        var objctr = other.GetComponent<ObjectController>();
        var tl = objctr.GetObject().GetTimeline();
        _actor.GetObject().AbilityUseOnObject<FireballCastAbility>(objctr.GetObject());
    }

    public override bool CanUseOnObject(GameObject other)
    {
        var objctr = other.GetComponent<ObjectController>();
        var tl = objctr.GetObject().GetTimeline();
        return _actor.GetObject().CanUseAbility<FireballCastAbility>(objctr.GetObject());
    }

    protected override void ActionToEnvironment(ReferencedPoint target)
    {
        _actor.GetObject().AbilityUseOnEnvironment<FireballCastAbility>(target);
    }

    public override void OnIconClick()
    {
        base.OnIconClick();
    }
}
