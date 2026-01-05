#if UNITY_64
using UnityEngine;
#endif

using System;
using System.Collections.Generic;

public class CreateGuardAction : NonObjectAction
{
    public GameObject GuardPrefab;
    public GameObject cursor;

    public override void Init()
    {
        ManualAwake();
    }

    // protected override void ManualAwake()
    // {
    // }

    public override string TooltipText()
    {
        return "Создать стража";
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
        cursor = Instantiate(GuardPrefab);

        RecurseChangeLayer(cursor.transform, (int)Layers.EFFECTS_LAYER);
    }

    public override void OnEnvironmentClick(ClickInformation click)
    {
        var instance = Instantiate(GuardPrefab, click.environment_hit.point, Quaternion.identity);
        var unical_name = GameCore.MakeUnicalName("Guard_");
        instance.name = unical_name;

        var current_timeline_controller = ChronosphereController.instance.GetCurrentTimeline();
        instance.transform.parent = current_timeline_controller.transform;

        current_timeline_controller.InitCreatedObjectController(
            instance.GetComponent<ObjectController>()
        );

        Cancel();
    }

    public override void OnActorClick(GameObject actor, ClickInformation click)
    {
        Debug.Log("CreateGuardAction: OnActorClick");
    }
}
