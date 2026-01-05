#if !UNITY_64
public static class GrabTestClass
{
    public static void GrabAliveTest(Checker checker)
    {
        Timeline timeline = new Timeline();
        var actor = timeline.CreateGuard("actor");
        var corpse = timeline.CreateGuard("corpse");
        corpse.SetAiController(new BasicAiController(corpse));

        corpse.SetPosition(new Vector3(5, 0, 0));
        actor._can_grab_alived = true;

        timeline.Promote(100);

        checker.Equal(corpse.GlobalPosition(), new Vector3(5, 0, 0));

        //corpse.ImmediateDeath();

        timeline.Promote(200);

        checker.IsTrue(!corpse.IsDead);
        checker.IsTrue(!actor.IsDead);

        actor.AddExternalCommand(
            new GrabCommand(corpse.ObjectId(), actor.LocalStep() + 1, is_dragging: false)
        );

        timeline.Promote(850);

        checker.Equal(actor.GlobalPosition(), new Vector3(5, 0, 0));

        checker.Equal(actor.grabbed_actor, corpse.ObjectId());
        checker.Equal(corpse.MovedWith(), actor.ObjectId());

        actor.AddExternalCommand(
            new MovingCommand(
                target_position: new ReferencedPoint(new Vector3(10, 0, 0), null),
                walking_type: WalkingType.Walk,
                stamp: actor.LocalStep()
            )
        );

        timeline.Promote(2200);
        checker.Equal(actor.GlobalPosition(), new Vector3(10, 0, 0));
        checker.Equal(corpse.GlobalPosition(), new Vector3(10, 0, 0));

        actor.AddExternalCommand(
            new UnGrabCommand(
                new ReferencedPoint(new Vector3(15, 0, 0), null),
                actor.LocalStep() + 1
            )
        );

        timeline.Promote(3500);
        checker.Equal(actor.GlobalPosition(), new Vector3(15, 0, 0));
        checker.Equal(corpse.GlobalPosition(), new Vector3(15, 0, 0));

        checker.Equal(actor.grabbed_actor, default(ObjectId));
        checker.Equal(corpse.MovedWith(), default(ObjectId));
    }

    public static void GrabCorpseDragTest(Checker checker)
    {
        Timeline timeline = new Timeline();
        var actor = timeline.CreateGuard("actor");
        var corpse = timeline.CreateGuard("corpse");
        corpse.SetAiController(new BasicAiController(corpse));

        corpse.SetPosition(new Vector3(5, 0, 0));
        actor._can_grab_corpse = true;

        timeline.Promote(100);

        checker.Equal(corpse.GlobalPosition(), new Vector3(5, 0, 0));

        corpse.ImmediateDeath();

        timeline.Promote(200);

        checker.IsTrue(corpse.IsDead || corpse.IsPreDead);
        checker.IsTrue(!actor.IsDead);

        actor.AddExternalCommand(
            new GrabCommand(corpse.ObjectId(), actor.LocalStep() + 1, is_dragging: true)
        );

        timeline.Promote(900);

        checker.Equal(actor.GlobalPosition(), new Vector3(5, 0, 0));

        checker.Equal(actor.grabbed_actor, corpse.ObjectId());
        //checker.Equal(corpse.MovedWith(), actor.ObjectId());

        actor.AddExternalCommand(
            new MovingCommand(
                target_position: new ReferencedPoint(new Vector3(10, 0, 0), null),
                walking_type: WalkingType.Walk,
                stamp: actor.LocalStep()
            )
        );

        timeline.Promote(2200);
        checker.Equal(actor.GlobalPosition(), new Vector3(10, 0, 0));
        checker.Equal(corpse.GlobalPosition(), new Vector3(9, 0, 0));

        actor.AddExternalCommand(
            new UnGrabCommand(
                new ReferencedPoint(new Vector3(15, 0, 0), null),
                actor.LocalStep() + 1
            )
        );

        timeline.Promote(3500);
        checker.Equal(actor.GlobalPosition(), new Vector3(15, 0, 0));
        checker.Equal(corpse.GlobalPosition(), new Vector3(14, 0, 0));

        checker.Equal(actor.grabbed_actor, default(ObjectId));
        checker.Equal(corpse.MovedWith(), default(ObjectId));
    }

    public static void GrabNonDragTest(Checker checker)
    {
        Timeline timeline = new Timeline();
        var actor = timeline.CreateGuard("actor");
        var corpse = timeline.CreateGuard("corpse");
        corpse.SetAiController(new BasicAiController(corpse));

        corpse.SetPosition(new Vector3(5, 0, 0));
        actor._can_grab_corpse = true;

        timeline.Promote(100);

        checker.Equal(corpse.GlobalPosition(), new Vector3(5, 0, 0));

        corpse.ImmediateDeath();

        timeline.Promote(200);

        checker.IsTrue(corpse.IsDead || corpse.IsPreDead);
        checker.IsTrue(!actor.IsDead);

        actor.AddExternalCommand(
            new GrabCommand(corpse.ObjectId(), actor.LocalStep() + 1, is_dragging: false)
        );

        timeline.Promote(900);

        checker.Equal(actor.GlobalPosition(), new Vector3(5, 0, 0));

        checker.Equal(actor.grabbed_actor, corpse.ObjectId());
        //checker.Equal(corpse.MovedWith(), actor.ObjectId());

        actor.AddExternalCommand(
            new MovingCommand(
                target_position: new ReferencedPoint(new Vector3(10, 0, 0), null),
                walking_type: WalkingType.Walk,
                stamp: actor.LocalStep()
            )
        );

        timeline.Promote(2200);
        checker.Equal(actor.GlobalPosition(), new Vector3(10, 0, 0));
        checker.Equal(corpse.GlobalPosition(), new Vector3(10, 0, 0));

        actor.AddExternalCommand(
            new UnGrabCommand(
                new ReferencedPoint(new Vector3(15, 0, 0), null),
                actor.LocalStep() + 1,
                walktype: WalkingType.Walk
            )
        );

        timeline.Promote(3500);
        checker.Equal(actor.GlobalPosition(), new Vector3(15, 0, 0));
        checker.Equal(corpse.GlobalPosition(), new Vector3(15, 0, 0));

        checker.Equal(actor.grabbed_actor, default(ObjectId));
        checker.Equal(corpse.MovedWith(), default(ObjectId));
    }
}
#endif
