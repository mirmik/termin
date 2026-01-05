using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class ControlRobotAction : OneAbilityAction
{
    public ControlRobotAction() : base(KeyCode.R) { }

    public override string TooltipText()
    {
        return "Захватить управление роботом";
    }

    protected override Ability MakeAbility()
    {
        var ability = new ControlRobotAbility();
        return ability;
    }

    public override void OnIconClick()
    {
        Debug.Log("OnIconClick");
        _actor.GetObject().AbilityUseSelf<ControlRobotAbility>();
    }

    public override void Cancel() { }

    public override void OnEnvironmentClick(ClickInformation click)
    {
        Cancel();
    }

    // public override void OnActorClick(GameObject actor, ClickInformation click)
    // {
    // }
}
