using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class GoldSkullAction : ParabolicAction
{
    public float DurationOfAttention = 3.0f;
    public float Radius = 10.0f;

    GameObject Skull;

    public GoldSkullAction() : base(keycode: KeyCode.X) { }

    public override string TooltipText()
    {
        return "Бросить приманку";
    }

    protected override Ability MakeAbility()
    {
        Skull = GameObject.Find("GoldSkull");
        Skull.transform.position = new Vector3(0, -100, 0);

        var skull_name = Skull.name;
        return new GoldSkullAbility(radius: Radius, name: skull_name);
    }

    protected override void ProgramEffectExtension(bool enable, Vector3 center) { }
}
