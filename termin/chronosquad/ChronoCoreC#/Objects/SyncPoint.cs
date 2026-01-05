public class SyncPoint
{
    //ChronoSphere ch;
    Timeline synced_timeline;

    public SyncPoint(Timeline timeline)
    {
        synced_timeline = timeline.Copy();
    }

    public void Load()
    {
        //var copy = synced_timeline.Copy();
        //ch.SetCurrentTimeline(copy);
    }
}
