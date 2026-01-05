using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using System;

public class BlinkAction : OneAbilityAction
{
    public Material LineMaterial;
    public Material BlinkEffectMaterial;
    public float BlinkTimeLapse = 0.5f;

    public override string TooltipText()
    {
        return "Мгновенно переместиться в указанную точку";
    }

    public BlinkAction() : base(KeyCode.B) { }

    protected override Ability MakeAbility()
    {
        return new BlinkAbility(BlinkTimeLapse);
    }

    public override void OnIconClick()
    {
        _gun_clicked = true;
        _line_renderer.enabled = true;
        UsedActionBuffer.Instance.SetUsedAction(this);
    }

    public override void Cancel()
    {
        UsedActionBuffer.Instance.SetUsedAction(null);
        _gun_clicked = false;
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

            RaycastHit hit = GameCore.CursorEnvironmentHit(mouse_pos);
            if (hit.collider != null)
            {
                Vector3 world_pos = hit.point;
                _line_renderer.SetPosition(1, world_pos);
            }
            else
            {
                _line_renderer.SetPosition(1, this.transform.position + new Vector3(0, 0, 10));
            }
        }

        // get current animatronic state
        //var state = _guard.CurrentAnimatronic();

        // skirt.GetComponent<Renderer>().material.Lerp(
        // 	BlinkSkirtMaterial1,
        // 	BlinkSkirtMaterial2,
        // 	0.5f
        // );
    }

    public override void OnEnvironmentClick(ClickInformation click)
    {
        var obj = click.environment_hit.collider.gameObject;
        var pos = click.environment_hit.point;

        var rpos = ReferencedPoint.FromGlobalPosition(
            pos,
            GameCore.FrameNameForObject(obj),
            _actor.GetObject().GetTimeline()
        );
        _actor.GetObject().AbilityUseOnEnvironment<BlinkAbility>(rpos);
        Cancel();
    }

    public override void OnActorClick(GameObject actor, ClickInformation click)
    {
        if (actor == this.gameObject)
        {
            Cancel();
            return;
        }

        Cancel();
        return;
    }
}
