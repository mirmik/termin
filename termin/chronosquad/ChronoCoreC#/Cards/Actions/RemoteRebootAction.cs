using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class RemoteRebootAction : GunAction
{
    protected override Ability MakeAbility()
    {
        var shoot_ability = new RemoteRebootAbility(ShootDistance);
        return shoot_ability;
    }
}
