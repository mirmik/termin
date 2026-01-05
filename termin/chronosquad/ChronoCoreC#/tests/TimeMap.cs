#if !UNITY_64
static class TimeMapTests
{
    static public void TimeMapTest(Checker checker)
    {
        ChronoSphere chronosphere = new ChronoSphere();
        var tl = chronosphere.CreateEmptyTimeline();
        TimelineMap map = new TimelineMap(chronosphere);

        tl.PromoteToTime(20.0f);
        tl.PromoteToTime(-10.0f);

        var list = map.Intervals();
        checker.Equal(list[0].Item1, (long)-2400);
        checker.Equal(list[0].Item2, (long)4800);
    }

    static public void TimeMapDrawerTest(Checker checker)
    {
        ChronoSphere chronosphere = new ChronoSphere();
        var tl = chronosphere.CreateEmptyTimeline();

        GameObject canvas = new GameObject("Canvas");
        GameObject go = new GameObject("TimelineGraph");
        go.AddComponent<TimelineGraph>();
        TimelineGraph drawer = go.GetComponent<TimelineGraph>();

        drawer.SetChronosphere(chronosphere);
        drawer.Init(canvas);

        tl.PromoteToTime(20.0f);
        var tlcopy = tl.Copy();
        tlcopy.DropLastTimelineStep();
        chronosphere.AddTimeline(tlcopy);

        tlcopy.PromoteToTime(-20.0f);
        var tlcopy2 = tlcopy.Copy();
        tlcopy2.DropLastTimelineStep();
        chronosphere.AddTimeline(tlcopy2);

        drawer.UpdateTimelineDrawsObject(canvas);
        drawer.UpdateTimelineDrawsCoordinates();
        checker.Equal(drawer.CountOfLines(), 3);

        TimelineGraphDraw graph0 = drawer.TimelineDraws.Values.ToList()[0];
        TimelineGraphDraw graph1 = drawer.TimelineDraws.Values.ToList()[1];
        TimelineGraphDraw graph2 = drawer.TimelineDraws.Values.ToList()[2];

        checker.Equal(graph0.Level, drawer.TopLevel);
        checker.Equal(graph1.Level, drawer.TopLevel + 100.0f);
        checker.Equal(graph2.Level, drawer.TopLevel + 200.0f);

        checker.Equal(graph0.Start(), (long)0);
        checker.Equal(graph1.Start(), (long)(20.0f * Utility.GAME_GLOBAL_FREQUENCY));
        checker.Equal(graph2.Start(), (long)(-20.0f * Utility.GAME_GLOBAL_FREQUENCY));

        checker.Equal(graph1.ParentStart(), (long)(20.0f * Utility.GAME_GLOBAL_FREQUENCY));
        checker.Equal(graph2.ParentStart(), (long)(-20.0f * Utility.GAME_GLOBAL_FREQUENCY));

        checker.Equal(graph0.Maximal(), (long)(20.0f * Utility.GAME_GLOBAL_FREQUENCY));
        checker.Equal(graph1.Maximal(), (long)(20.0f * Utility.GAME_GLOBAL_FREQUENCY));
        checker.Equal(graph2.Maximal(), (long)(-20.0f * Utility.GAME_GLOBAL_FREQUENCY));

        checker.Equal(graph0.Minimal(), (long)0);
        checker.Equal(graph1.Minimal(), (long)(-20.0f * Utility.GAME_GLOBAL_FREQUENCY));
        checker.Equal(graph2.Minimal(), (long)(-20.0f * Utility.GAME_GLOBAL_FREQUENCY));

        checker.Equal(graph0.HasParent(), false);
        checker.Equal(graph1.HasParent(), true);
        checker.Equal(graph2.HasParent(), true);

        checker.Equal(graph1.Parent().Level, drawer.TopLevel);
        checker.Equal(graph2.Parent().Level, drawer.TopLevel + 100.0f);
    }
}

#endif
