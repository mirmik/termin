using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class TimeMoveOnDeath : MonoBehaviour
{
    GuardView _guard_view;

    void Start()
    {
        _guard_view = this.GetComponent<GuardView>();
        var guard = _guard_view.guard();
        AddAbility();
    }

    void AddAbility()
    {
        var activity = new PastStepOnDeath((long)(Utility.GAME_GLOBAL_FREQUENCY * 3.0f));
        _guard_view.guard().AddAbility(activity);
    }
}
