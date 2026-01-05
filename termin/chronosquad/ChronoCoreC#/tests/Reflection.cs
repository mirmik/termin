#if !UNITY_64

public static class ReflectionTests
{
    static public void FieldScannerTest(Checker checker)
    {
        var scanresult = FieldScanner.DoScan(typeof(BasicMultipleAction));
        checker.IsTrue(scanresult[typeof(MovingAnimatronic)].Count > 10);
        // checker.Equal(scanresult[typeof(BlinkEffectEvent)].Count, 5);
    }

    // static public void SerializeCardTest(Checker checker)
    // {
    // 	var card = new TimeHast(1, 2, 3);
    // 	string text = FieldScanner.SerializeCardToJson(card);
    // 	Console.WriteLine(text);

    // 	var des = FieldScanner.DeserializeCardFromJson(text);

    // 	checker.IsTrue(des.IsEqual(card));
    // }

    // static public void SerializableCardsTest(Checker checker)
    // {
    //     // All cards must be serializable
    //     var types = FieldScanner.GetDerivedTypes(typeof(BasicMultipleAction));

    //     foreach (var type in types)
    //     {
    //         var has_serializable_attribute =
    //             type.GetCustomAttributes(typeof(SerializableAttribute), true).Length > 0;
    //         if (!has_serializable_attribute)
    //             Console.WriteLine(type);
    //         checker.IsTrue(has_serializable_attribute);
    //     }
    // }

    // static public void SerializeCardTest(Checker checker)
    // {
    //  	var card = new TimeHast(1, 2, 3);
    //  	string text = SimpleJsonParser.Serialize(card);
    //  	var des = SimpleJsonParser.Deserialize<TimeModifier>(text);
    //  	checker.IsTrue(des.IsEqual(card));
    // }

    // static public void SerializeCard_2_Test(Checker checker)
    // {
    //  	var card = new IdleAnimatronic(
    // 		start_step: 1,
    // 		finish_step: 2,
    // 		position : new Vector3(1, 2, 3),
    // 		direction : new Vector3(4, 5.51f, 6),
    // 		idle_type : IdleType.Croach
    // 	);
    //  	string text = SimpleJsonParser.Serialize(card);

    //  	var des = SimpleJsonParser.Deserialize<Animatronic>(text);

    //  	string text2 = SimpleJsonParser.Serialize(des);

    //  	checker.IsTrue(des.IsEqual(card));
    // 	checker.IsTrue(text == text2);
    // }

    // static public void SerializeCard_3_Test(Checker checker)
    // {
    //  	var card = new IdleAnimatronic(
    // 		start_step: 1,
    // 		finish_step: 2,
    // 		position : new Vector3(1, 2, 3),
    // 		direction : new Vector3(4, 5.53324132412352435243524123413241234121f, 6),
    // 		idle_type : IdleType.Croach
    // 	);
    //  	string text = SimpleJsonParser.Serialize(card);

    //  	var des = SimpleJsonParser.Deserialize<Animatronic>(text);

    //  	string text2 = SimpleJsonParser.Serialize(des);

    //  	checker.IsTrue(des.IsEqual(card));
    //  	checker.Equal(des.HashCode(), card.HashCode());
    // 	checker.IsTrue(text == text2);
    // }
}

#endif
