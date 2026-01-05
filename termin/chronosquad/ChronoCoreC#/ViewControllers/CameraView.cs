using System.Collections;
using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif

#if UNITY_64
[RequireComponent(typeof(NetPointView))]
#endif
public class CameraView : ObjectController
{
    CameraObject Camera()
    {
        return GetObject() as CameraObject;
    }

    public override void InitObjectController(ITimeline timeline)
    {
        GetComponent<ObjectController>().CreateObject<CameraObject>(name, timeline);
        var avatar = GetComponent<ObjectController>().GetObject() as CameraObject;
        avatar.SetSightDistance(base.GetSightDistance());
        avatar.SetHasCamera(true);
        FindSubobjectsTransforms();
        //avatar.SetBodyPartsPose(this);
    }

    void Start() { }

    // Update is called once per frame
    public override void UpdateView()
    {
        var camera = Camera();
        var pose = camera.GlobalPose();
        this.transform.position = pose.position;
        this.transform.rotation = pose.rotation;
        UpdateHideOrMaterial(camera);
        UpdateDistruct();
        UpdateTempreature(camera);
        UpdateStunEffect(camera);
    }
}
