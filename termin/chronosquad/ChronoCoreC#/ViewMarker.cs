using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class ViewMarker : MonoBehaviour
{
    ObjectOfTimeline _attached_to;
    static ViewMarker _instance;
    GameObject Model;
    GameObject ModelBase;

    public static ViewMarker Instance
    {
        get { return _instance; }
    }

    ChronosphereController chronosphereController;
    ChronoSphere chronoSphere;
    FOVTesterController fOVTesterController;

    bool eenabled = false;

    TimelineController CurrentTimelineController
    {
        get { return chronosphereController.CurrentTimelineController(); }
    }

    Timeline CurrentTimeline
    {
        get { return CurrentTimelineController.GetTimeline(); }
    }

    void Start()
    {
        Model = transform.Find("StellarEye").gameObject;
        ModelBase = transform.Find("StellarEyeBase").gameObject;
        _instance = this;
        chronosphereController = FindFirstObjectByType<ChronosphereController>();
        chronoSphere = chronosphereController.GetChronosphere();
        fOVTesterController = FindFirstObjectByType<FOVTesterController>();
        Model.SetActive(false);
        ModelBase.SetActive(false);
    }

    public bool IsPositionMode()
    {
        return _attached_to == null;
    }

    void UpdatePositionMode()
    {
        var enemies = CurrentTimeline.Enemies();
        var position = transform.position;

        var direction_to_camera = Camera.main.transform.position - position;
        var camera_direction = Camera.main.transform.forward;

        Model.transform.rotation = Quaternion.LookRotation(-camera_direction);

        GameObject last = null;
        foreach (var enemy in enemies)
        {
            if (enemy.IsDead || enemy.IsPreDead)
                continue;

            if (!(enemy is Actor))
                continue;

            var objctr = CurrentTimelineController.GetObject(enemy);
            var canSee = Raycaster.IsCanSee2(enemy, position);

            if (canSee)
            {
                last = objctr.gameObject;
                objctr.SetViewMarkerLine(objctr.CameraPosition(), position + Vector3.up * 0.5f);
            }
            else
            {
                objctr.HideViewMarkerLine();
            }
        }

        // if (last != null && fOVTesterController != null)
        // 	fOVTesterController.ProgramAttachTo(
        // 		last);
    }

    void UpdateAttachedMode()
    {
        var enemies = CurrentTimeline.Enemies();
        var position = transform.position;

        var direction_to_camera = Camera.main.transform.position - position;
        var camera_direction = Camera.main.transform.forward;

        Model.transform.rotation = Quaternion.LookRotation(-camera_direction);

        GameObject last = null;
        foreach (var enemy in enemies)
        {
            if (enemy.IsDead || enemy.IsPreDead)
                continue;

            if (!(enemy is Actor))
                continue;

            var objctr = CurrentTimelineController.GetObject(enemy);
            if (enemy == _attached_to)
            {
                continue;
            }

            var target_actor = _attached_to;
            var timeline = CurrentTimelineController.GetTimeline();
            var canSee = timeline.present.GetCanSee(enemy, target_actor);

            if (canSee == CanSee.See)
            {
                last = objctr.gameObject;
                objctr.SetViewMarkerLine(objctr.CameraPosition(), position + Vector3.up * 0.5f);
            }
            else
            {
                objctr.HideViewMarkerLine();
            }
        }

        // if (last != null && fOVTesterController != null)
        // 	fOVTesterController.ProgramAttachTo(
        // 		last);
    }

    void Update()
    {
        if (!eenabled)
            return;

        if (IsPositionMode())
            UpdatePositionMode();
        else
            UpdateAttachedMode();
    }

    public void Attach(GameObject obj)
    {
        transform.parent = obj.transform;
        transform.localPosition = Vector3.zero + Vector3.up * 2.0f;
        ModelBase.SetActive(false);
        Model.SetActive(true);
        _attached_to = obj.GetComponent<ObjectController>().GetObject();
        eenabled = true;
    }

    public void Attach(Vector3 position)
    {
        transform.parent = null;
        transform.position = position + Vector3.up * 0.5f;
        ModelBase.SetActive(true);
        Model.SetActive(true);
        _attached_to = null;
        eenabled = true;
    }

    public void Dettach()
    {
        transform.parent = null;
        ModelBase.SetActive(false);
        Model.SetActive(false);
        _attached_to = null;
        eenabled = false;
    }
}
