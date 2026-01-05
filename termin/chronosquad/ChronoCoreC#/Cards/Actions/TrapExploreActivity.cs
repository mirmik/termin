using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using System;

public class TrapExploreAction : OneAbilityAction
{
    public Material BlinkEffectMaterial;

    public TrapExploreAction() : base(KeyCode.F) { }

    public override string TooltipText()
    {
        return "Взрыв вокруг персонажа";
    }

    override protected Ability MakeAbility()
    {
        var trap_explore_ability = new TrapExploreAbility();
        return trap_explore_ability;
    }

    public override void OnIconClick()
    {
        var guard = _actor.GetObject();
        guard.AbilityUseSelf<TrapExploreAbility>();
    }

    public override void OnActorClick(GameObject actor, ClickInformation click)
    {
        throw new NotImplementedException();
    }

    public override void Cancel() { }

    public override void OnEnvironmentClick(ClickInformation click)
    {
        Cancel();
    }
}
