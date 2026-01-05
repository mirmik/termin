using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class EliminateAction : TargetChooseAction
{
    EliminateAction() : base(KeyCode.A) { }

    protected override Ability MakeAbility()
    {
        var ability = new EliminateAbility(1.0f);
        return ability;
    }

    public override string TooltipText()
    {
        return "Атаковать в ближнем бою";
    }

    protected override void ActionTo(GameObject other)
    {
        var objctr = other.GetComponent<ObjectController>();
        var tl = objctr.GetObject().GetTimeline();
        _actor.GetObject().AbilityUseOnObject<EliminateAbility>(objctr.GetObject());
    }

    public override bool CanUseOnObject(GameObject other)
    {
        var objctr = other.GetComponent<ObjectController>();
        var tl = objctr.GetObject().GetTimeline();
        return _actor.GetObject().CanUseAbility<EliminateAbility>(objctr.GetObject());
    }
}
