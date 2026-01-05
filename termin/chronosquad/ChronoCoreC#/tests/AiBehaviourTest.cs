#if !UNITY_64
public static class AiBehaviourTestClass
{
    public static void PatrolTest_AiModule(Checker checker)
    {
        Actor obj = new Actor();
        Timeline timeline = new Timeline();
        timeline.AddObject("obj", obj);

        var ai_controller = new BasicAiController(obj);
        ai_controller.AddCommander(new PatrolAiCommander(), name: "patrol", priority: 0);
        obj.SetAiController(ai_controller);

        ai_controller
            .GetCommander<PatrolAiCommander>()
            .SetPoints(
                new MyList<PatrolPoint>()
                {
                    new PatrolPoint(new Vector3(2, 0, 2)),
                    new PatrolPoint(new Vector3(1, 0, 0)),
                    new PatrolPoint(new Vector3(0, 0, 1))
                }
            );
        checker.Equal(obj.Position(), new Vector3(0, 0, 0));

        timeline.Promote(20);
        checker.IsNotNull(obj.CurrentAnimatronic());
        checker.Equal(obj.CurrentAnimatronic().GetType(), typeof(MovingAnimatronic));
        checker.Equal(
            (obj.CurrentAnimatronic() as MovingAnimatronic).FinishPosition(),
            new Vector3(2, 0, 2)
        );
        checker.Equal(
            (obj.AiController() as BasicAiController)
                .GetCommander<PatrolAiCommander>()
                .TargetPointIndex(),
            0
        );
        checker.NotEqual(obj.Position(), new Vector3(0, 0, 0));

        //checker.Equal(obj.CurrentAnimatronic().FinishTime, 2.8375f);
        timeline.PromoteToTime(2.95f);

        var commander = ai_controller.GetCommander("patrol");
        var card1 = commander.Changes.MyList.AsList()[0];
        var card2 = commander.Changes.MyList.AsList()[1];
        checker.Equal(card1.GetType(), typeof(ChangePatrolStateEvent));
        checker.Equal(((ChangePatrolStateEvent)card1).prevstate.point_no, 0);
        checker.Equal(((ChangePatrolStateEvent)card1).prevstate.phase.phase, PatrolStatePhase.Move);
        checker.Equal(((ChangePatrolStateEvent)card1).nextstate.point_no, 0);
        checker.Equal(
            ((ChangePatrolStateEvent)card1).nextstate.phase.phase,
            PatrolStatePhase.RotateAfterMove
        );

        checker.Equal(((ChangePatrolStateEvent)card2).prevstate.point_no, 0);
        checker.Equal(((ChangePatrolStateEvent)card2).prevstate.phase.phase, PatrolStatePhase.Move);
        checker.Equal(((ChangePatrolStateEvent)card2).nextstate.point_no, 0);
        checker.Equal(
            ((ChangePatrolStateEvent)card2).nextstate.phase.phase,
            PatrolStatePhase.RotateAfterMove
        );
        // checker.Equal(card1.StartStep, 684);
        // checker.Equal(card1.FinishStep, 684);
        // var card2 = commander.Changes.MyList.AsList()[1];
        // checker.Equal(card2.GetType(), typeof(ChangePatrolStateEvent));
        // checker.Equal(((ChangePatrolStateEvent)card2).prevstate, 0);
        // checker.Equal(((ChangePatrolStateEvent)card2).nextstate, 1);
        // checker.Equal(card2.StartStep, 684);
        // checker.Equal(card2.FinishStep, 684);

        timeline.PromoteToTime(2.95f);
        checker.Equal(
            (obj.AiController() as BasicAiController)
                .GetCommander<PatrolAiCommander>()
                .TargetPointIndex(),
            1
        );

        timeline.PromoteToTime(5.4f);
        checker.Equal(
            (obj.AiController() as BasicAiController)
                .GetCommander<PatrolAiCommander>()
                .TargetPointIndex(),
            2
        );

        timeline.PromoteToTime(7.1f);
        checker.Equal(
            (obj.AiController() as BasicAiController)
                .GetCommander<PatrolAiCommander>()
                .TargetPointIndex(),
            0
        );

        timeline.PromoteToTime(9.2f);
        checker.Equal(
            (obj.AiController() as BasicAiController)
                .GetCommander<PatrolAiCommander>()
                .TargetPointIndex(),
            1
        );
    }

    public static void TimelineCopyPatrolTest_AiModule(Checker checker)
    {
        ChronoSphere chronosphere = new ChronoSphere();

        Actor obj = new Actor();
        Timeline timeline = new Timeline();
        chronosphere.AddTimeline(timeline);
        timeline.AddObject("obj", obj);
        timeline.SetCurrentTimeline();

        checker.Equal(timeline.GetChronosphere(), chronosphere);
        checker.Equal(obj.Chronosphere(), chronosphere);

        var behaviour = new BasicAiController(obj);
        behaviour.AddCommander(new PatrolAiCommander(), name: "patrol", priority: 0);
        obj.SetAiController(behaviour);

        behaviour
            .GetCommander<PatrolAiCommander>()
            .SetPoints(
                new MyList<PatrolPoint>()
                {
                    new PatrolPoint(new Vector3(2, 2, 0)),
                    new PatrolPoint(new Vector3(1, 0, 0)),
                    new PatrolPoint(new Vector3(0, 1, 0))
                }
            );

        timeline.Promote(20);
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

        timeline.PromoteToTime(2.94f);
        checker.Equal(obj.Position(), new Vector3(2, 2, 0), 0.5f);
        checker.Equal(
            (obj.AiController() as BasicAiController)
                .GetCommander<PatrolAiCommander>()
                .TargetPointIndex(),
            1
        );

        timeline.PromoteToTime(5.3f);
        checker.Equal(
            (obj.AiController() as BasicAiController)
                .GetCommander<PatrolAiCommander>()
                .TargetPointIndex(),
            2
        );

        timeline.PromoteToTime(7.1f);
        checker.Equal(
            (obj.AiController() as BasicAiController)
                .GetCommander<PatrolAiCommander>()
                .TargetPointIndex(),
            0
        );

        timeline.PromoteToTime(9.2f);
        checker.Equal(
            (obj.AiController() as BasicAiController)
                .GetCommander<PatrolAiCommander>()
                .TargetPointIndex(),
            1
        );

        checker.Equal((obj.AiController() as BasicAiController).GetObject(), obj);

        var timeline_copy = chronosphere.CreateCopyOfCurrentTimeline();
        checker.Equal(timeline_copy.Objects().Count, 1);
        var guard_copy = timeline_copy.Objects()["obj"] as Actor;

        checker.Equal(guard_copy.GetTimeline(), timeline_copy);
        checker.Equal(guard_copy.AiController().GetType(), typeof(BasicAiController));
        checker.Equal(
            (guard_copy.AiController() as BasicAiController)
                .GetCommander<PatrolAiCommander>()
                .TargetPointIndex(),
            1
        );
        checker.Equal(
            (guard_copy.AiController() as BasicAiController)
                .GetCommander<PatrolAiCommander>()
                .PatrolPoints()
                .Count,
            3
        );
        checker.Equal(guard_copy.AiController().GetObject().Name(), guard_copy.Name());
        checker.IsTrue(guard_copy.CurrentAnimatronic() is MovingAnimatronic);

        timeline_copy.PromoteToTime(2.95f);
        checker.Equal(
            (guard_copy.AiController() as BasicAiController)
                .GetCommander<PatrolAiCommander>()
                .TargetPointIndex(),
            1
        );

        timeline_copy.PromoteToTime(5.3f);
        checker.Equal(
            (guard_copy.AiController() as BasicAiController)
                .GetCommander<PatrolAiCommander>()
                .TargetPointIndex(),
            2
        );
    }

    // public static void PatrolCanSeeTest(Checker checker)
    // {
    // 	var tl = new Timeline();
    // 	var obj = new Actor("obj");
    // 	tl.AddObject(obj);

    // 	var hero = new Actor("hero");
    // 	tl.AddObject(hero);

    // 	obj.ImmediateBlinkTo(position: new Vector3(10, 0, 0), direction: new Vector3(1, 0, 0));
    // 	hero.ImmediateBlinkTo(position: new Vector3(0, 0, 0), direction: new Vector3(1, 0, 0));

    // 	tl.Promote(10);
    // 	checker.IsFalse(obj.CanSee(hero));

    // 	obj.ImmediateBlinkTo(position: new Vector3(0, 0, 0), direction: new Vector3(1, 0, 0));
    // 	hero.ImmediateBlinkTo(position: new Vector3(10, 0, 0), direction: new Vector3(1, 0, 0));

    // 	tl.Promote(20);
    // 	checker.IsTrue(obj.CanSee(hero));
    // }

    public static void MoveTest(Checker checker)
    {
        var tl = new Timeline();
        var obj = new Actor("obj");
        tl.AddObject(obj);

        checker.Equal(obj.Direction(), new Vector3(0, 0, 1));
        checker.Equal(obj.Position(), new Vector3(0, 0, 0));
        checker.Equal(obj.Rotation(), new Quaternion(0, 0, 0, 1));

        obj.MoveToCommand(new Vector3(0, 0, 10), is_run: false);
        tl.Promote(3000);
        checker.Equal(obj.Direction(), new Vector3(0, 0, 1), 1e-2f);
        checker.Equal(obj.Position(), new Vector3(0, 0, 10));
        checker.Equal(obj.Rotation(), new Quaternion(0, 0, 0, 1), 1e-4f);

        obj.MoveToCommand(new Vector3(10, 0, 10), is_run: false);
        tl.Promote(6000);
        checker.Equal(obj.Direction(), new Vector3(1, 0, 0), 1e-2f);
        checker.Equal(obj.Position(), new Vector3(10, 0, 10));
        checker.Equal(obj.Rotation(), new Quaternion(0, 0.70710677f, 0, 0.70710677f), 1e-3f);

        obj.MoveToCommand(new Vector3(10, 0, 0), is_run: false);
        tl.Promote(9000);
        checker.Equal(obj.Direction(), new Vector3(0, 0, -1), 1e-2f);
        checker.Equal(obj.Rotation(), new Quaternion(0, 1, 0, 0));
        checker.Equal(obj.Position(), new Vector3(10, 0, 0));
    }

    public static void LoudSoundReactionTest_AiModule(Checker checker)
    {
        var tl = new Timeline();
        var obj = new Actor("obj");
        tl.AddObject(obj);

        obj.SetAiController(new BasicAiController(obj));
        var patrol_behaviour = (BasicAiController)obj.AiController();
        patrol_behaviour.AddCommander(new GuardReactionCommander(), "reaction", 1);
        patrol_behaviour.AddCommander(new PatrolAiCommander(), "patrol", 0);

        checker.Equal(obj.Direction(), new Vector3(0, 0, 1));

        tl.Promote(1);
        var ev = new LoudSoundEvent(
            step: 5,
            center: new ReferencedPoint(new Vector3(-5, 0, 0), null),
            radius: 10,
            noise_parameters: new RestlessnessParameters(duration_of_attention: 10.0f, lures: true)
        );
        tl.AddEvent(ev);

        checker.Equal(ev.ListOfEnemiesInRadius(tl).Count, 1);

        tl.Promote(20);
        var ai_controller = obj.AiController();
        var attention_module = ai_controller.GetAttentionModule();
        var alarm_sources = attention_module.AlarmSources();
        checker.Equal(alarm_sources.Count, 1);

        tl.Promote(2000);
        checker.Equal(alarm_sources.Count, 1); // Должны ли alarm_sources удаляться?
        checker.Equal(attention_module.IsPanic(), true);
        checker.Equal(obj.Direction(), new Vector3(-1, 0, 0), 1e-3f);
        checker.Equal(obj.Position(), new Vector3(-5, 0, 0));

        tl.Promote(10000);
        checker.Equal(alarm_sources.Count, 0); // Должны ли alarm_sources удаляться?
        checker.Equal(attention_module.IsPanic(), false);
        checker.Equal(obj.Direction(), new Vector3(-1, 0, 0), 1e-3f);
        checker.Equal(obj.Position(), new Vector3(-5, 0, 0));

        // гвард не возвращается , поскольку последняя точка отсутствует
    }

    public static void LoudSoundPatrolReactionTest(Checker checker)
    {
        var tl = new Timeline();
        var obj = new Actor("obj");
        tl.AddObject(obj);

        obj.SetAiController(new BasicAiController(obj));
        var patrol = (BasicAiController)obj.AiController();
        patrol.AddCommander(new PatrolAiCommander(), "patrol", 0);
        patrol.AddCommander(new GuardReactionCommander(), "reaction", 1);
        patrol
            .GetCommander<PatrolAiCommander>()
            .SetPoints(
                new MyList<PatrolPoint>()
                {
                    new PatrolPoint(new Vector3(2, 2, 0)),
                    new PatrolPoint(new Vector3(1, 0, 0)),
                    new PatrolPoint(new Vector3(0, 1, 0))
                }
            );
        obj.SetAiController(patrol);
        var attention = patrol.AttentionModule();
        var animatronics = obj.Animatronics();
        var commands = obj.CommandBuffer().GetCommandQueue();

        tl.Promote(10);
        var ev = new LoudSoundEvent(
            step: 20,
            center: new ReferencedPoint(new Vector3(-5, 0, 0), null),
            radius: 10,
            noise_parameters: new RestlessnessParameters(duration_of_attention: 10.0f, lures: true)
        );
        tl.AddEvent(ev);

        checker.Equal(attention.AlarmSources().Count, 0);
        // 		checker.Equal(animatronics.Count, 2);
        // 		checker.Equal(animatronics.AsList()[0].GetType(), typeof(IdleAnimatronic));
        // //		checker.Equal(animatronics.AsList()[1].GetType(), typeof(MovingAnimatronic));
        // 		checker.Equal(commands.Count, 1);
        checker.Equal(obj.CommandBuffer().CommandsAdded.Count, 0);

        tl.Promote(30);
        //checker.Equal(obj.CommandBuffer().CommandsAdded.Count, 0);
        //checker.Equal(commands.Count, 2);
        // checker.Equal(commands.AsList()[0].GetType(), typeof(MovingCommand));
        // checker.Equal(commands.AsList()[0].StartStep, (long)4);
        // checker.Equal(commands.AsList()[0].FinishStep, (long)24);
        // checker.Equal(commands.AsList()[1].GetType(), typeof(MovingCommand));
        // checker.Equal(commands.AsList()[1].StartStep, (long)24);
        // checker.Equal(commands.AsList()[1].FinishStep, long.MaxValue);
        // checker.Equal((commands.AsList()[0] as MovingCommand).TargetPosition(), new Vector3(2,2,0));
        // checker.Equal((commands.AsList()[1] as MovingCommand).TargetPosition(), new Vector3(-5,0,0));
        // checker.Equal(animatronics.Count, 3);
        // checker.Equal(animatronics.AsList()[0].GetType(), typeof(IdleAnimatronic));
        // checker.Equal(animatronics.AsList()[1].GetType(), typeof(MovingAnimatronic));
        // checker.Equal(animatronics.AsList()[2].GetType(), typeof(MovingAnimatronic));
        // checker.Equal((animatronics.AsList()[0] as IdleAnimatronic).FinishStep, long.MaxValue);
        // checker.Equal((animatronics.AsList()[0] as IdleAnimatronic).InterruptionStep, (long)4);
        // checker.Equal((animatronics.AsList()[1] as MovingAnimatronic).StartStep, (long)4);
        // checker.Equal((animatronics.AsList()[1] as MovingAnimatronic).FinishStep, (long)682);
        // checker.Equal((animatronics.AsList()[1] as MovingAnimatronic).InterruptionStep, (long)24);
        // checker.Equal((animatronics.AsList()[1] as MovingAnimatronic).FinishPosition(), new Vector3(2, 2, 0));
        // checker.Equal((animatronics.AsList()[2] as MovingAnimatronic).StartStep, (long)24);
        // checker.Equal((animatronics.AsList()[2] as MovingAnimatronic).FinishStep, (long)1237);
        // checker.Equal((animatronics.AsList()[2] as MovingAnimatronic).InterruptionStep, (long)1237);
        // checker.Equal((animatronics.AsList()[2] as MovingAnimatronic).FinishPosition(), new Vector3(-5, 0, 0));
        checker.Equal(attention.AlarmSources().Count, 1);
        checker.Equal(attention.IsPanic(), true);

        tl.PromoteToTime(0.5f);
        checker.Equal(obj.Position(), new Vector3(-0.34f, 0.051f, 0), 0.1f);

        tl.PromoteToTime(5.2f);
        checker.Equal(attention.AlarmSources().Count, 1);
        checker.Equal(obj.Position(), new Vector3(-5, 0, 0), 0.1f);

        tl.PromoteToTime(8.0f);
        checker.Equal(attention.AlarmSources().Count, 1);
        checker.Equal(obj.Position(), new Vector3(-5, 0, 0), 0.1f);

        tl.PromoteToTime(16.0f);
        checker.Equal(attention.AlarmSources().Count, 0);
        checker.NotEqual(obj.Position(), new Vector3(-5, 0, 0));
    }

    public static void CorpsePatrolReactionTest(Checker checker)
    {
        var tl = new Timeline();
        var obj = new Actor("obj");
        tl.AddObject(obj);
        obj.AddAbility(new ShootAbility(shoot_distance: 10.0f));

        var patrol = new BasicAiController(obj);
        patrol.AddCommander(new PatrolAiCommander(), name: "patrol", priority: 0);
        patrol.AddCommander(new GuardReactionCommander(), name: "reaction", priority: 1);
        patrol
            .GetCommander<PatrolAiCommander>()
            .SetPoints(
                new MyList<PatrolPoint>()
                {
                    new PatrolPoint(new Vector3(2, 2, 0)),
                    new PatrolPoint(new Vector3(1, 0, 0)),
                    new PatrolPoint(new Vector3(0, 1, 0))
                }
            );
        obj.SetAiController(patrol);
        obj.AiController().AttentionModule().CorpseAttentionTime = 20.0f;

        var another = new Actor("another");
        another.DisableBehaviour();
        tl.AddObject(another);
        another.ImmediateBlinkTo(position: new Vector3(-5, 0, 0), direction: new Vector3(1, 0, 0));

        tl.Promote(1000);

        tl.Promote(1010);
        another.ImmediateDeath();
        checker.IsFalse(another.IsDead);
        var attention_module = obj.AiController().AttentionModule();

        tl.Promote(3000);
        // checker.IsTrue(another.IsDead);
        // checker.Equal(attention_module.AlarmSourcesList().Count(), 1);
        // var attention = patrol.Attention();

        // checker.LessThan((obj.Position() - new Vector3(-5, 0, 0)).magnitude, 1.0f);

        // tl.Promote(7000);
        // checker.IsTrue(another.IsDead);
        // //checker.Equal(attention.FoundedCorpses[0].name, "another");
        // checker.Equal(attention.FoundedCorpses.Count, 1);
        // checker.NotEqual(obj.Position(), new Vector3(-5, 0, 0));

        // tl.Promote(500);
        // checker.IsFalse(another.IsDead);
        // //tl.DropTimelineToCurrentState();
        // checker.Equal(attention.FoundedCorpses.Count, 0);

        // tl.Promote(3000);
        // checker.IsTrue(another.IsDead);

        // checker.Equal(attention.FoundedCorpses.Count, 1);
        // //checker.Equal(attention.AlarmSources()[0].Center(tl).LocalPosition, new Vector3(-5, 0, 0));

        // checker.LessThan((obj.Position() - new Vector3(-5, 0, 0)).magnitude, 1.0f);

        // tl.Promote(7000);
        // checker.NotEqual(obj.Position(), new Vector3(-5, 0, 0));

        // tl.Promote(500);
        // checker.IsFalse(another.IsDead);
        // tl.DropTimelineToCurrentState();
        // checker.Equal(attention.FoundedCorpses.Count, 0);

        // tl.PromoteToTime(1.0f);
        // checker.IsFalse(another.IsDead);

        // checker.Equal(attention.FoundedCorpses.Count, 0);
        // //checker.Equal(attention[0].Center(), new Vector3(-5, 0, 0));

        // checker.NotEqual(obj.Position(), new Vector3(-5, 0, 0));

        // tl.Promote(7000);
        // checker.NotEqual(obj.Position(), new Vector3(-5, 0, 0));
    }

    public static void PatrolTest_HeroHunt_AiModule(Checker checker)
    {
        Actor obj = new Actor();
        Actor hero = new Actor();
        Timeline timeline = new Timeline();

        obj.AddAbility(new ShootAbility(shoot_distance: 10.0f, can_shoot_from_croach: true));

        hero.MarkAsHero();
        hero.SetPosition(new Vector3(3, 0, 3));
        timeline.AddObject("obj", obj);
        timeline.AddObject("hero", hero);

        var ai_controller = new BasicAiController(obj);
        ai_controller.AddCommander(new PatrolAiCommander(), name: "patrol", priority: 0);
        ai_controller.AddCommander(new GuardReactionCommander(), name: "reaction", priority: 1);
        obj.SetAiController(ai_controller);

        ai_controller
            .GetCommander<PatrolAiCommander>()
            .SetPoints(
                new MyList<PatrolPoint>()
                {
                    new PatrolPoint(new Vector3(2, 0, 2)),
                    new PatrolPoint(new Vector3(1, 0, 0)),
                    new PatrolPoint(new Vector3(0, 0, 1))
                }
            );

        timeline.Promote(50);
        checker.IsTrue(Raycaster.IsCanSee1(obj, hero));
        checker.Equal(
            timeline.present.CanSeeMatrix()[obj._timeline_index, hero._timeline_index],
            CanSee.See
        );
        //checker.Equal(obj.AiController().GetAttentionModule().AlarmSourcesList().Count, 1);
        checker.IsTrue(obj.CommandBuffer().GetCommandQueue().AsList()[0] is MovingCommand);

        timeline.Promote(60);
        //checker.Equal(obj.AiController().GetAttentionModule().AlarmSourcesList().Count, 1);
        checker.IsTrue(obj.CommandBuffer().GetCommandQueue().AsList()[0] is MovingCommand);
        //checker.IsTrue(obj.CommandBuffer().GetCommandQueue().AsList()[1] is StubCommand);
        checker.IsTrue(obj.CommandBuffer().GetCommandQueue().AsList()[2] is ShootCommand);
        //checker.IsTrue(obj.CommandBuffer().GetCommandQueue().AsList()[2] is MovingCommand);
        checker.Equal(obj.CommandBuffer().GetCommandQueue().Count, 3);
        checker.IsTrue(obj.CurrentCommand() is ShootCommand);

        checker.IsTrue(Raycaster.IsCanSee1(obj, hero));
        checker.Equal(hero.CurrentReferencedPoint().LocalPosition, new Vector3(3, 0, 3));

        timeline.Promote(150);
        checker.Equal(
            (obj.AiController() as BasicAiController)
                .GetCommander<PatrolAiCommander>()
                .TargetPointIndex(),
            0
        );
        checker.NotEqual(obj.Position(), new Vector3(0, 0, 0));

        timeline.PromoteToTime(3.5f);
        checker.IsTrue(
            (obj.AiController() as BasicAiController)
                .GetCommander<PatrolAiCommander>()
                .TargetPointIndex() == 0
                || (obj.AiController() as BasicAiController)
                    .GetCommander<PatrolAiCommander>()
                    .TargetPointIndex() == 1
        );

        timeline.PromoteToTime(5.8f);
        checker.IsTrue(
            (obj.AiController() as BasicAiController)
                .GetCommander<PatrolAiCommander>()
                .TargetPointIndex() == 1
                || (obj.AiController() as BasicAiController)
                    .GetCommander<PatrolAiCommander>()
                    .TargetPointIndex() == 2
        );

        // timeline.PromoteToTime(7.7f);
        // checker.IsTrue(
        // 	(obj.AiController() as BasicAiController)
        // 		.GetCommander<PatrolAiCommander>()
        // 		.TargetPointIndex() == 0 ||
        // 	(obj.AiController() as BasicAiController)
        // 		.GetCommander<PatrolAiCommander>()
        // 		.TargetPointIndex() == 2
        // );

        timeline.PromoteToTime(9.7f);
        checker.IsTrue(
            (obj.AiController() as BasicAiController)
                .GetCommander<PatrolAiCommander>()
                .TargetPointIndex() == 0
                || (obj.AiController() as BasicAiController)
                    .GetCommander<PatrolAiCommander>()
                    .TargetPointIndex() == 1
        );

        //checker.Equal(obj.AiController().GetAttentionModule().AlarmSourcesList().Count, 1);
        checker.Equal(hero.IsDead, true);
    }
}
#endif
