public class CameraConstractionState
{
    public float TimeConst = 1.0f;

    public virtual bool IsFree()
    {
        return true;
    }

    public virtual Pose CameraConstratePose(long step)
    {
        return new Pose();
    }
}

public class CameraConstractionState_Pose : CameraConstractionState
{
    public Pose pose;

    public CameraConstractionState_Pose(Pose pose)
    {
        this.pose = pose;
    }

    public override bool IsFree()
    {
        return false;
    }

    public override Pose CameraConstratePose(long step)
    {
        return pose;
    }
}

public class CameraConstractionState_PoseLerp : CameraConstractionState
{
    public Pose apose;
    public Pose bpose;

    long start_time;
    long end_time;

    public CameraConstractionState_PoseLerp(Pose apose, Pose bpose, long start_time, long end_time)
    {
        this.apose = apose;
        this.bpose = bpose;
        this.start_time = start_time;
        this.end_time = end_time;
    }

    public override bool IsFree()
    {
        return false;
    }

    public override Pose CameraConstratePose(long step)
    {
        return Pose.Lerp(apose, bpose, (float)(step - start_time) / (end_time - start_time));
    }
}
