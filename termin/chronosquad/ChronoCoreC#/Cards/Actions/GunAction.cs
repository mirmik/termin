using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class GunAction : OneAbilityAction
{
    public float ShootDistance = 15.0f;
    public Material material;
    public bool can_shoot_from_croach = false;

    protected KeyCode HotKey = KeyCode.F;
    public Material ShootMaterial;

    public bool IgnoreObstacles = false;

    public GunAction() : base(KeyCode.F) { }

    protected override Ability MakeAbility()
    {
        if (IgnoreObstacles == false)
        {
            var shoot_ability = new ShootAbility(
                ShootDistance,
                can_shoot_from_croach: can_shoot_from_croach
            );
            return shoot_ability;
        }
        else
        {
            var shoot_ability = new ShootAbilityOverWalls(
                ShootDistance,
                can_shoot_from_croach: can_shoot_from_croach
            );
            return shoot_ability;
        }
    }

    void ProgramZoneCammeraEffect(bool enable, Vector3 center)
    {
        _main_camera_shader_filter.ProgramZoneCammeraEffect(enable, ShootDistance, center);
    }

    public override string TooltipText()
    {
        return "Выстрелить в противника или объект";
    }

    public override void UpdateActive()
    {
        if (_gun_clicked)
        {
            _line_renderer.startWidth = LineWidth;
            _line_renderer.endWidth = LineWidth;
            _line_renderer.SetPosition(0, this.transform.position + new Vector3(0, 1, 0));

            Vector3 mouse_pos = Input.mousePosition;
            ClickInformation clickInformation = GameCore.CursorHit(mouse_pos);
            var envpoint = clickInformation.environment_hit;

            if (clickInformation.actor_hit.collider != null)
            {
                var collider = clickInformation.actor_hit.collider;
                var objctr = GameCore.FindObjectControllerInParentTree(collider.gameObject);
                if (objctr != null)
                {
                    Vector3 world_pos = objctr.GetTorsoGlobalPosition();
                    _line_renderer.SetPosition(1, world_pos);
                }
            }
            else
            {
                if (envpoint.collider != null)
                {
                    _line_renderer.SetPosition(1, envpoint.point);
                }
                else
                {
                    _line_renderer.SetPosition(1, this.transform.position + new Vector3(0, 0, 10));
                }
            }

            ProgramZoneCammeraEffect(true, this.transform.position);
        }
    }

    public override void OnEnvironmentClick(ClickInformation click)
    {
        Cancel();
    }

    public override void OnActorClick(GameObject actor, ClickInformation click)
    {
        if (actor == this.gameObject)
        {
            Cancel();
            return;
        }

        Ability sability = GetAbility();
        var obj = actor.GetComponent<ObjectController>().GetObject();
        sability.UseOnObject(
            obj,
            _actor.GetObject().GetTimeline(),
            _actor.GetObject().AbilityListPanel()
        );

        Cancel();
        return;
    }
}
