using UnityEngine;

public class ExplosionOnDeathAction : OneAbilityAction
{
    public float Radius = 3.0f;
    public float DurationOfAttention = 3.0f;

    MainCameraShaderFilter mainCameraShaderFilter;

    public ExplosionOnDeathAction() : base(KeyCode.N) { }

    public override string TooltipText()
    {
        return "Взрыв при уничтожении";
    }

    protected override Ability MakeAbility()
    {
        var ability = new ExplosionOnDeathAbility(
            Radius,
            new RestlessnessParameters(duration_of_attention: DurationOfAttention, lures: false)
        );
        return ability;
    }

    public override void Init()
    {
        base.Init();

        mainCameraShaderFilter = GameObject.FindFirstObjectByType<MainCameraShaderFilter>();
        var object_controller = GetComponent<ObjectController>();
        object_controller.OnHoverEventHook += OnHover;
    }

    public void OnHover()
    {
        var pos = transform.position;
        mainCameraShaderFilter.ProgramRedCammeraEffect(true, Radius, pos);
    }

    public void OnUnHover() { }
}
