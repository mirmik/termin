#if !UNITY_64
static class TimePhantomTests
{
    // static public void TimePhantomTest(Checker checker)
    // {
    // 	var chronosphere = new ChronoSphere();
    // 	var tl = chronosphere.CreateEmptyTimeline();
    // 	var guard = tl.CreateGuard("obj");

    // 	var ability = new ReverseAbilitySimplified();
    // 	guard.AddAbility(ability);

    // 	tl.Promote(1000);
    // 	guard.AbilityUseSelf<ReverseAbilitySimplified>();
    // 	checker.Equal(tl, chronosphere.CurrentTimeline());

    // 	tl.Promote(2000);
    // 	checker.Equal(tl.Objects().Count, 1);
    // 	checker.Equal(tl.NextPassList().Count, 1);

    // 	var ntl = tl.Copy(reverse: true);
    // 	ntl.Promote(0);

    // 	checker.Equal(ntl.NextPassList().Count, 0);
    // 	checker.Equal(ntl.Objects().Count, 2);
    // }
    static public void TimeParadoxTest_Internal(Checker checker)
    {
        ParadoxStatus status;
        var chronosphere = new ChronoSphere();
        var tl = chronosphere.CreateEmptyTimeline();
        var guard = tl.CreateGuard("obj");
        guard.MarkAsHero();
        guard.SetPosition(new Vector3(0, 1, 0));

        status = tl.CheckTimeParadox();
        checker.Equal(status, ParadoxStatus.NoParadox);

        tl.Promote(999);
        tl.Promote(1000);
        guard.MoveToCommand(new Vector3(10, 0, 0), WalkingType.Walk);

        tl.Promote(1001);
        checker.Equal(guard.CommandBuffer().GetCommandQueue().Count, 1);
        checker.Equal(guard.CommandBuffer().GetCommandQueue().AsList()[0].StartStep, (long)1001);
        checker.Equal(guard.Animatronics().Count, 2);
        checker.Equal((guard.Animatronics().AsList()[0] as IdleAnimatronic).StartStep, (long)1);
        checker.Equal(
            (guard.Animatronics().AsList()[0] as IdleAnimatronic).FinishStep,
            long.MaxValue
        );
        checker.Equal(
            (guard.Animatronics().AsList()[1] as MovingAnimatronic).StartStep,
            (long)1001
        );
        checker.Equal(
            (guard.Animatronics().AsList()[1] as MovingAnimatronic).FinishStep,
            (long)3412
        );
        checker.Equal(
            (guard.Animatronics().AsList()[1] as MovingAnimatronic).InterruptionStep,
            (long)3412
        );
        var pose = guard.CurrentReferencedPose();

        tl.Promote(0);
        tl.DropTimelineToCurrentState();

        tl.Promote(999);
        tl.Promote(1000);
        tl.Promote(1001);
        checker.Equal(guard.Animatronics().Count, 2);
        checker.Equal((guard.Animatronics().AsList()[0] as IdleAnimatronic).StartStep, (long)1);
        checker.Equal(
            (guard.Animatronics().AsList()[0] as IdleAnimatronic).FinishStep,
            long.MaxValue
        );
        checker.Equal(
            (guard.Animatronics().AsList()[1] as MovingAnimatronic).StartStep,
            (long)1001
        );
        checker.Equal(
            (guard.Animatronics().AsList()[1] as MovingAnimatronic).FinishStep,
            (long)3412
        );
        checker.Equal(
            (guard.Animatronics().AsList()[1] as MovingAnimatronic).InterruptionStep,
            (long)3412
        );
        var pose1 = guard.CurrentReferencedPose();

        checker.Equal(pose, pose1);
    }

    static public void TimeParadoxTest_StepByStep(Checker checker)
    {
        ParadoxStatus status;
        var chronosphere = new ChronoSphere();
        var tl = chronosphere.CreateEmptyTimeline();
        var guard = tl.CreateGuard("obj");
        guard.MarkAsHero();
        guard.SetPosition(new Vector3(0, 1, 0));

        status = tl.CheckTimeParadox();
        checker.Equal(status, ParadoxStatus.NoParadox);

        tl.Promote(1000);
        status = tl.CheckTimeParadox();
        checker.Equal(status, ParadoxStatus.NoParadox);
        guard.MoveToCommand(new Vector3(10, 0, 0), WalkingType.Walk);
        status = tl.CheckTimeParadox();
        checker.Equal(status, ParadoxStatus.NoParadox);

        tl.Promote(1001);
        status = tl.CheckTimeParadox();
        checker.Equal(status, ParadoxStatus.NoParadox);

        tl.Promote(1002);
        status = tl.CheckTimeParadox();
        checker.Equal(status, ParadoxStatus.NoParadox);

        tl.Promote(1003);
        status = tl.CheckTimeParadox();
        checker.Equal(status, ParadoxStatus.NoParadox);

        tl.Promote(1004);
        status = tl.CheckTimeParadox();
        checker.Equal(status, ParadoxStatus.NoParadox);

        tl.Promote(1005);

        status = tl.CheckTimeParadox();
        checker.Equal(status, ParadoxStatus.NoParadox);
    }

    static public void TimeParadoxTest(Checker checker)
    {
        ParadoxStatus status;
        var chronosphere = new ChronoSphere();
        var tl = chronosphere.CreateEmptyTimeline();
        var guard = tl.CreateGuard("obj");
        guard.MarkAsHero();
        guard.SetPosition(new Vector3(0, 1, 0));

        status = tl.CheckTimeParadox();
        checker.Equal(status, ParadoxStatus.NoParadox);

        tl.PromoteToTime(1.0f);
        guard.MoveToCommand(new Vector3(10, 0, 0), WalkingType.Walk);

        tl.PromoteToTime(1.1f);

        status = tl.CheckTimeParadox();
        checker.Equal(status, ParadoxStatus.NoParadox);

        tl.PromoteToTime(21.0f);
        checker.Equal(guard.Position(), new Vector3(10, 0, 0));

        status = tl.CheckTimeParadox();
        checker.Equal(status, ParadoxStatus.NoParadox);

        guard.MoveToCommand(new Vector3(0, 10, 0), WalkingType.Walk);
        tl.PromoteToTime(23.0f);

        status = tl.CheckTimeParadox();
        checker.Equal(status, ParadoxStatus.NoParadox);
    }

    // public static void TimeParadoxPatrol_Test(Checker checker)
    // {
    //     Actor obj = new Actor();
    //     Timeline timeline = new Timeline();
    //     timeline.AddObject("obj", obj);

    //     var ai_controller = new BasicAiController(obj);
    //     ai_controller.AddCommander(new PatrolAiCommander(), name: "patrol", priority: 0);
    //     obj.SetAiController(ai_controller);

    //     ai_controller
    //         .GetCommander<PatrolAiCommander>()
    //         .SetPoints(
    //             new MyList<PatrolPoint>()
    //             {
    //                 new PatrolPoint(new Vector3(20, 20, 0)),
    //                 new PatrolPoint(new Vector3(10, 0, 0)),
    //                 new PatrolPoint(new Vector3(0, 10, 0))
    //             }
    //         );

    //     timeline.Promote(10);
    //     checker.Equal(((Actor)obj).CurrentAnimatronic().GetType(), typeof(MovingAnimatronic));

    //     var copy = timeline.Copy();
    //     copy.Promote(0);
    //     copy.DropTimelineToCurrentState();

    //     var cobj = copy.GetObject("obj");
    //     checker.Equal(((Actor)cobj).CurrentAnimatronic(), (Animatronic)null);

    //     //checker.IsTrue(((Actor)cobj).Animatronics().AsList()[0].HashCode() == ((Actor)obj).Animatronics().AsList()[0].HashCode());
    //     //checker.IsTrue(((Actor)cobj).Animatronics().AsList()[1].HashCode() == ((Actor)obj).Animatronics().AsList()[1].HashCode());

    //     checker.Equal(cobj.Position(), new Vector3(0, 0, 0));
    //     //checker.Equal(((Actor)cobj).Animatronics().Count, 2);
    //     //checker.Equal(((Actor)cobj).Animatronics().AsList()[0].GetType(), typeof(IdleAnimatronic));
    //     //checker.Equal(((Actor)cobj).Animatronics().AsList()[1].GetType(), typeof(MovingAnimatronic));

    //     timeline.Promote(0);
    //     timeline.Promote(5);

    //     copy.Promote(0);
    //     copy.Promote(5);

    //     checker.Equal(((Actor)obj).AiController().Changes.MyList.Count, 0);
    //     checker.Equal(((Actor)cobj).AiController().Changes.MyList.Count, 0);

    //     timeline.PromoteToTime(10.0f);
    //     checker.IsTrue(
    //         ((Actor)cobj).CommandBuffer().GetCommandQueue().AsList()[0].HashCode()
    //             == ((Actor)obj).CommandBuffer().GetCommandQueue().AsList()[0].HashCode()
    //     );
    //     //checker.IsTrue(((Actor)cobj).Animatronics().AsList()[0].HashCode() == ((Actor)obj).Animatronics().AsList()[0].HashCode());
    //     //checker.IsTrue(((Actor)cobj).Animatronics().AsList()[1].HashCode() == ((Actor)obj).Animatronics().AsList()[1].HashCode());

    //     //checker.Equal(((Actor)obj).CurrentAnimatronic(), (Animatronic)null);
    //     //checker.Equal(((Actor)cobj).CurrentAnimatronic(), (Animatronic)null);

    //     //checker.Equal(copy.CurrentStep(), timeline.CurrentStep());
    //     var tpos = obj.Position();
    //     var cpos = cobj.Position();
    //     //checker.Equal(cpos, tpos);

    //     checker.NotEqual(obj.Position(), new Vector3(0, 0, 0));
    //     checker.Equal(timeline.CheckTimeParadox(), ParadoxStatus.NoParadox);

    //     checker.Equal(timeline.CheckTimeParadox(), ParadoxStatus.NoParadox);

    //     checker.Equal(copy.CheckTimeParadox(), ParadoxStatus.NoParadox);
    // }

    public static void MoveCommand_ParadoxCheckImitation0_Test(Checker checker)
    {
        Actor obj = new Actor();
        obj.MarkAsHero();
        ChronoSphere chronosphere = new ChronoSphere();
        Timeline timeline = new Timeline();
        chronosphere.AddTimeline(timeline);
        timeline.AddObject("obj", obj);
        obj.SetDirection(new Vector3(0, 0, 1));

        timeline.PromoteToTime(1.0f);
        obj.MoveToCommand(new Vector3(10, 0, 0), WalkingType.Walk);
        timeline.PromoteToTime(2.0f);
        obj.MoveToCommand(new Vector3(0, 0, 10), WalkingType.Walk);
        timeline.PromoteToTime(13.0f);

        var pose = obj.CurrentReferencedPose();
        long current_step = timeline.CurrentStep();

        timeline.PromoteToTime(0.0f);

        timeline.DropTimelineToCurrentState();

        timeline.PromoteToTime(1.0f);
        obj.MoveToCommand(new Vector3(10, 0, 0), WalkingType.Walk);
        timeline.PromoteToTime(2.0f);
        obj.MoveToCommand(new Vector3(0, 0, 10), WalkingType.Walk);
        timeline.Promote(current_step);

        var pose1 = obj.CurrentReferencedPose();

        checker.Equal(pose, pose1);
    }

    public static void MoveCommand_ParadoxCheckImitation_Test(Checker checker)
    {
        Actor obj = new Actor();
        obj.MarkAsHero();
        ChronoSphere chronosphere = new ChronoSphere();
        Timeline timeline = new Timeline();
        chronosphere.AddTimeline(timeline);
        timeline.AddObject("obj", obj);

        timeline.PromoteToTime(1.0f);
        obj.MoveToCommand(new Vector3(10, 0, 0), WalkingType.Walk);
        timeline.PromoteToTime(2.0f);
        obj.MoveToCommand(new Vector3(0, 0, 10), WalkingType.Walk);
        timeline.PromoteToTime(13.0f);

        var pose = obj.CurrentReferencedPose();

        timeline.PromoteToTime(0.0f);
        timeline.DropTimelineToCurrentState();
        timeline.PromoteToTime(13.0f);

        var pose1 = obj.CurrentReferencedPose();

        checker.Equal(pose, pose1);
    }

    public static void MoveCommand_Test(Checker checker)
    {
        Actor obj = new Actor();
        obj.MarkAsHero();
        ChronoSphere chronosphere = new ChronoSphere();
        Timeline timeline = new Timeline();
        chronosphere.AddTimeline(timeline);
        timeline.AddObject("obj", obj);
        obj.SetDirection(new Vector3(0, 0, 1));

        timeline.PromoteToTime(1.0f);

        obj.MoveToCommand(new Vector3(10, 0, 0), WalkingType.Walk);
        //checker.Equal(obj.Direction(), new Vector3(1, 0, 0));

        timeline.PromoteToTime(2.0f);
        checker.Equal(obj.Direction(), new Vector3(1, 0, 0), 1e-5f);

        obj.MoveToCommand(new Vector3(0, 0, 10), WalkingType.Walk);

        timeline.PromoteToTime(13.0f);
        checker.NotEqual(obj.Direction(), new Vector3(1, 0, 0));

        checker.Equal(obj.Position(), new Vector3(0, 0, 10));

        var pose = obj.CurrentReferencedPose();

        Timeline copy = timeline.Copy();
        copy.Promote(0 * (long)Utility.GAME_GLOBAL_FREQUENCY);
        copy.DropTimelineToCurrentState();
        copy.Promote(timeline.CurrentStep());

        var pose1 = obj.CurrentReferencedPose();

        checker.Equal(timeline.CheckTimeParadox(), ParadoxStatus.NoParadox);
    }

    public static void MoveCommand2_Test(Checker checker)
    {
        Actor obj = new Actor();
        obj.MarkAsHero();
        ChronoSphere chronosphere = new ChronoSphere();
        Timeline timeline = new Timeline();
        chronosphere.AddTimeline(timeline);
        timeline.AddObject("obj", obj);

        timeline.PromoteToTime(0.1f);

        obj.MoveToCommand(new Vector3(10, 0, 0), WalkingType.Walk);

        timeline.PromoteToTime(2.0f);
        checker.Equal(timeline.CheckTimeParadox(), ParadoxStatus.NoParadox);

        obj.MoveToCommand(new Vector3(0, 10, 0), WalkingType.Walk);

        timeline.PromoteToTime(7.0f);
        //checker.Equal(timeline.CheckTimeParadox(), ParadoxStatus.NoParadox);

        obj.MoveToCommand(new Vector3(0, 0, 11), WalkingType.Walk);

        timeline.PromoteToTime(11.0f);
        checker.Equal(timeline.CheckTimeParadox(), ParadoxStatus.NoParadox);

        timeline.PromoteToTime(20.0f);
        checker.Equal(obj.Position(), new Vector3(0, 0, 11));
        checker.Equal(timeline.CheckTimeParadox(), ParadoxStatus.NoParadox);
    }

    public static void MoveCommand3_Test(Checker checker)
    {
        Actor obj = new Actor();
        obj.MarkAsHero();
        ChronoSphere chronosphere = new ChronoSphere();
        Timeline timeline = new Timeline();
        chronosphere.AddTimeline(timeline);
        timeline.AddObject("obj", obj);
        timeline.PromoteToTime(0.1f);

        obj.MoveToCommand(new Vector3(10, 0, 0), WalkingType.Walk);

        timeline.PromoteToTime(2.0f);
        checker.Equal(obj.Animatronics().Count, 2);
        checker.Equal(timeline.CheckTimeParadox(), ParadoxStatus.NoParadox);

        obj.MoveToCommand(new Vector3(0, 10, 0), WalkingType.Walk);

        timeline.PromoteToTime(7.0f);
        checker.Equal(obj.CommandBuffer().GetCommandQueue().Count, 3);
        checker.Equal(obj.Animatronics().Count, 3);

        var copy = timeline.Copy();
        var cobj = (Actor)copy.GetObject("obj");
        checker.Equal(timeline.CheckTimeParadox(), ParadoxStatus.NoParadox);

        copy.PromoteToTime(0.0f);
        copy.DropTimelineToCurrentState();
        copy.PromoteToTime(7.0f);

        checker.Equal(obj.CommandBuffer().GetCommandQueue().Count, 3);
        checker.Equal(cobj.CommandBuffer().GetCommandQueue().Count, 3);

        checker.Equal(obj.Animatronics().Count, 3);
        checker.Equal(cobj.Animatronics().Count, 3);
        checker.Equal(
            obj.Animatronics().AsList()[0].StartStep,
            cobj.Animatronics().AsList()[0].StartStep
        );
        checker.Equal(obj.Animatronics().AsList()[1].GetType(), typeof(MovingAnimatronic));
        checker.Equal(obj.Animatronics().AsList()[2].GetType(), typeof(MovingAnimatronic));
        checker.Equal(cobj.Animatronics().AsList()[1].GetType(), typeof(MovingAnimatronic));
        checker.Equal(
            ((MovingAnimatronic)cobj.Animatronics().AsList()[1]).FinishPosition(),
            new Vector3(10, 0, 0)
        );
        checker.Equal(
            ((MovingAnimatronic)cobj.Animatronics().AsList()[2]).FinishPosition(),
            new Vector3(0, 10, 0)
        );
        checker.Equal(
            ((MovingAnimatronic)obj.Animatronics().AsList()[1]).FinishPosition(),
            new Vector3(10, 0, 0)
        );
        checker.Equal(
            ((MovingAnimatronic)obj.Animatronics().AsList()[2]).FinishPosition(),
            new Vector3(0, 10, 0)
        );
        checker.Equal(obj.Animatronics().Count, cobj.Animatronics().Count);
        checker.Equal(obj.Position(), cobj.Position());

        checker.Equal(
            obj.CommandBuffer().GetCommandQueue().Count,
            cobj.CommandBuffer().GetCommandQueue().Count
        );
        checker.Equal(timeline.CheckTimeParadox(), ParadoxStatus.NoParadox);
    }

    // public static void Death_Test(Checker checker)
    // {
    //     Actor obj = new Actor();
    //     Actor killer = new Actor();
    //     obj.MarkAsHero();
    //     killer.MarkAsHero();
    //     Timeline timeline = new Timeline();
    //     timeline.AddObject("obj", obj);
    //     timeline.AddObject("killer", killer);
    //     timeline.PromoteToTime(0.1f);

    //     obj.MoveToCommand(new Vector3(10, 0, 0), WalkingType.Walk);
    //     timeline.PromoteToTime(2.0f);
    //     checker.Equal(timeline.CheckTimeParadox(), ParadoxStatus.NoParadox);

    //     killer.AddExternalCommand(new ShootCommand(obj, 100, null, killer.LocalStep() + 1));
    //     checker.Equal(timeline.CheckTimeParadox(), ParadoxStatus.NoParadox);

    //     timeline.PromoteToTime(5.0f);

    //     var copy = timeline.Copy();
    //     checker.Equal(copy.GlobalEvents().MyList.Count, 2);
    //     copy.PromoteToTime(0.0f);
    //     checker.Equal(copy.GlobalEvents().MyList.Count, 2);
    //     copy.DropTimelineToCurrentState();
    //     checker.Equal(copy.GlobalEvents().MyList.Count, 0);
    //     copy.PromoteToTime(5.0f);
    //     checker.Equal(copy.GlobalEvents().MyList.Count, 2);

    //     checker.Equal(timeline.GlobalEvents().MyList.Count, 2);
    //     checker.Equal(copy.GlobalEvents().MyList.Count, 2);

    //     //checker.Equal(timeline.CheckTimeParadox(), ParadoxStatus.NoParadox);
    // }

    static public void OnZeroMoveTest(Checker checker)
    {
        var chronosphere = new ChronoSphere();
        var tl = chronosphere.CreateEmptyTimeline();
        var guard = tl.CreateGuard("obj");

        guard.MoveToCommand(new Vector3(10, 0, 0), WalkingType.Walk);
        tl.PromoteToTime(20.0f);

        checker.Equal(guard.Position(), new Vector3(10, 0, 0));

        checker.Equal(tl.CheckTimeParadox(), ParadoxStatus.NoParadox);
    }

    // static public void CancelledReverseParadoxTest(Checker checker)
    // {
    //     var chronosphere = new ChronoSphere();
    //     var tl = chronosphere.CreateEmptyTimeline();
    //     var guard = tl.CreateGuard("guard");
    //     guard.MarkAsHero();
    //     guard.AddAbility(new StepToPastAbility(1.0f));

    //     tl.PromoteToTime(10.0f);

    //     guard.AbilityUseSelf<StepToPastAbility>();

    //     var ntl = chronosphere.Timelines().Values.ToList()[1];
    //     checker.Equal(ntl.CurrentTime(), 9.0f);
    //     checker.Equal(ntl.Objects().Count, 2);

    //     ntl.PromoteToTime(8.0f);
    //     checker.Equal(ntl.CheckTimeParadox(), ParadoxStatus.NoParadox);

    //     guard = ntl.Objects().Values.ToList()[0] as Actor;
    //     guard.MoveToCommand(new Vector3(10.0f, 0, 0), WalkingType.Walk);

    //     var nntl = chronosphere.Timelines().Values.ToList()[2];
    //     var guard0 = nntl.Objects().Values.ToList()[0] as Actor;
    //     var guard1 = nntl.Objects().Values.ToList()[1] as Actor;
    //     nntl.PromoteToTime(10.0f);

    //     Debug.Log("************************************************");
    //     checker.Equal(nntl.CheckTimeParadox(), ParadoxStatus.ParadoxDetected);
    //     Debug.Log("************************************************");
    //     nntl.MarkParadoxes();

    //     checker.Equal(guard0.IsTimeParadox(), false);
    //     checker.Equal(guard1.IsTimeParadox(), true);
    // }

    // static public void CancelledDeadParadoxTest(Checker checker)
    // {
    //     var chronosphere = new ChronoSphere();
    //     var tl = chronosphere.CreateEmptyTimeline();
    //     var killer0 = tl.CreateGuard("killer");
    //     var victim = tl.CreateGuard("victim");

    //     var timeline_controller = new CurrentTimelineView(chronosphere);
    //     var killer0_controller = new ObjectSelector(killer0.Name(), timeline_controller);
    //     var victim_controller = new ObjectSelector(victim.Name(), timeline_controller);

    //     killer0.AddAbility(new ReverseAbility(null));
    //     killer0.AddAbility(new ShootAbility(100, null));
    //     killer0.AddAbility(new RecombinateAbility());

    //     timeline_controller.PromoteTime(6.0f);

    //     checker.Equal(
    //         timeline_controller.CurrentTimeline().CheckTimeParadox(),
    //         ParadoxStatus.NoParadox
    //     );

    //     killer0_controller.UseSelf<ReverseAbility>();
    //     var killer1 = timeline_controller.CurrentTimeline().Objects().Values.ToList()[2] as Actor;
    //     var killer1_controller = new ObjectSelector(killer1.Name(), timeline_controller);

    //     checker.Equal(
    //         timeline_controller.CurrentTimeline().CheckTimeParadox(),
    //         ParadoxStatus.NoParadox
    //     );

    //     timeline_controller.PromoteTime(3.0f);
    //     killer1_controller.UseSelf<ReverseAbility>();
    //     var killer2 = timeline_controller.CurrentTimeline().Objects().Values.ToList()[3] as Actor;
    //     var killer2_controller = new ObjectSelector(killer2.Name(), timeline_controller);

    //     checker.Equal(
    //         timeline_controller.CurrentTimeline().CheckTimeParadox(),
    //         ParadoxStatus.NoParadox
    //     );

    //     timeline_controller.PromoteTime(5.0f);
    //     killer2_controller.UseOnObject<ShootAbility>(victim_controller.Object());

    //     checker.Equal(
    //         timeline_controller.CurrentTimeline().CheckTimeParadox(),
    //         ParadoxStatus.NoParadox
    //     );

    //     timeline_controller.PromoteTime(6.0f);

    //     checker.Equal(
    //         timeline_controller.CurrentTimeline().CheckTimeParadox(),
    //         ParadoxStatus.NoParadox
    //     );
    //     timeline_controller.PromoteTime(4.0f);

    //     checker.Equal(
    //         timeline_controller.CurrentTimeline().CheckTimeParadox(),
    //         ParadoxStatus.NoParadox
    //     );

    //     timeline_controller.CreateReversePass();
    //     checker.Equal(chronosphere.TimelinesCount, 4);

    //     checker.Equal(
    //         timeline_controller.CurrentTimeline().CheckTimeParadox(),
    //         ParadoxStatus.NoParadox
    //     );
    // }
}
#endif
