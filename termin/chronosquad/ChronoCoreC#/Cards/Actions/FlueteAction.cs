using System.Collections;
using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif

public class FlueteAction : TargetChooseAction
{
    public float Radius = 10.0f;

    FlueteAction() : base(KeyCode.V) { }

    protected override Ability MakeAbility()
    {
        var ability = new FlueteAbility(Radius);
        return ability;
    }

    public override string TooltipText()
    {
        return "Подманить";
    }

    protected override void ActionToEnvironment(ReferencedPoint target)
    {
        _actor.GetObject().AbilityUseOnEnvironment<FlueteAbility>(target);
    }

    public override void OnActorClick(GameObject actor, ClickInformation click)
    {
        OnEnvironmentClick(click);
        return;
    }

    protected override void DrawEffects(Vector3 position)
    {
        ProgramBlueCammeraEffect(true, position, Radius);
    }
}
