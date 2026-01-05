#if !UNITY_64

public static class BurrowTests
{
    public static void BurrowTest(Checker checker)
    {
        ChronoSphere chronosphere = new ChronoSphere();
        var timeline = chronosphere.CreateEmptyTimeline();
        var actor = timeline.CreateObject<Actor>("actor");
        var enemy = timeline.CreateObject<Actor>("enemy");
        var burrow = timeline.CreateObject<PhysicalObject>("burrow");
        var burrow_aspect = timeline.CreateObject<PhysicalObject>("burrow_aspect");
        BurrowComponent component = new BurrowComponent(burrow);
        burrow.AddComponent(component);

        BurrowInternalAspect aspect = new BurrowInternalAspect(burrow_aspect);
        burrow_aspect.AddComponent(aspect);
        aspect.AddEntrance(burrow.Name());

        burrow.SetPosition(new Vector3(0, 0, 1));
        burrow_aspect.SetPosition(new Vector3(0, 0, 1));

        timeline.PromoteToTime(1.0f);
        checker.Equal(actor.CurrentReferencedPosition().LocalPosition, new Vector3(0, 0, 0));
        checker.Equal(burrow.CurrentReferencedPosition().LocalPosition, new Vector3(0, 0, 1));

        actor.AddExternalCommand(
            new MoveToInteractionCommand(burrow.ObjectId(), WalkingType.Walk, actor.LocalStep() + 1)
        );

        timeline.PromoteToTime(2.0f);
        checker.Equal(actor.CurrentReferencedPosition().LocalPosition, new Vector3(0, 0, 1));
        checker.Equal(burrow.GetComponent<BurrowComponent>().Contains("actor"), true);
        checker.Equal(actor.IsBurrowed(), true);

        checker.Equal(Raycaster.IsCanSee1(enemy, actor), false);
    }

    public static void Burrow2Test(Checker checker)
    {
        ChronoSphere chronosphere = new ChronoSphere();
        var timeline = chronosphere.CreateEmptyTimeline();
        var actor = timeline.CreateObject<Actor>("actor");
        var burrow = timeline.CreateObject<PhysicalObject>("burrow");
        var burrow_aspect = timeline.CreateObject<PhysicalObject>("burrow_aspect");
        BurrowComponent component = new BurrowComponent(burrow);
        burrow.AddComponent(component);

        BurrowInternalAspect aspect = new BurrowInternalAspect(burrow_aspect);
        burrow_aspect.AddComponent(aspect);
        aspect.AddEntrance(burrow.Name());

        burrow.SetPosition(new Vector3(0, 0, 1));
        burrow_aspect.SetPosition(new Vector3(0, 0, 1));

        timeline.PromoteToTime(1.0f);
        checker.Equal(actor.CurrentReferencedPosition().LocalPosition, new Vector3(0, 0, 0));
        checker.Equal(burrow.CurrentReferencedPosition().LocalPosition, new Vector3(0, 0, 1));

        actor.AddExternalCommand(
            new MoveToInteractionCommand(burrow.ObjectId(), WalkingType.Walk, actor.LocalStep() + 1)
        );

        timeline.PromoteToTime(2.0f);
        checker.Equal(actor.CurrentReferencedPosition().LocalPosition, new Vector3(0, 0, 1));
        checker.Equal(burrow.GetComponent<BurrowComponent>().Contains("actor"), true);
        checker.Equal(actor.IsBurrowed(), true);

        actor.AddExternalCommand(
            new MovingCommand(
                new ReferencedPoint(new Vector3(0, 0, 4), null),
                WalkingType.Walk,
                actor.LocalStep() + 1
            )
        );

        timeline.PromoteToTime(6.0f);
        checker.Equal(actor.CurrentReferencedPosition().LocalPosition, new Vector3(0, 0, 4));
        //checker.Equal(actor.IsBurrowed(), false);
    }
}

#endif
