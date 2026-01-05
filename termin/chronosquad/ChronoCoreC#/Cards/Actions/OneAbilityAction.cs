using UnityEngine;
using System;
using System.Collections;

public abstract class OneAbilityAction : MonoBehaviourAction
{
    Type ability_type;
    protected bool _gun_clicked = false;
    KeyCode keycode;

    public OneAbilityAction(KeyCode keycode)
    {
        this.keycode = keycode;
    }

    private void SetAbility(Ability ability)
    {
        ability_type = ability.GetType();
    }

    public Ability GetAbility()
    {
        if (ability_type == null)
            Debug.LogError("Ability type is not set: " + this);
        var obj = _actor.GetObject();
        return obj.AbilityList.GetAbility(ability_type);
    }

    public sealed override float CooldownTime()
    {
        if (ability_type == null)
            Debug.LogError("Ability type is not set: " + this);
        return GetAbility().CooldownTime();
    }

    public sealed override float GetFillPercent()
    {
        if (ability_type == null)
            Debug.LogError("Ability type is not set: " + this);
        var ability = GetAbility();
        return _actor.GetObject().GetAbilityCooldownPercent(ability);
    }

    public override void Init()
    {
        _actor = this.GetComponent<ObjectController>();
        var activity = new Activity(icon, this, keycode);
        _actor.add_activity(activity);

        setup_line_renderer();

        var ability = MakeAbility();
        _actor.GetObject().AddAbility(ability);
        SetAbility(ability);

        base.Init();
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
        ClearEffects();
    }

    public override void OnEnvironmentClick(ClickInformation click)
    {
        throw new NotImplementedException();
    }

    public override void OnActorClick(GameObject actor, ClickInformation click)
    {
        throw new NotImplementedException();
    }

    abstract protected Ability MakeAbility();
}
