using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using System;

public class ReverseInTimeAction : OneAbilityAction
{
    public Material BlinkEffectMaterial;

    public ReverseInTimeAction() : base(KeyCode.R) { }

    public override string TooltipText()
    {
        return "Реверсия времени";
    }

    override protected Ability MakeAbility()
    {
        var reverse_ability = new ReverseAbility();
        return reverse_ability;
    }

    public override void OnIconClick()
    {
        var guard = _actor.GetObject();
        var timeline = guard.GetTimeline();
        var ability_list_panel = guard.AbilityListPanel();
        guard.GetAbility<ReverseAbility>().UseSelf(timeline, ability_list_panel);
    }
}
