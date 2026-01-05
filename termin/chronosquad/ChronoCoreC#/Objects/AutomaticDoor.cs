using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif

public class AutomaticDoorObject : PhysicalObject
{
    float _current_phase;
    float open_close_time = 1.0f;

    public AutomaticDoorObject()
    {
        DisableBehaviour();
    }

    public override ObjectOfTimeline Copy(ITimeline newtimeline)
    {
        AutomaticDoorObject obj = new AutomaticDoorObject();
        obj.CopyFrom(this, newtimeline);
        return obj;
    }

    public override void CopyFrom(ObjectOfTimeline obj, ITimeline newtimeline)
    {
        base.CopyFrom(obj, newtimeline);
        AutomaticDoorObject door = obj as AutomaticDoorObject;
        _current_phase = door._current_phase;
        open_close_time = door.open_close_time;
    }

    public void SetPhase(float phase)
    {
        _current_phase = phase;
    }

    public float Phase()
    {
        return _current_phase;
    }

    public void StartOpenAnimatronic()
    {
        var local_step = LocalStep();
        var dist = 1.0f - _current_phase;
        var time = dist / open_close_time;

        var anim = new AutomaticDoorPhaseAnimatronic(
            start_phase: _current_phase,
            finish_phase: 1.0f,
            referencedPose: CurrentReferencedPose(),
            start_step: local_step,
            finish_step: (long)(local_step + Utility.GAME_GLOBAL_FREQUENCY * time)
        );
        SetNextAnimatronic(anim);
    }

    public void StartCloseAnimatronic()
    {
        var local_step = LocalStep();
        var time = _current_phase / open_close_time;

        var anim = new AutomaticDoorPhaseAnimatronic(
            start_phase: _current_phase,
            finish_phase: 0.0f,
            referencedPose: CurrentReferencedPose(),
            start_step: local_step,
            finish_step: (long)(local_step + Utility.GAME_GLOBAL_FREQUENCY * time)
        );
        SetNextAnimatronic(anim);
    }

    public void StartSinusAnimatronic()
    {
        var local_step = LocalStep();
        var anim = new SinusAutomaticDoorPhaseAnimatronic(
            referencedPose: CurrentReferencedPose(),
            start_step: local_step,
            finish_step: local_step + 100
        );
        SetNextAnimatronic(anim);
    }

    public void ToogleDoor()
    {
        if (_current_phase == 0.0f)
            StartOpenAnimatronic();
        else
            StartCloseAnimatronic();
    }
}
