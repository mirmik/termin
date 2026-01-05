#if !UNITY_64

using System.Reflection;

static class ComplexPatrolTests
{
    static public void ComplexPatrolTest_Stand(Checker checker)
    {
        Actor obj = new Actor();
        Timeline timeline = new Timeline();
        timeline.AddObject("obj", obj);

        var ai_controller = new BasicAiController(obj);
        var commander = new PatrolAiCommander();
        ai_controller.AddCommander(commander, name: "patrol", priority: 0);
        obj.SetAiController(ai_controller);

        ai_controller
            .GetCommander<PatrolAiCommander>()
            .SetPoints(
                new MyList<PatrolPoint>()
                {
                    new PatrolPoint(new Vector3(5, 0, 0), stand_time: 1.0f),
                    new PatrolPoint(new Vector3(5, 0, 5)),
                    new PatrolPoint(new Vector3(0, 0, 5))
                }
            );

        timeline.PromoteToTime(6.0f);
        checker.Equal(obj.Position(), new Vector3(5, 0, 0), 0.5f);

        checker.Equal(obj.Animatronics().AsList()[0] is MovingAnimatronic, true);
        checker.Equal(obj.Animatronics().AsList()[1].GetType(), typeof(RotateAnimatronic));
        checker.Equal(obj.Animatronics().AsList()[2].GetType(), typeof(PatrolIdleAnimatronic));
        checker.Equal(obj.Animatronics().AsList().Count, 3);
        checker.Equal(commander.CurrentPatrolState().phase.phase, PatrolStatePhase.Stand);
        checker.Equal((commander.Changes.CountOfCards()), 4);
        // checker.Equal((commander.Changes.list.AsList()[0] as ChangePatrolStateEvent).nextstate.phase.phase, PatrolStatePhase.RotateAfterMove);
        // checker.Equal((commander.Changes.list.AsList()[1] as ChangePatrolStateEvent).nextstate.phase.phase, PatrolStatePhase.RotateAfterMove);
        // checker.Equal((commander.Changes.list.AsList()[2] as ChangePatrolStateEvent).nextstate.phase.phase, PatrolStatePhase.RotateAfterMove);
        // checker.Equal((commander.Changes.list.AsList()[3] as ChangePatrolStateEvent).nextstate.phase.phase, PatrolStatePhase.RotateAfterMove);

        timeline.PromoteToTime(7.0f);
        checker.Equal(obj.Position(), new Vector3(5, 0, 1), 0.1f);
    }

    static public void ComplexPatrolTest_Interaction(Checker checker)
    {
        Actor obj = new Actor();
        PhysicalObject terminal = new PhysicalObject();
        terminal.SetPosition(new Vector3(6, 0, 0));
        Timeline timeline = new Timeline();
        timeline.AddObject("obj", obj);
        timeline.AddObject("terminal", terminal);

        terminal.DisableBehaviour();
        var ai_controller = new BasicAiController(obj);
        ai_controller.AddCommander(new PatrolAiCommander(), name: "patrol", priority: 0);
        obj.SetAiController(ai_controller);

        ai_controller
            .GetCommander<PatrolAiCommander>()
            .SetPoints(
                new MyList<PatrolPoint>()
                {
                    new PatrolPoint(new Vector3(5, 0, 0)),
                    new PatrolPoint(
                        new Vector3(5.1f, 0, 0),
                        patrolPointType: PatrolPointType.ServiceSystemCheck,
                        interaction_object_name: "terminal"
                    ),
                    new PatrolPoint(new Vector3(5, 0, 5)),
                    new PatrolPoint(new Vector3(0, 0, 5))
                }
            );

        timeline.PromoteToTime(5.0f);
        checker.Equal(obj.Position(), new Vector3(5, 0, 0), 0.1f);

        timeline.PromoteToTime(5.9f);
        checker.Equal(obj.Position(), new Vector3(6, 0, 0), 0.1f);

        checker.Equal(terminal.Position(), new Vector3(6, 0, 0));
    }
}

#endif
