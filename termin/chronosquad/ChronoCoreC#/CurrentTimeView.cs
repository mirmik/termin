public class CurrentTimelineView
{
    ChronoSphere _chronosphere;

    public CurrentTimelineView(ChronoSphere chronosphere)
    {
        _chronosphere = chronosphere;
    }

    public Timeline CurrentTimeline()
    {
        return _chronosphere.CurrentTimeline();
    }

    public void PromoteTime(float time)
    {
        CurrentTimeline().PromoteToTime(time);
    }

    public void CreateReversePass()
    {
        var ntl = CurrentTimeline().Copy();
        ntl.SetReversedPass(!CurrentTimeline().IsReversedPass());
        _chronosphere.AddTimeline(ntl);
        ntl.SetCurrent();
    }
}
