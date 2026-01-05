using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using System;

public class ReturnToMasterAction : OneAbilityAction
{
    public Material BlinkEffectMaterial;
    public GameObject master;

    public ReturnToMasterAction() : base(KeyCode.X) { }

    public override string TooltipText()
    {
        return "Вернуться к хозяину";
    }

    protected override Ability MakeAbility()
    {
        var objid = new ObjectId(master.name);
        var ability = new ReturnToMasterAbility(objid);
        return ability;
    }

    public override void OnIconClick()
    {
        var guard = _actor.guard();
        var timeline = guard.GetTimeline();
        var ability_list_panel = guard.AbilityListPanel();
        guard.GetAbility<ReturnToMasterAbility>().UseSelf(timeline, ability_list_panel);
    }
}
