#if !UNITY_64
public static class TimelineControlClass
{
    public static void MoveTest(Checker checker)
    {
        var chronosphere = new ChronoSphere();
        Timeline timeline = new Timeline();
        chronosphere.AddTimeline(timeline);
        chronosphere.SetCurrentTimeline(timeline);

        var guard = new Actor("guard1");
        timeline.AddObject(guard);

        checker.Equal(timeline.Objects().Count, 1);
        checker.Equal(guard.Position(), new Vector3(0, 0, 0), 1e-2f);

        guard.MoveToCommand(new Vector3(10, 0, 0), is_run: true);
        timeline.PromoteToTime(5.0f);

        checker.Equal(guard.Position(), new Vector3(10, 0, 0), 1e-2f);
        timeline.PromoteToTime(2.5f);
        checker.Equal(guard.Position(), new Vector3(5, 0, 0), 1e-1f);

        checker.IsTrue(timeline.IsPast());

        guard.MoveToCommand(new Vector3(0, 10, 0), WalkingType.Run);

        checker.Equal(chronosphere.Timelines().Count, 2);
        var guard_copy = chronosphere.TimelinesList()[1].GetActor("guard1");
        checker.Equal(guard_copy.Position(), new Vector3(5, 0, 0), 1e-1f);

        var timeline_copy = chronosphere.TimelinesList()[1];
        checker.Equal(timeline_copy, chronosphere.CurrentTimeline());

        timeline_copy.PromoteToTime(10.0f);
        checker.Equal(guard_copy.Position(), new Vector3(0, 10, 0), 1e-2f);

        timeline.PromoteToTime(5.0f);
        checker.Equal(guard.Position(), new Vector3(10, 0, 0), 1e-2f);
    }

    public static void Move2Test(Checker checker)
    {
        var chronosphere = new ChronoSphere();
        Timeline timeline = new Timeline();
        chronosphere.AddTimeline(timeline);
        chronosphere.SetCurrentTimeline(timeline);

        var guard = new Actor("guard1");
        timeline.AddObject(guard);

        checker.Equal(timeline.Objects().Count, 1);
        checker.Equal(guard.Position(), new Vector3(0, 0, 0));

        guard.MoveToCommand(new Vector3(10, 0, 0), is_run: true);
        timeline.PromoteToTime(5.0f);

        checker.Equal(guard.Position(), new Vector3(10, 0, 0), 1e-1f);
        timeline.PromoteToTime(2.5f);
        checker.Equal(guard.Position(), new Vector3(5, 0, 0), 1e-1f);

        checker.IsTrue(timeline.IsPast());

        guard.MoveToCommand(new Vector3(0, 0, 10), WalkingType.Run);

        checker.Equal(chronosphere.Timelines().Count, 2);
        var guard_copy = chronosphere.TimelinesList()[1].GetActor("guard1");
        checker.Equal(guard_copy.Position(), new Vector3(5, 0, 0), 1e-1f);

        var timeline_copy = chronosphere.TimelinesList()[1];
        checker.Equal(timeline_copy, chronosphere.CurrentTimeline());

        timeline_copy.PromoteToTime(10.0f);
        checker.Equal(guard_copy.Position(), new Vector3(0, 0, 10), 1e-2f);

        timeline.PromoteToTime(5.0f);
        checker.Equal(guard.Position(), new Vector3(10, 0, 0), 1e-2f);

        timeline_copy.PromoteToTime(2.5f);
        guard_copy.MoveToCommand(new Vector3(0, 0, 0), WalkingType.Run);

        var timeline_copy2 = chronosphere.TimelinesList()[2];
        checker.Equal(chronosphere.CurrentTimeline(), timeline_copy2);
        var guard_copy2 = timeline_copy2.GetActor("guard1");

        checker.Equal(guard_copy2.Position(), guard_copy.Position());

        chronosphere.SetCurrentTimeline(timeline_copy);
        timeline_copy.PromoteToTime(500 / 480.0f);
        guard_copy.MoveToCommand(new Vector3(0, 0, 100), WalkingType.Run);

        var timeline_copy3 = chronosphere.TimelinesList()[3];
        checker.Equal(chronosphere.CurrentTimeline(), timeline_copy3);
        var guard_copy3 = timeline_copy3.GetActor("guard1");

        checker.Equal(guard_copy3.Position(), guard_copy.Position());
    }

    public static void Move3Test(Checker checker)
    {
        var chronosphere = new ChronoSphere();
        Timeline timeline = new Timeline();
        chronosphere.AddTimeline(timeline);
        chronosphere.SetCurrentTimeline(timeline);

        var guard = new Actor("guard1");
        timeline.AddObject(guard);

        checker.Equal(timeline.Objects().Count, 1);
        checker.Equal(guard.Position(), new Vector3(0, 0, 0));

        guard.MoveToCommand(new Vector3(100, 0, 0), WalkingType.Run);
        timeline.PromoteToTime(1000 / 480.0f);

        timeline.PromoteToTime(500 / 480.0f);

        guard.MoveToCommand(new Vector3(0, 100, 0), WalkingType.Run);
        var timeline_copy = chronosphere.TimelinesList()[1];
        var guard_copy = timeline_copy.GetActor("guard1");

        timeline.PromoteToTime(1000 / 480.0f);

        timeline_copy.PromoteToTime(1000 / 480.0f);
        timeline_copy.PromoteToTime(750 / 480.0f);
        checker.NotEqual(guard_copy.Position().x, 0);
        checker.NotEqual(guard_copy.Position().y, 0);

        guard_copy.MoveToCommand(new Vector3(0, 0, 100), WalkingType.Run);
        //timeline_copy.Promote(751);
        var timeline_copy2 = chronosphere.TimelinesList()[2];
        var guard_copy2 = timeline_copy2.GetActor("guard1");

        //var animatronic = guard_copy2.LastAnimatronic as MovingAnimatronic;
        //checker.Equal(animatronic.StartPosition(), guard_copy.Position());

        checker.Equal(guard_copy2.Position(), guard_copy.Position());

        timeline_copy2.PromoteToTime(751 / 480.0f);
        var pos1 = guard_copy2.Position();
        timeline_copy2.PromoteToTime(749 / 480.0f);
        var pos2 = guard_copy2.Position();

        checker.Equal(pos1, pos2, 1e-1f);
    }
}
#endif
