using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using System;

public class DisguiseAction : OneAbilityAction
{
    bool _is_disguise_view_enabled = false;

    public float TimeOffset { get; set; }

    Material material;
    public Material disguise_material;
    Renderer render;

    //Color color;
    //Color alpha_color;

    GameObject model;
    GameObject cube;

    public DisguiseAction() : base(keycode: KeyCode.D) { }

    void Awake()
    {
        _actor = this.GetComponent<ObjectController>();
        model = _actor.transform.Find("Model").gameObject;
        cube = model.transform.Find("Cube").gameObject;
        material = cube.GetComponent<Renderer>().material;
        render = cube.GetComponent<Renderer>();
    }

    protected override Ability MakeAbility()
    {
        return new DisguiseAbility(TimeOffset);
    }

    public override string TooltipText()
    {
        return "Маскировка";
    }

    public override void OnIconClick()
    {
        var _guard = _actor.GetActor();
        if (_guard.IsDisguise())
            return;

        if (_guard.IsDead)
            return;

        _guard.AbilityUseSelf<DisguiseAbility>();
    }

    public override void Cancel() { }

    void SetDisguiseMaterial()
    {
        render.material = (disguise_material);
    }

    void SetCommonMaterial()
    {
        render.material = (material);
    }

    void Update()
    {
        var obj = _actor.GetActor();
        if (obj.IsDisguise() && !_is_disguise_view_enabled)
        {
            SetDisguiseMaterial();
            _is_disguise_view_enabled = true;
        }
        else if (!obj.IsDisguise() && _is_disguise_view_enabled)
        {
            SetCommonMaterial();
            _is_disguise_view_enabled = false;
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
        }
        Cancel();
    }
}
