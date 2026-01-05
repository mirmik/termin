using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class PastStepOnDeathAction : OneAbilityAction
{
    public PastStepOnDeathAction() : base(KeyCode.N) { }

    public override string TooltipText()
    {
        return "Шаг в прошлое";
    }

    protected override Ability MakeAbility()
    {
        var ability = new PastStepOnDeath((long)(3.0f * Utility.GAME_GLOBAL_FREQUENCY));
        return ability;
    }

    public override void OnIconClick()
    {
        _actor.GetObject().AbilityUseSelf<StepToPastAbility>();
    }

    public override void Cancel() { }

    public override void OnEnvironmentClick(ClickInformation click)
    {
        Cancel();
    }
}
