using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class SwapHostAction : TargetChooseAction
{
    public SwapHostAction() : base(KeyCode.X) { }

    protected override Ability MakeAbility()
    {
        //string avatar_name = Avatar?.name;
        var ability = new SwapHostAbility(parasiteMode: ParasiteMode.Passanger);
        return ability;
    }

    public override string TooltipText()
    {
        return "Сменить хозяина";
    }

    protected override void ActionTo(GameObject other)
    {
        var objctr = other.GetComponent<ObjectController>();
        var tl = objctr.GetObject().GetTimeline();
        _actor.GetObject().AbilityUseOnObject<SwapHostAbility>(objctr.GetObject());
    }

    public override bool CanUseOnObject(GameObject other)
    {
        var objctr = other.GetComponent<ObjectController>();
        var tl = objctr.GetObject().GetTimeline();
        return _actor.GetObject().CanUseAbility<SwapHostAbility>(objctr.GetObject());
    }
}
