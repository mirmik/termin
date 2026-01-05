using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using System;

public class ToogleDoorAction : MonoBehaviourAction
{
    public override string TooltipText()
    {
        return "Открыть/закрыть дверь";
    }

    public override void Init()
    {
        _actor = this.GetComponent<ObjectController>();
        //_guard_view = this.GetComponent<GuardView>();
        var activity = new Activity(icon, this, KeyCode.D);
        _actor.add_activity(activity);

        // var drawer = new BlindDrawer(BlinkEffectMaterial);
    }

    public override void OnIconClick()
    {
        var obj = _actor.GetObject();
        var door = obj as AutomaticDoorObject;
        door.ToogleDoor();
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

    public override global::System.Single GetFillPercent()
    {
        return 100.0f;
    }

    public override global::System.Single CooldownTime()
    {
        return 0.0f;
    }
}
