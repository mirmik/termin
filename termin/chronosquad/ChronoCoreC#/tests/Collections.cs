#if !UNITY_64

using System.Reflection;

static class CollectionsTests
{
    static public void ReflectionTest(Checker checker)
    {
        BasicMultipleAction a = new CommandMock(0, 100);
        BasicMultipleAction b = new CommandMock(0, 100);
        BasicMultipleAction c = new CommandMock(10, 100);

        var type = a.GetType();
        checker.Equal(type.Name, "CommandMock");
        checker.Equal(type.GetFields(BindingFlags.NonPublic | BindingFlags.Instance).Length, 2);

        checker.Equal(a.IsEqual(b), true);
        checker.Equal(a.IsEqual(c), false);
    }

    static public void Reflection2Test(Checker checker)
    {
        BasicMultipleAction a = new CommandMock(0, 100);
        TimeModifier b = new TimeModifier(0, 100);

        checker.Equal(a.IsEqual(b), false);
    }

    static public void Reflection3Test(Checker checker)
    {
        BasicMultipleAction a = new CommandMock(0, 100);
        TimeModifier b = new TimeModifier(0, 100);

        checker.NotEqual(a.GetHashCode(), b.GetHashCode());
    }

    static public void Reflection4Test(Checker checker)
    {
        TimeHast a = new TimeHast(0, 100, 12);
        TimeHast b = new TimeHast(0, 100, 11);

        checker.NotEqual(a.GetHashCode(), b.GetHashCode());
        checker.Equal(a.IsEqual(b), false);
    }

    // static public void Reflection5Test(Checker checker)
    // {
    // 	MovingAnimatronic a = new MovingAnimatronic(
    // 		WalkingType.Walk,
    // 		new ReferencedPose(new Vector3(0, 0, 0), new Vector3(1, 0, 0), null),
    // 		new ReferencedPoint(new Vector3(1, 0, 0), null),
    // 		0,
    // 		100,
    // 		1,
    // 		is_dragging: false
    // 	);

    // 	checker.Equal(
    // 		a.GetType().GetFields(BindingFlags.NonPublic | BindingFlags.Instance).Length,
    // 		6
    // 	);

    // 	checker.Equal(
    // 		a.GetType()
    // 			.BaseType.BaseType.GetFields(BindingFlags.NonPublic | BindingFlags.Instance)
    // 			.Length,
    // 		2
    // 	);
    // }

    static public void Reflection6Test(Checker checker)
    {
        ShootEffectEvent a = new ShootEffectEvent(
            start_step: 12,
            finish_step: 34,
            position1: new Vector3(0, 1, 2),
            position2: new Vector3(4, 5, 6)
        //ShootEffectMaterial : null
        );

        ShootEffectEvent b = new ShootEffectEvent(
            start_step: 0,
            finish_step: 0,
            position1: new Vector3(0, 1, 2),
            position2: new Vector3(4, 5, 6)
        //ShootEffectMaterial : null
        );

        ShootEffectEvent c = new ShootEffectEvent(
            start_step: 12,
            finish_step: 34,
            position1: new Vector3(0, 0, 0),
            position2: new Vector3(0, 0, 0)
        //ShootEffectMaterial: null
        );

        checker.NotEqual(a.HashCode(), b.HashCode());
        checker.NotEqual(a.HashCode(), c.HashCode());
    }

    static public void Reflection8Test(Checker checker)
    {
        ShootEffectEvent a = new ShootEffectEvent(
            start_step: 12,
            finish_step: 34,
            position1: new Vector3(0, 1, 2),
            position2: new Vector3(4, 5, 6)
        );

        checker.Equal(a.GetType(), typeof(ShootEffectEvent));
        checker.Equal(a.GetType().BaseType, typeof(GlobalEvent));
        checker.Equal(a.GetType().BaseType.BaseType, typeof(EventCard<ITimeline>));
        checker.Equal(a.GetType().BaseType.BaseType.BaseType, typeof(BasicMultipleAction));

        checker.Equal(
            a.GetType()
                .BaseType.BaseType.BaseType.GetFields(
                    BindingFlags.NonPublic | BindingFlags.Instance
                )
                .Length,
            2
        );
        checker.Equal(
            a.GetType()
                .BaseType.BaseType.GetFields(BindingFlags.NonPublic | BindingFlags.Instance)
                .Length,
            2
        );
        checker.Equal(
            a.GetType().BaseType.GetFields(BindingFlags.NonPublic | BindingFlags.Instance).Length,
            2
        );

        checker.Equal(a.GetFields().Count, 11);
    }

    static public void MultipleActionListTest(Checker checker)
    {
        MyList<BasicMultipleAction> added;
        MyList<BasicMultipleAction> goned;

        MultipleActionList<BasicMultipleAction> list = new MultipleActionList<BasicMultipleAction>(
            true
        );

        var a = new CommandMock(0, 100);
        var b = new CommandMock(10, 20);

        checker.NotEqual(a.HashCode(), b.HashCode());
        checker.NotEqual(a.HashCode(), (long)0);

        list.Add(a);
        list.Add(b);

        var list_from_start = list.GetListSortedByStartStep();
        var list_from_finish = list.GetListSortedByFinishStep();
        checker.Equal(list_from_start.Count, 2);
        checker.Equal(list_from_finish.Count, 2);
        checker.Equal(list_from_start.First.Value, a);
        //checker.Equal(list_from_start.Last.Value, b);
        //checker.Equal(list_from_finish.First.Value, a);
        checker.Equal(list_from_finish.Last.Value, b);

        list.PromoteList(1, out added, out goned);
        checker.Equal(list.ActiveStates().Count, 1);
        checker.Equal(added.Count, 1);
        checker.Equal(goned.Count, 0);
        checker.Equal(list.CurrentByStart().Value, a);
        checker.Equal(list.CurrentByFinish().Value, b);

        list.PromoteList(13, out added, out goned);
        checker.Equal(list.ActiveStates().Count, 2);
        checker.Equal(added.Count, 1);
        checker.Equal(goned.Count, 0);
        checker.Equal(list.CurrentByStart().Value, b);
        checker.Equal(list.CurrentByFinish().Value, b);

        list.PromoteList(24, out added, out goned);
        checker.Equal(list.ActiveStates().Count, 1);
        checker.Equal(added.Count, 0);
        checker.Equal(goned.Count, 1);
        checker.Equal(list.CurrentByStart().Value, b);
        checker.Equal(list.CurrentByFinish().Value, a);

        list.PromoteList(103, out added, out goned);
        checker.Equal(list.ActiveStates().Count, 0);
        checker.Equal(added.Count, 0);
        checker.Equal(goned.Count, 1);
        checker.Equal(list.CurrentByStart().Value, b);
        //checker.IsNull(list.CurrentByFinish());

        list.PromoteList(13, out added, out goned);
        checker.Equal(list.ActiveStates().Count, 2);
        checker.Equal(added.Count, 2);
        checker.Equal(goned.Count, 0);
        checker.Equal(list.CurrentByStart().Value, b);
        checker.Equal(list.CurrentByFinish().Value, b);

        list.PromoteList(-5, out added, out goned);
        checker.Equal(list.ActiveStates().Count, 0);
        checker.Equal(added.Count, 0);
        checker.Equal(goned.Count, 2);
        checker.IsNull(list.CurrentByStart());
        checker.Equal(list.CurrentByFinish().Value, b);
    }

    static public void MultipleActionList_Reversed_Test(Checker checker)
    {
        MyList<BasicMultipleAction> added;
        MyList<BasicMultipleAction> goned;

        MultipleActionList<BasicMultipleAction> list = new MultipleActionList<BasicMultipleAction>(
            true
        );

        var a = new CommandMock(900, 1000);

        list.Promote(2000, out added, out goned);
        list.Add(a);

        checker.Equal(list.ByStartIteratorPosition(), 0);
        //checker.Equal(list.ByFinishIteratorPosition(), -1);

        list.Promote(0, out added, out goned);

        checker.Equal(list.ByStartIteratorPosition(), -1);
        //checker.Equal(list.ByFinishIteratorPosition(), 0);

        list.Promote(2000, out added, out goned);

        //checker.Equal(list.ByStartIteratorPosition(), 0);
        //checker.Equal(list.ByFinishIteratorPosition(), -1);
    }

    static public void ActionListTest_Drop(Checker checker)
    {
        MyList<BasicMultipleAction> added;
        MyList<BasicMultipleAction> goned;

        ActionList<BasicMultipleAction> list = new ActionList<BasicMultipleAction>(true);

        var a = new CommandMock(0, 10);
        var b = new CommandMock(10, 20);
        var c = new CommandMock(20, 30);

        list.Add(a);
        list.Add(b);
        list.Add(c);

        list.Promote(15, out added, out goned);

        list.DropToCurrentState();

        checker.IsTrue(list.CurrentState() != null);
        checker.Equal(list.CurrentState(), b);
        checker.Equal(list.Count, 2);
    }

    static public void MultipleActionListTest_Drop(Checker checker)
    {
        MyList<BasicMultipleAction> added;
        MyList<BasicMultipleAction> goned;

        MultipleActionList<BasicMultipleAction> list = new MultipleActionList<BasicMultipleAction>(
            true
        );

        var a = new CommandMock(0, 10);
        var d = new CommandMock(0, 50);
        var c = new CommandMock(20, 30);
        var b = new CommandMock(10, 20);
        var e = new CommandMock(16, 40);

        list.Add(a);
        list.Add(c);
        list.Add(b);
        list.Add(d);
        list.Add(e);

        list.Promote(15, out added, out goned);
        checker.Equal(list.ActiveStates().Count, 2);
        checker.Equal(list.Count, 5);

        list.DropToCurrentState();

        checker.Equal(list.ActiveStates().Count, 2);
        checker.Equal(list.ActiveStates()[0], b);
        checker.Equal(list.Count, 3);
    }
}
#endif
