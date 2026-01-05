using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class HackAction : TargetChooseAction
{
    public GameObject Avatar;

    HackAction() : base(KeyCode.X) { }

    protected override Ability MakeAbility()
    {
        string avatar_name = Avatar?.name;
        var ability = new HackAbility(range: 2.0f, avatar_name: avatar_name);
        return ability;
    }

    public override string TooltipText()
    {
        return "Взломать";
    }

    protected override void ActionTo(GameObject other)
    {
        var objctr = other.GetComponent<ObjectController>();
        var tl = objctr.GetObject().GetTimeline();
        _actor.GetObject().AbilityUseOnObject<HackAbility>(objctr.GetObject());
    }

    public override bool CanUseOnObject(GameObject other)
    {
        var objctr = other.GetComponent<ObjectController>();
        var tl = objctr.GetObject().GetTimeline();
        return _actor.GetObject().CanUseAbility<HackAbility>(objctr.GetObject());
    }
}
