using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using System;

public class ZeroJumpAction : OneAbilityAction
{
    public Material LineMaterial;
    public float MaxDistance = 10.0f;
    public float FleetSpeed = 5.0f;

    public ZeroJumpAction() : base(KeyCode.V) { }

    public override string TooltipText()
    {
        return "Прыгнуть в указанную точку";
    }

    protected override Ability MakeAbility()
    {
        return new ZeroJumpAbility(MaxDistance, FleetSpeed);
    }

    public override void Cancel()
    {
        UsedActionBuffer.Instance.SetUsedAction(null);
        _line_renderer.enabled = false;
    }

    public override void UpdateActive()
    {
        if (_gun_clicked)
        {
            _line_renderer.startWidth = LineWidth;
            _line_renderer.endWidth = LineWidth;
            _line_renderer.SetPosition(0, this.transform.position + new Vector3(0, 1, 0));

            Vector3 mouse_pos = Input.mousePosition;

            RaycastHit hit;
            Ray ray = Camera.main.ScreenPointToRay(mouse_pos);
            if (Physics.Raycast(ray, out hit))
            {
                Vector3 world_pos = hit.point;
                _line_renderer.SetPosition(1, world_pos);
            }
            else
            {
                _line_renderer.SetPosition(1, this.transform.position + new Vector3(0, 0, 10));
            }
        }
    }

    // Vector3 TargetDirection(Actor guard, Vector3 target_position)
    // {
    // 	var simple_direction = target_position - guard.position();
    // 	var closest = GameCore.GetClosestActor(target_position, new MyList<ObjectOfTimeline>() { guard });
    // 	var distance = Vector3.Distance(target_position, closest.position());
    // 	if (distance < 10)
    // 	{
    // 		var direction = closest.position() - target_position;
    // 		direction.y = 0;
    // 		direction.Normalize();
    // 		return direction;
    // 	}
    // 	else
    // 	{
    // 		simple_direction.y = 0;
    // 		simple_direction.Normalize();
    // 		return simple_direction;
    // 	}
    // }

    public override void OnEnvironmentClick(ClickInformation click)
    {
        var rpos = ReferencedPoint.FromGlobalPosition(
            click.environment_hit.point,
            GameCore.FrameNameForPosition(click.environment_hit.point),
            _actor.GetObject().GetTimeline()
        );
        _actor.GetObject().AbilityUseOnEnvironment<ZeroJumpAbility>(rpos);
        Cancel();
    }

    public override void OnActorClick(GameObject actor, ClickInformation click)
    {
        if (actor == this.gameObject)
        {
            Cancel();
            return;
        }

        var target_objctr = actor.GetComponent<ObjectController>();
        if (target_objctr == null)
        {
            return;
        }

        var obj = target_objctr.GetObject();
        _actor.GetObject().AbilityUseOnObject<ZeroJumpAbility>(obj);

        Cancel();
    }
}
