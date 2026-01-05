#if !UNITY_64
public static class GroupsTestClass
{
    public static void GroupTest(Checker checker)
    {
        Timeline tl = new Timeline();
        var obj1 = tl.CreateGuard("obj1");
        var obj2 = tl.CreateGuard("obj2");

        obj1.SetAiController(new BasicAiController(obj1));
        obj2.SetAiController(new BasicAiController(obj2));

        var group = new GroupController();
        group.SetChilds(new MyList<Actor> { obj1, obj2 });
    }
}

#endif
