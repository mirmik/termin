using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class ParasiteAction : TargetChooseAction
{
    public bool ControlMode = true;

    ParasiteAction() : base(KeyCode.G) { }

    protected override Ability MakeAbility()
    {
        ParasiteMode mode = ControlMode ? ParasiteMode.Control : ParasiteMode.Passanger;
        return new ParasiteAbility(1.0f, mode);
    }

    protected override void ActionTo(GameObject target_actor)
    {
        var _obj = target_actor.GetComponent<ObjectController>();
        var parasite_action = _actor.GetObject().GetAbility<ParasiteAbility>();
        _actor.guard().AbilityUseOnObject<ParasiteAbility>(_obj.GetActor());
    }

    public override string TooltipText()
    {
        return "Паразит";
    }
}
