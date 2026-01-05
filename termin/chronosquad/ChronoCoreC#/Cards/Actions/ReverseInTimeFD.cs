using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using System;

public class ReverseInTimeActionFD : OneAbilityAction
{
    public Material BlinkEffectMaterial;

    public ReverseInTimeActionFD() : base(KeyCode.R) { }

    public override string TooltipText()
    {
        return "Реверсия времени";
    }

    override protected Ability MakeAbility()
    {
        var reverse_ability = new ReverseFourDAbility();
        return reverse_ability;
    }

    public override void OnIconClick()
    {
        var guard = _actor.GetObject();
        var timeline = guard.GetTimeline();
        var ability_list_panel = guard.AbilityListPanel();
        guard.GetAbility<ReverseFourDAbility>().UseSelf(timeline, ability_list_panel);
    }
}
