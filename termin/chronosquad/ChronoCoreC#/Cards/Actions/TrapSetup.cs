using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class TrapSetupAction : TargetChooseAction
{
    TrapSetupAction() : base(KeyCode.F) { }

    protected override Ability MakeAbility()
    {
        var ability = new TrapSetupAbility(0.0f);
        return ability;
    }

    public override string TooltipText()
    {
        return "Подманить";
    }

    protected override void ActionToEnvironment(ReferencedPoint target)
    {
        _actor.GetObject().AbilityUseOnEnvironment<TrapSetupAbility>(target);
    }
}
