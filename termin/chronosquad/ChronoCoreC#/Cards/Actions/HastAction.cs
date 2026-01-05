using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using System;

public class HastAction : OneAbilityAction
{
    public override string TooltipText()
    {
        return "Ускорение";
    }

    public HastAction() : base(KeyCode.J) { }

    protected override Ability MakeAbility()
    {
        var hast_ability = new HastAbility();
        return hast_ability;
    }

    public override void OnIconClick()
    {
        _actor.guard().AbilityUseSelf<HastAbility>();
    }

    public override void Cancel() { }

    public override void OnEnvironmentClick(ClickInformation click)
    {
        Cancel();
    }

    public override void OnActorClick(GameObject actor, ClickInformation click)
    {
        throw new NotImplementedException();
    }
}
