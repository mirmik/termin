#if !UNITY_64

public static class SerializeTests
{
    // static public void C0Test(Checker checker)
    // {
    // 	var card = new TimeHast(1, 2, 3);
    // 	var dct = card.ToTrent();
    // 	var des = BasicMultipleAction.CreateFromTrent(dct);

    // 	string text = SimpleJsonParser.SerializeTrent(dct);

    // 	var des2dct = SimpleJsonParser.DeserializeTrent(text) as Dictionary<string, object>;
    // 	var des2 = BasicMultipleAction.CreateFromTrent(des2dct);

    // 	checker.IsTrue(des.IsEqual(card));
    // 	checker.IsTrue(des2.IsEqual(card));

    // }

    // static public void C1Test(Checker checker)
    // {
    // 	Timeline timeline = new Timeline();
    // 	var guard0 =timeline.CreateGuard("guard0");
    // 	var guard1 =timeline.CreateGuard("guard1");

    // 	var tr = timeline.ToTrent();
    // 	var des = Timeline.CreateFromTrent(tr) as Timeline;

    // 	checker.IsTrue(des.IsEqual(timeline));
    // }

    // 	static public void C2Test(Checker checker)
    // {
    // 	Timeline timeline = new Timeline();
    // 	var guard0 =timeline.CreateGuard("guard0");
    // 	var guard1 =timeline.CreateGuard("guard1");

    // 	guard0.MoveToCommand(new Vector3(1, 0, 0), WalkingType.Walk);

    // 	timeline.PromoteToTime(10.0f);

    // 	var tr = timeline.ToTrent();
    // 	var des = Timeline.CreateFromTrent(tr) as Timeline;

    // 	checker.Equal(des.Objects().Count, 2);
    // 	var des_guard0 = des.Objects().Values.ToList()[0] as Actor;
    // 	checker.Equal(des_guard0.Position(), new Vector3(1, 0, 0));
    // 	checker.Equal(guard0.CommandBuffer().GetCommandQueue().Count, 1);
    // 	checker.Equal(des_guard0.CommandBuffer().GetCommandQueue().Count, 1);

    // 	checker.IsTrue(des.IsEqual(timeline));

    // 	var trstr = SimpleJsonParser.SerializeTrent(tr);
    // 	//Console.WriteLine(trstr);
    // }
}

#endif
