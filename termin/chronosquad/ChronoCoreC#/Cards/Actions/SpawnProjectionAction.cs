#if UNITY_64
using UnityEngine;
#endif

using System;
using System.Collections.Generic;

public class SpawnProjectionAction : OneAbilityAction
{
    GameObject cursor;

    SpawnProjectionAction() : base(KeyCode.P) { }

    // public override void Init()
    // {
    // 	ManualAwake();
    // }

    protected override Ability MakeAbility()
    {
        var ability = new SpawnProjectionAbility();
        return ability;
    }

    public override string TooltipText()
    {
        return "Создать проекцию";
    }

    public override void Cancel()
    {
        UsedActionBuffer.Instance.SetUsedAction(null);
        Destroy(cursor);
    }

    public override void UpdateActive()
    {
        var mouse_pos = Input.mousePosition;
        var hit = GameCore.CursorEnvironmentHit(mouse_pos);
        cursor.transform.position = hit.point;
    }

    void RecurseChangeLayer(Transform transform, int layer)
    {
        transform.gameObject.layer = layer;
        foreach (Transform child in transform)
        {
            RecurseChangeLayer(child, layer);
        }
    }

    public override void OnIconClick()
    {
        UsedActionBuffer.Instance.SetUsedAction(this);
        cursor = Instantiate(this.gameObject);
        RecurseChangeLayer(cursor.transform, (int)Layers.EFFECTS_LAYER);

        Destroy(cursor.GetComponent<ObjectController>());
        Destroy(cursor.GetComponent<ControlableActor>());
        Destroy(cursor.GetComponent<IconedActor>());
        Destroy(cursor.transform.Find("CameraOfHero").gameObject);
    }

    public override void OnEnvironmentClick(ClickInformation click)
    {
        // var name = gameObject.name;
        // var instance = Instantiate(GuardPrefab, click.environment_hit.point, Quaternion.identity);
        // var unical_name = GameCore.MakeUnicalName(name + "_");
        // instance.name = unical_name;

        // var current_timeline_controller = ChronosphereController.instance.
        // 	GetCurrentTimeline();
        // instance.transform.parent = current_timeline_controller.transform;

        // current_timeline_controller.InitCreatedObjectController(
        // 	instance.GetComponent<ObjectController>());
        var objctr = GetComponent<ObjectController>();
        var guard = objctr.GetObject();

        var ability_list_panel = guard.AbilityListPanel();
        guard.AbilityUseOnEnvironment<SpawnProjectionAbility>(
            GameCore.Vector3ToReferencedPoint(click.environment_hit.point)
        );
        Cancel();
    }

    public override void OnActorClick(GameObject actor, ClickInformation click)
    {
        Debug.Log("CreateGuardAction: OnActorClick");
    }
}
