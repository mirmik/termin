using System;

public class CameraObject : PhysicalObject
{
    public override ObjectOfTimeline Copy(ITimeline newtimeline)
    {
        CameraObject camera = new CameraObject();
        camera.CopyFrom(this, newtimeline);
        return camera;
    }

    public override void CopyFrom(ObjectOfTimeline other, ITimeline newtimeline)
    {
        var camera = other as CameraObject;
        base.CopyFrom(camera, newtimeline);
    }

    public override bool IsMovable()
    {
        return false;
    }
}
