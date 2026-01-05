#if !UNITY_64

[TestClass]
public static class VariantsTests
{
    public static void VariantTest(Checker checker)
    {
        var chronosphere = new ChronoSphere();
        var tl = new Timeline();
        chronosphere.AddTimeline(tl);
        var actor = new Actor();
        var enemy = new Actor();
        tl.AddObject("actor", actor);
        tl.AddObject("enemy", enemy);

        var activity = new ShootAbility(100);
        actor.AddAbility(activity);

        actor.MoveToCommand(new Vector3(40.0f, 0, 0));

        tl.PromoteToTime(10.0f);
        actor.TearWithReverse();

        checker.Equal(tl.Objects().Count, 3);
        checker.Equal(actor.GlobalPosition(), new Vector3(10.0f, 0, 0), 0.1f);

        tl.PromoteToTime(5.0f);
        checker.Equal(actor.GlobalPosition(), new Vector3(5.0f, 0, 0), 0.1f);

        var obj2 = tl.ObjectList()[2];
        checker.Equal(obj2.GlobalPosition(), new Vector3(15.0f, 0, 0), 0.1f);

        obj2.TearWithReverse();
        checker.Equal(obj2.GlobalPosition(), new Vector3(15.0f, 0, 0), 0.1f);

        var obj3 = tl.ObjectList()[3];
        checker.Equal(obj3.GlobalPosition(), new Vector3(15.0f, 0, 0), 0.1f);

        tl.PromoteToTime(10.0f);

        checker.Equal(obj2.GlobalPosition(), new Vector3(10.0f, 0, 0), 0.1f);
        checker.Equal(obj3.GlobalPosition(), new Vector3(20.0f, 0, 0), 0.1f);
        checker.Equal(tl.Objects().Count, 4);

        tl.PromoteToTime(15.0f);
        obj3.AbilityUseOnObject<ShootAbility>(enemy);

        tl.PromoteToTime(20.0f);
        checker.Equal(enemy.IsDead, true);

        tl.DeleteVariant(obj3);
        checker.Equal(enemy.IsDead, false);
        checker.Equal(tl.Objects().Count, 3);
    }

    public static void Variant2Test(Checker checker)
    {
        var chronosphere = new ChronoSphere();
        var tl = new Timeline();
        chronosphere.AddTimeline(tl);
        var actor = new Actor();
        var enemy = new Actor();
        tl.AddObject("actor", actor);
        tl.AddObject("enemy", enemy);

        var activity = new ShootAbility(100);
        actor.AddAbility(activity);

        actor.MoveToCommand(new Vector3(40.0f, 0, 0));

        tl.PromoteToTime(10.0f);
        actor.TearWithReverse();

        checker.Equal(tl.Objects().Count, 3);
        checker.Equal(actor.GlobalPosition(), new Vector3(10.0f, 0, 0), 0.1f);

        tl.PromoteToTime(5.0f);
        checker.Equal(actor.GlobalPosition(), new Vector3(5.0f, 0, 0), 0.1f);

        var obj2 = tl.ObjectList()[2];
        checker.Equal(obj2.GlobalPosition(), new Vector3(15.0f, 0, 0), 0.1f);

        obj2.TearWithReverse();
        checker.Equal(obj2.GlobalPosition(), new Vector3(15.0f, 0, 0), 0.1f);

        var obj3 = tl.ObjectList()[3];
        checker.Equal(obj3.GlobalPosition(), new Vector3(15.0f, 0, 0), 0.1f);

        tl.PromoteToTime(10.0f);

        checker.Equal(obj2.GlobalPosition(), new Vector3(10.0f, 0, 0), 0.1f);
        checker.Equal(obj3.GlobalPosition(), new Vector3(20.0f, 0, 0), 0.1f);
        checker.Equal(tl.Objects().Count, 4);

        var fourd = actor.FourD;
        tl.PromoteToTime(15.0f);
        checker.Equal(fourd.CountOfViewedViews(), 1);

        tl.PromoteToTime(7.5f);
        checker.Equal(fourd.CountOfViewedViews(), 3);

        Debug.Log("HERE");
        checker.IsTrue(fourd.views[0].InBrokenInterval());
        checker.IsTrue(fourd.views[1].InBrokenInterval());
        checker.IsTrue(fourd.views[2].InBrokenInterval());
    }
}

#endif
