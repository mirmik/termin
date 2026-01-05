using System.Collections;
using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif

public class AvatarView : ObjectController
{
    public GameObject StartLocation = null;
    HeroCameraRegistrator heroCameraRegistrator;

    void Awake()
    {
        // find in children
        heroCameraRegistrator = GetComponentInChildren<HeroCameraRegistrator>();
    }

    public void UpdateFieldOfView()
    {
        if (heroCameraRegistrator == null)
        {
            return;
        }

        var ava = avatar();
        var location = ava.LocationObject();

        //Debug.Log("UpdateFieldOfView: " + location.Name() + " " + location.HasEyes() + " " + heroCameraRegistrator.IsEnabled());
        if (location.IsHero())
        {
            if (heroCameraRegistrator.IsEnabled())
                heroCameraRegistrator.Disable();
            return;
        }

        if (ava.HasOculars() && heroCameraRegistrator.IsEnabled() == false)
        {
            heroCameraRegistrator.ShowSight();
            UpdateCameraPosition();
            return;
        }

        if (!ava.HasOculars() && heroCameraRegistrator.IsEnabled() == true)
        {
            heroCameraRegistrator.Disable();
            return;
        }
    }

    void UpdateCameraPosition()
    {
        var ava = avatar();
        var location = ava.LocationObject();
        var camera = heroCameraRegistrator.GetComponent<Camera>();
        var location_camera_pose = location.CameraPose();
        camera.transform.position = location_camera_pose.position;
        camera.transform.rotation = location_camera_pose.rotation;
    }

    Avatar avatar()
    {
        return GetObject() as Avatar;
    }

    public override void InitObjectController(ITimeline timeline)
    {
        CreateObject<Avatar>(name, timeline);
        var avatar = GetObject() as Avatar;
        avatar.MarkAsHero();
    }

    public override void InitSecondPhase()
    {
        if (StartLocation != null)
        {
            var avatar = GetObject() as Avatar;
            avatar.SetLocation(new ObjectId(StartLocation.name));
        }
    }

    public override void UpdateView()
    {
        var guard = GetObject();
        if (avatar().Location == default(ObjectId))
        {
            Debug.Log("AvatarView: Update: Location is null");
            return;
        }

        var avatar_pose = avatar().GlobalPose();
        var location = avatar().Location;
        var location_object = avatar().LocationObject();
        this.transform.position = avatar_pose.position;
        this.transform.rotation = avatar_pose.rotation;

        UpdateHideOrMaterial(guard, force_hide: location_object.IsHero());

        UpdateFieldOfView();
        UpdateTempreature(guard);
    }

    public bool LeftClickOnAnotherActor(GameObject another_actor, Vector3 pos)
    {
        var obj = another_actor.GetComponent<ObjectController>().GetObject();

        if (obj == GetObject())
        {
            return false;
        }

        if (obj.IsHero())
        {
            return false;
        }

        avatar().MoveCommand(new ObjectId(another_actor.name));

        return true;
    }

    public void OnEnvironmentClick(Vector3 pos, GameObject hit)
    {
        var avater = avatar();
        var controlled = avater.DirrectControlled;

        if (controlled != default(ObjectId))
        {
            avater.MoveControlled(pos);
        }
        else
        {
            var timeline = avater.GetTimeline() as Timeline;
            timeline.FindNearestObject(
                pos,
                2.0f,
                (obj) =>
                {
                    if (obj.IsHero())
                    {
                        return;
                    }
                    avater.MoveCommand(new ObjectId(obj.Name()));
                    return;
                }
            );
        }
    }
}
