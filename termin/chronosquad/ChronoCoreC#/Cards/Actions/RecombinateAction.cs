using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using System;

public class RecombinateInTimeAction : OneAbilityAction
{
    public Material BlinkEffectMaterial;

    RecombinateAbility _reverse_ability;

    public RecombinateInTimeAction() : base(KeyCode.N) { }

    public override string TooltipText()
    {
        return "Темпоральная рекомбинация";
    }

    protected override Ability MakeAbility()
    {
        _reverse_ability = new RecombinateAbility();
        return _reverse_ability;
    }

    public override void OnIconClick()
    {
        var guard = _actor.guard();
        var timeline = guard.GetTimeline();
        var ability_list_panel = guard.AbilityListPanel();
        guard.GetAbility<RecombinateAbility>().UseSelf(timeline, ability_list_panel);
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
