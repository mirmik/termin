#if !UNITY_64
static class ReversePassTests
{
    static public void PassMoveTest(Checker checker)
    {
        ChronoSphere chronosphere = new ChronoSphere();
        Timeline tl = new Timeline();
        chronosphere.SetCurrentTimeline(tl);

        var guard = new Actor("guard");
        tl.AddObject(guard);

        tl.Promote(1000);
        checker.Equal(tl.CurrentStep(), (long)1000);

        checker.Equal(guard.Position(), new Vector3(0, 0, 0));

        guard.MoveToCommand(new Vector3(1, 0, 0), WalkingType.Walk);

        checker.Equal(tl.IsPast(), false);
        tl.Promote(2000);
        checker.Equal(tl.IsPast(), false);
        checker.Equal(tl.CurrentStep(), (long)2000);
        checker.Equal(guard.Position(), new Vector3(1, 0, 0));

        tl.Promote(0);
        checker.Equal(tl.IsPast(), true);
        checker.Equal(tl.CurrentStep(), (long)0);
        checker.Equal(guard.Position(), new Vector3(0, 0, 0));
    }

    static public void PassMoveTest3(Checker checker)
    {
        ChronoSphere chronosphere = new ChronoSphere();
        Timeline tl = new Timeline();
        chronosphere.SetCurrentTimeline(tl);

        var guard = new Actor("guard");
        tl.AddObject(guard);

        tl.Promote(51000);
        checker.Equal(tl.CurrentStep(), (long)51000);

        checker.Equal(guard.Position(), new Vector3(0, 0, 0));

        guard.MoveToCommand(new Vector3(1, 0, 0), WalkingType.Walk);

        // checker.Equal(tl.IsPast(), false);
        // tl.Promote(52000);
        // checker.Equal(tl.IsPast(), false);
        // checker.Equal(tl.CurrentStep(), (long)52000);
        // checker.Equal(guard.Position(), new Vector3(1, 0, 0));

        tl.Promote(50000);
        checker.Equal(tl.IsPast(), true);
        checker.Equal(tl.CurrentStep(), (long)50000);
        checker.Equal(guard.Position(), new Vector3(0, 0, 0));
    }

    static public void ReversePassMoveTest(Checker checker)
    {
        ChronoSphere chronosphere = new ChronoSphere();
        Timeline tl = new Timeline();
        chronosphere.SetCurrentTimeline(tl);

        var guard = new Actor("guard");
        tl.AddObject(guard);

        tl.SetReversedPass(true);
        tl.SetMinimalStep(long.MinValue);
        guard.SetReversed(true);

        tl.Promote(-1000);
        checker.Equal(tl.CurrentStep(), (long)-1000);

        checker.Equal(guard.Position(), new Vector3(0, 0, 0));

        guard.MoveToCommand(new Vector3(1, 0, 0), WalkingType.Walk);

        checker.Equal(tl.IsPast(), false);
        tl.Promote(-2000);
        checker.Equal(tl.IsPast(), false);
        checker.Equal(tl.CurrentStep(), (long)-2000);
        checker.Equal(guard.Position(), new Vector3(1, 0, 0));

        tl.Promote(0);
        checker.Equal(tl.IsPast(), true);
        checker.Equal(tl.CurrentStep(), (long)0);
        checker.Equal(guard.Position(), new Vector3(0, 0, 0));
    }

    static public void ReverseDeathTest(Checker checker)
    {
        ChronoSphere chronosphere = new ChronoSphere();
        Timeline tl = new Timeline();
        chronosphere.SetCurrentTimeline(tl);

        var guard = new Actor("guard");
        tl.AddObject(guard);

        tl.SetReversedPass(true);
        tl.SetMinimalStep(long.MinValue);
        guard.SetReversed(true);

        tl.Promote(-1000);

        tl.AddEvent(new DeathEvent(step: -1500, actor: guard, who_kill_me: null, reversed: true));
        checker.Equal(guard.IsDead || guard.IsPreDead, false);

        tl.Promote(-2000);
        checker.Equal(guard.IsDead || guard.IsPreDead, true);
    }

    static public void ShootInReverseTimeTest(Checker checker)
    {
        ChronoSphere chronosphere = new ChronoSphere();
        Timeline tl = new Timeline();
        chronosphere.SetCurrentTimeline(tl);
        var guard = new Actor("guard");
        var killer = new Actor("killer");
        tl.AddObject(guard);
        tl.AddObject(killer);
        tl.SetReversedPass(true);
        tl.SetMinimalStep(long.MinValue);
        guard.SetReversed(true);
        killer.SetReversed(true);

        guard.MoveToCommand(new Vector3(2, 0, 0), WalkingType.Walk);

        checker.Equal(killer.Animatronics().Count, 0);
        tl.PromoteToTime(-1100 / 480.0f);
        checker.Equal(killer.Animatronics().Count, 1);

        killer.AddExternalCommand(
            new ShootCommand(
                target_actor: guard.ObjectId(),
                shoot_distance: 1,
                stamp: killer.LocalStep() + 1,
                can_shoot_from_croach: true
            )
        );
        tl.PromoteToTime(-1100 / 480.0f - 0.5f);

        checker.Equal(killer.Animatronics().Count, 2);
        tl.PromoteToTime(-3000 / 480.0f);
        checker.Equal(killer.Animatronics().First.Value.GetType(), typeof(IdleAnimatronic));
        checker.Equal(killer.Animatronics().First.Next.Value.GetType(), typeof(MovingAnimatronic));
        checker.Equal(
            killer.Animatronics().First.Next.Next.Value.GetType(),
            typeof(ShootAnimatronic)
        );
        checker.Equal(
            killer.Animatronics().First.Next.Next.Next.Value.GetType(),
            typeof(IdleAnimatronic)
        );

        checker.Equal(guard.IsDead, true);

        tl.PromoteToTime(-500 / 480.0f);
        checker.Equal(guard.IsDead, false);
    }

    public static void PatrolInReverseTimeTest(Checker checker)
    {
        Actor obj = new Actor();
        Timeline timeline = new Timeline();
        timeline.AddObject("obj", obj);

        var ai_controller = new BasicAiController(obj);
        ai_controller.AddCommander(new PatrolAiCommander(), name: "patrol", priority: 0);
        obj.SetAiController(ai_controller);

        timeline.SetReversedPass(true);
        timeline.SetMinimalStep(long.MinValue);
        obj.SetReversed(true);

        ai_controller
            .GetCommander<PatrolAiCommander>()
            .SetPoints(
                new MyList<PatrolPoint>()
                {
                    new PatrolPoint(new Vector3(2, 2, 0)),
                    new PatrolPoint(new Vector3(1, 0, 0)),
                    new PatrolPoint(new Vector3(0, 1, 0))
                }
            );

        timeline.PromoteToTime(-1.0f);
        checker.Equal(
            (obj.CurrentAnimatronic() as MovingAnimatronic).FinishPosition(),
            new Vector3(2, 2, 0)
        );
        checker.Equal(
            (obj.AiController() as BasicAiController)
                .GetCommander<PatrolAiCommander>()
                .TargetPointIndex(),
            0
        );
        checker.NotEqual(obj.Position(), new Vector3(0, 0, 0));

        timeline.PromoteToTime(-2.92f);
        checker.Equal(obj.Position(), new Vector3(2, 2, 0), 0.5f);
        // checker.Equal(
        // 	(obj.AiController() as BasicAiController)
        // 		.GetCommander<PatrolAiCommander>()
        // 		.TargetPointIndex(),
        // 	1
        // );

        timeline.PromoteToTime(-5.24f);
        checker.Equal(obj.Position(), new Vector3(1, 0, 0), 0.5f);
        // checker.Equal(
        // 	(obj.AiController() as BasicAiController)
        // 		.GetCommander<PatrolAiCommander>()
        // 		.TargetPointIndex(),
        // 	2
        // );

        timeline.PromoteToTime(-7.00f);
        // checker.Equal(
        // 	(obj.AiController() as BasicAiController)
        // 		.GetCommander<PatrolAiCommander>()
        // 		.TargetPointIndex(),
        // 	0
        // );

        timeline.PromoteToTime(-9.00f);
        // checker.Equal(
        // 	(obj.AiController() as BasicAiController)
        // 		.GetCommander<PatrolAiCommander>()
        // 		.TargetPointIndex(),
        // 	1
        // );
    }

    // public static void PatrolInReverseTimeTest_HeroHunt_AiModule(Checker checker)
    // {
    // 	Actor obj = new Actor();
    // 	obj.AddAbility(new ShootAbility(shoot_distance: 10.0f));
    // 	Actor hero = new Actor();
    // 	Timeline timeline = new Timeline();
    // 	hero.MarkAsHero();
    // 	hero.SetPosition(new Vector3(3, 3, 0));
    // 	timeline.AddObject("obj", obj);
    // 	timeline.AddObject("hero", hero);

    // 	var ai_controller = new BasicAiController(obj);
    // 	ai_controller.AddCommander(new PatrolAiCommander(), name: "patrol", priority: 0);
    // 	ai_controller.AddCommander(new GuardReactionCommander(), name: "reaction", priority: 1);
    // 	obj.SetAiController(ai_controller);

    // 	timeline.SetReversedPass(true);
    // 	timeline.SetMinimalStep(long.MinValue);
    // 	hero.SetReversed(true);
    // 	obj.SetReversed(true);

    // 	ai_controller
    // 		.GetCommander<PatrolAiCommander>()
    // 		.SetPoints(
    // 			new MyList<PatrolPoint>()
    // 			{
    // 				new PatrolPoint(new Vector3(2, 2, 0)),
    // 				new PatrolPoint(new Vector3(1, 0, 0)),
    // 				new PatrolPoint(new Vector3(0, 1, 0))
    // 			}
    // 		);

    // 	timeline.PromoteToTime(-0.1f);
    // 	timeline.PromoteToTime(-1.1f);
    // 	checker.Equal(
    // 		(obj.CurrentAnimatronic() as MovingAnimatronic).FinishPosition(),
    // 		new Vector3(2, 2, 0)
    // 	);
    // 	checker.Equal(
    // 		(obj.AiController() as BasicAiController)
    // 			.GetCommander<PatrolAiCommander>()
    // 			.TargetPointIndex(),
    // 		0
    // 	);
    // 	checker.NotEqual(obj.Position(), new Vector3(0, 0, 0));

    // 	timeline.PromoteToTime(-3.47f);
    // 	checker.Equal(obj.Position(), new Vector3(2, 2, 0), 1.0f);
    // 	checker.Equal(
    // 		(obj.AiController() as BasicAiController)
    // 			.GetCommander<PatrolAiCommander>()
    // 			.TargetPointIndex(),
    // 		1
    // 	);

    // 	timeline.PromoteToTime(-5.79f);
    // 	checker.Equal(obj.Position(), new Vector3(1, 0, 0), 0.5f);
    // 	checker.Equal(
    // 		(obj.AiController() as BasicAiController)
    // 			.GetCommander<PatrolAiCommander>()
    // 			.TargetPointIndex(),
    // 		2
    // 	);

    // 	timeline.PromoteToTime(-7.50f);
    // 	checker.Equal(
    // 		(obj.AiController() as BasicAiController)
    // 			.GetCommander<PatrolAiCommander>()
    // 			.TargetPointIndex(),
    // 		0
    // 	);

    // 	timeline.PromoteToTime(-10.0f);
    // 	checker.Equal(
    // 		(obj.AiController() as BasicAiController)
    // 			.GetCommander<PatrolAiCommander>()
    // 			.TargetPointIndex(),
    // 		1
    // 	);

    // 	checker.Equal(hero.IsDead, true);
    // }

    public static void CancelMovingTest(Checker checker)
    {
        Timeline tl = new Timeline();

        var guard = new Actor("guard");
        tl.AddObject(guard);
        guard.MoveToCommand(new Vector3(20, 0, 0), WalkingType.Walk);

        checker.Equal(tl.IsPast(), false);
        tl.PromoteToTime(0.5f);
        checker.Equal(guard.Position(), new Vector3(0.495f, 0, 0), 1e-2f);

        guard.MoveToCommand(new Vector3(0, 1, 0), WalkingType.Walk);

        tl.PromoteToTime(1.0f);
        checker.Equal(guard.Position(), new Vector3(0.27524662f, 0.44394618f, 0), 0.1f);
    }

    public static void CancelMovingTest_Reversed(Checker checker)
    {
        Timeline tl = new Timeline();

        var guard = new Actor("guard");
        tl.AddObject(guard);

        tl.SetReversedPass(true);
        tl.SetMinimalStep(long.MinValue);
        guard.SetReversed(true);

        guard.MoveToCommand(new Vector3(1, 0, 0), WalkingType.Walk);

        checker.Equal(tl.IsPast(), false);
        tl.PromoteToTime(-0.5f);
        checker.Equal(guard.Position(), new Vector3(0.495f, 0, 0), 1e-2f);

        guard.MoveToCommand(new Vector3(0, 1, 0), WalkingType.Walk);

        tl.PromoteToTime(-1.0f);
        checker.Equal(guard.Position(), new Vector3(0.27524662f, 0.44394618f, 0), 0.1f);
    }

    public static void CancelMovingTest_Reversed_AfterTimelineCopy(Checker checker)
    {
        ChronoSphere chronosphere = new ChronoSphere();
        Timeline tl = new Timeline();
        chronosphere.SetCurrentTimeline(tl);

        var guard = new Actor("guard");
        tl.AddObject(guard);

        tl.SetReversedPass(true);
        tl.SetMinimalStep(long.MinValue);
        guard.SetReversed(true);

        guard.MoveToCommand(new Vector3(1, 0, 0), WalkingType.Walk);

        checker.Equal(tl.IsPast(), false);
        tl.PromoteToTime(-0.1f);
        checker.NotEqual(guard.Position(), new Vector3(1, 0, 0));

        tl.PromoteToTime(-1.0f);
        checker.Equal(guard.Position(), new Vector3(0.995f, 0, 0f), 1e-2f);

        tl.PromoteToTime(-0.15f);
        //checker.Equal(guard.Position(), new Vector3(0.995f, 0, 0.1f));

        guard.MoveToCommand(new Vector3(1, 0, 0), WalkingType.Walk);
        //tl.Promote(-200);
    }

    public static void CancelDeathTest(Checker checker)
    {
        ChronoSphere chronosphere = new ChronoSphere();
        Timeline tl = new Timeline();
        chronosphere.SetCurrentTimeline(tl);

        var guard = new Actor("guard");
        tl.AddObject(guard);

        tl.Promote(100);
        tl.AddEvent(new DeathEvent(step: 100, actor: guard, who_kill_me: null, reversed: false));

        tl.Promote(200);
        checker.Equal(guard.IsDead || guard.IsPreDead, true);

        tl.Promote(0);
        checker.Equal(guard.IsDead || guard.IsPreDead, false);

        tl.Promote(50);

        checker.Equal(chronosphere.Timelines().Count, 1);
        guard.MoveToCommand(new Vector3(0, 1, 0), WalkingType.Walk);

        tl = chronosphere.CurrentTimeline();
        guard = tl.GetActor("guard");

        checker.Equal(chronosphere.Timelines().Count, 2);
        checker.Equal(tl.GlobalEvents().CountOfCards(), 0);

        tl.Promote(200);
        checker.Equal(guard.IsDead || guard.IsPreDead, false);

        tl.Promote(0);
        checker.Equal(guard.IsDead || guard.IsPreDead, false);
    }

    public static void CancelDeathTest_reversedPass(Checker checker)
    {
        ChronoSphere chronosphere = new ChronoSphere();
        Timeline tl = new Timeline();
        chronosphere.SetCurrentTimeline(tl);

        var guard = new Actor("guard");
        tl.AddObject(guard);

        tl.SetReversedPass(true);
        tl.SetMinimalStep(long.MinValue);
        guard.SetReversed(true);

        tl.Promote(1700);
        tl.AddEvent(
            new DeathEvent(step: 1700 - 100, actor: guard, who_kill_me: null, reversed: true)
        );

        tl.Promote(1700 - 200);
        checker.Equal(guard.IsDead || guard.IsPreDead, true);
        checker.Equal(tl.GlobalEvents().MyList.Count, 1);

        tl.Promote(1700);
        checker.Equal(guard.IsDead || guard.IsPreDead, false);

        tl.Promote(1700 - 50);

        checker.Equal(chronosphere.Timelines().Count, 1);
        guard.MoveToCommand(new Vector3(0, 1, 0), WalkingType.Walk);

        tl = chronosphere.CurrentTimeline();
        guard = tl.GetActor("guard");

        checker.Equal(chronosphere.Timelines().Count, 2);
        checker.Equal(tl.GlobalEvents().MyList.Count, 0);

        tl.Promote(1700 - 200);
        checker.Equal(guard.IsDead || guard.IsPreDead, false);

        tl.Promote(1700);
        checker.Equal(guard.IsDead || guard.IsPreDead, false);
    }

    public static void CancelDeathTest_reversedPass2(Checker checker)
    {
        //Timeline.direction_check_enabled = true;
        ChronoSphere chronosphere = new ChronoSphere();
        Timeline tl = new Timeline();
        chronosphere.SetCurrentTimeline(tl);

        var guard = new Actor("guard");
        tl.AddObject(guard);

        tl.SetReversedPass(true);
        tl.SetMinimalStep(long.MinValue);
        guard.SetReversed(true);

        tl.Promote(-100);
        tl.AddEvent(new DeathEvent(step: -100, actor: guard, who_kill_me: null, reversed: true));

        tl.Promote(-200);
        checker.Equal(guard.IsDead || guard.IsPreDead, true);

        tl.Promote(0);
        checker.Equal(guard.IsDead || guard.IsPreDead, false);

        tl.Promote(-50);

        checker.Equal(chronosphere.Timelines().Count, 1);
        guard.MoveToCommand(new Vector3(0, 1, 0), WalkingType.Walk);

        tl = chronosphere.CurrentTimeline();
        guard = tl.GetActor("guard");

        checker.Equal(chronosphere.Timelines().Count, 2);
        //        checker.Equal(tl.GlobalEvents().MyList.Count, 0);

        tl.Promote(-200);
        checker.Equal(guard.IsDead, false);

        tl.Promote(0);
        checker.Equal(guard.IsDead, false);
        //Timeline.direction_check_enabled = false;
    }
}
#endif
