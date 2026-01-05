using System.Collections.Generic;

public interface IEaseFrame
{
    Pose Evaluate(float time);
}

public struct EaseFrame : IEaseFrame
{
    public Pose StartPose { get; set; }
    public Pose FinishPose { get; set; }
    public Easing.TimeCurve Curve { get; set; }

    public EaseFrame(Pose start_pose, Pose finish_pose, Easing.TimeCurve curve)
    {
        StartPose = start_pose;
        FinishPose = finish_pose;
        Curve = curve;
    }

    public Pose Evaluate(float time)
    {
        if (time < Curve.zero)
            return StartPose;
        if (time > Curve.zero + Curve.multiplier)
            return FinishPose;
        var coeff = Curve.Evaluate(time);
        return Pose.Lerp(StartPose, FinishPose, coeff);
    }
}

public class ComplexEaseFrame
{
    MyList<IEaseFrame> Frames { get; set; } = new MyList<IEaseFrame>();

    public ComplexEaseFrame() { }

    public ComplexEaseFrame(MyList<IEaseFrame> frames)
    {
        Frames = frames;
    }

    public void AddFrame(EaseFrame frame)
    {
        Frames.Add(frame);
    }

    public Pose Evaluate(float time)
    {
        Pose result = Pose.Identity;
        foreach (var frame in Frames)
        {
            result *= frame.Evaluate(time);
        }
        return result;
    }
}
