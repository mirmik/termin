using System.Collections;
using System.Collections.Generic;
using UnityEngine;

abstract public class TargetChooseAction : OneAbilityAction
{
    public Material material;

    //public Texture2D _icon;


    public TargetChooseAction(KeyCode keycode) : base(keycode) { }

    protected virtual void ActionTo(GameObject actor) { }

    protected virtual void ActionToEnvironment(ReferencedPoint target) { }

    protected virtual void DrawEffects(Vector3 position) { }

    public override void UpdateActive()
    {
        if (_gun_clicked)
        {
            _line_renderer.startWidth = LineWidth;
            _line_renderer.endWidth = LineWidth;
            _line_renderer.SetPosition(0, this.transform.position);

            Vector3 mouse_pos = Input.mousePosition;

            ClickInformation clickInformation = GameCore.CursorHit(mouse_pos);
            var hit = clickInformation.environment_hit;

            if (clickInformation.actor_hit.collider != null)
            {
                var collider = clickInformation.actor_hit.collider;
                var objctr = GameCore.FindObjectControllerInParentTree(collider.gameObject);
                if (objctr != null)
                {
                    Vector3 world_pos = objctr.GetTorsoGlobalPosition();
                    _line_renderer.SetPosition(1, world_pos);
                    DrawEffects(world_pos);
                }
            }
            else
            {
                if (hit.collider != null)
                {
                    Vector3 world_pos = hit.point;
                    _line_renderer.SetPosition(1, world_pos);
                    DrawEffects(world_pos);
                }
                else
                {
                    _line_renderer.SetPosition(1, this.transform.position + new Vector3(0, 0, 10));
                }
            }
        }
    }

    override public void OnEnvironmentClick(ClickInformation click)
    {
        var point = GameCore.Vector3ToReferencedPoint(click.environment_hit.point);
        ActionToEnvironment(point);
        Cancel();
    }

    override public void OnActorClick(GameObject actor, ClickInformation click)
    {
        if (actor == this.gameObject)
        {
            Cancel();
            return;
        }

        ActionTo(actor);
        Cancel();
    }
}
