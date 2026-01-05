using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using System;

public class RecombinateTargetInTimeAction : TargetChooseAction
{
    RecombinateTargetAbility _reverse_ability;

    public RecombinateTargetInTimeAction() : base(KeyCode.N) { }

    public override string TooltipText()
    {
        return "Темпоральная рекомбинация";
    }

    protected override Ability MakeAbility()
    {
        _reverse_ability = new RecombinateTargetAbility();
        return _reverse_ability;
    }

    protected override void ActionTo(GameObject other)
    {
        var objctr = other.GetComponent<ObjectController>();
        var tl = objctr.GetObject().GetTimeline();
        _actor.GetObject().AbilityUseOnObject<RecombinateTargetAbility>(objctr.GetObject());
    }

    public override bool CanUseOnObject(GameObject other)
    {
        var objctr = other.GetComponent<ObjectController>();
        var tl = objctr.GetObject().GetTimeline();
        return _actor.GetObject().CanUseAbility<RecombinateTargetAbility>(objctr.GetObject());
    }
}
